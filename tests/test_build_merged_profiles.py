"""Tests for the source-level merged profile builder and base class resolution."""
from __future__ import annotations

import ast
import dataclasses
import importlib
import logging
import sys
import types
from pathlib import Path

import pytest

from cimprofiles.build_merged_profiles import (_CONFIG, _first_line, _load_config,
                                               _module_source, _package_dir, build_release,
                                               merge_sources)
from cimprofiles.identity import Identity
from cimprofiles.merge import merge_profiles, most_specific_base
from cimprofiles.units import UnitMultiplier, UnitSymbol

RELEASES = _load_config(_CONFIG)


def _field(cls, name):
    return next(f for f in dataclasses.fields(cls) if f.name == name)


@pytest.mark.parametrize('module', [
    'cimprofiles.cim18.cim18v17.substation.substation',
    'cimprofiles.cim18.cim18gmdm.electrical.electrical',
    'cimprofiles.cim17.cgmes_3_0_0.core_equipment.core_equipment',
])
def test_single_part_reproduces_cimtool_class_source(module):
    """Every class of a part comes out byte-identical, so the CIMTool layout is kept."""
    source = _module_source(module)
    merged, _exported = merge_sources({module: source})

    lines = source.split('\n')
    body = ast.parse(source).body
    starts = [_first_line(node) for node in body] + [len(lines) + 1]
    for index, node in enumerate(body):
        if isinstance(node, ast.ClassDef) and node.name != 'Identity':
            block = '\n'.join(lines[starts[index] - 1:starts[index + 1] - 1])
            assert block in merged, node.name


@pytest.mark.parametrize('release', RELEASES, ids=lambda release: release['name'])
def test_committed_merged_profiles_are_up_to_date(release):
    """The committed files match a fresh build; re-run the builder if this fails."""
    package_dir = _package_dir(release['package'])
    for file_name, content in build_release(release).items():
        assert (package_dir / file_name).read_text(encoding='utf-8') == content, file_name


def test_most_specific_base_picks_the_deepest_candidate():
    parents = {'Terminal': {'Identity', 'ACDCTerminal'},
               'ACDCTerminal': {'IdentifiedObject'},
               'IdentifiedObject': {'Identity'}}
    assert most_specific_base('Terminal', {'Identity', 'ACDCTerminal'}, parents) == 'ACDCTerminal'


def test_most_specific_base_rejects_unrelated_candidates():
    parents = {'X': {'A', 'B'}, 'A': {'Identity'}, 'B': {'Identity'}}
    with pytest.raises(ValueError, match="Conflicting base classes for 'X'"):
        most_specific_base('X', {'A', 'B'}, parents)


# Two parts in the shape of CIMTool output. Part B selects Terminal without
# IdentifiedObject, so CIMTool flattened its base to Identity.
PART_A = """from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from cimprofiles.identity import Identity, stereotype

NAMESPACES = {'cim': 'http://cim#'}

class CIMStereotype(Enum):
    Concrete = 'Concrete'

class PhaseKind(Enum):
    A = 'A'

@dataclass(repr=False, eq=False)
class IdentifiedObject(Identity):
    name: Optional[str] = field(default=None, metadata={'serialize': True})

@dataclass(repr=False, eq=False)
class Terminal(IdentifiedObject):
    '''Terminal from part A.'''
    phases: Optional[PhaseKind] = field(default=None, metadata={'serialize': True})
    Equipment: Optional[Equipment] = field(default=None, metadata={'inverse': 'Equipment.Terminals', 'serialize': False})
    '''inverse end, from part A'''

@dataclass(repr=False, eq=False)
class Equipment(IdentifiedObject):
    Terminals: list[Terminal] = field(default_factory=list, metadata={'inverse': 'Terminal.Equipment', 'serialize': False})
    '''Terminals, from part A'''
"""
PART_B = """from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from cimprofiles.identity import Identity, stereotype

NAMESPACES = {'cim': 'http://cim#', 'gad': 'http://gad#'}

class CIMStereotype(Enum):
    Concrete = 'Concrete'

class PhaseKind(Enum):
    A = 'A'
    B = 'B'

@stereotype(CIMStereotype.Concrete)
@dataclass(repr=False, eq=False)
class Terminal(Identity):
    '''Terminal from part B.'''
    Equipment: Optional[Equipment] = field(default=None, metadata={'inverse': 'Equipment.Terminals', 'serialize': True})
    '''own end, from part B'''
    sequenceNumber: Optional[int] = field(default=None, metadata={'serialize': True})

@dataclass(repr=False, eq=False)
class Equipment(Identity):
    Terminals: list[Terminal] = field(default_factory=list, metadata={'inverse': 'Terminal.Equipment', 'serialize': False})
    '''Terminals, from part B'''
"""


def _module(monkeypatch, name: str, source: str) -> types.ModuleType:
    module = types.ModuleType(name)
    monkeypatch.setitem(sys.modules, name, module)
    exec(source, module.__dict__)
    # Exported like a CIMTool init file: Identity and the part's classes but CIMStereotype
    module.__all__ = ['Identity'] + [key for key, value in vars(module).items() if isinstance(value, type)
                                     and value.__module__ == name and key != 'CIMStereotype']
    return module


def test_merge_sources_follows_the_merge_rules(monkeypatch):
    own_identity = "\nclass Identity:\n    '''A profile's own Identity class.'''\n"
    source, exported = merge_sources({'part_a': PART_A, 'part_b': PART_B + own_identity})
    merged = _module(monkeypatch, 'merged_parts', source)

    assert merged.Terminal.__bases__ == (merged.IdentifiedObject,)       # the most specific base
    assert merged.Identity is Identity                                     # the profile's own is dropped
    assert [f.name for f in dataclasses.fields(merged.Terminal)] \
        == ['identifier', 'name', 'phases', 'Equipment', 'sequenceNumber']  # union, first-seen order
    assert _field(merged.Terminal, 'Equipment').metadata['serialize'] is True  # the serialized end
    assert "'''own end, from part B'''" in source and 'inverse end, from part A' not in source
    assert 'Terminals, from part A' in source and 'Terminals, from part B' not in source  # else the earliest
    assert "'''Terminal from part A.'''" in source                         # the first docstring
    assert '@stereotype(CIMStereotype.Concrete)\n@dataclass(repr=False, eq=False)\nclass Terminal(' in source
    assert set(merged.PhaseKind.__members__) == {'A', 'B'}
    assert 'CIMStereotype' not in exported
    assert {'Identity', 'UnitSymbol', 'UnitMultiplier'} <= set(exported)


def test_merge_sources_rejects_disagreeing_enum_values():
    with pytest.raises(ValueError, match='PhaseKind: parts disagree on member A'):
        merge_sources({'part_a': PART_A, 'part_b': PART_B.replace("A = 'A'", "A = 'X'")})


def test_runtime_merge_resolves_flattened_bases(monkeypatch):
    merged = merge_profiles(_module(monkeypatch, 'part_a', PART_A), _module(monkeypatch, 'part_b', PART_B))
    assert issubclass(merged.Terminal, merged.IdentifiedObject)
    assert {'phases', 'Equipment', 'sequenceNumber'} <= {f.name for f in dataclasses.fields(merged.Terminal)}


@pytest.mark.parametrize('release', RELEASES, ids=lambda release: release['name'])
def test_merged_source_fits_the_parts_line_width(release):
    merged = build_release(release)[f"{release['name']}.py"]
    part_width = max(len(line) for part in release['parts'] for line in _module_source(part).split('\n'))
    assert max(len(line) for line in merged.split('\n')) <= part_width


@pytest.mark.parametrize('release', RELEASES, ids=lambda release: release['name'])
def test_merged_profiles_use_the_library_unit_enums(release):
    """The parts import UnitSymbol/UnitMultiplier from cimprofiles, so CIMUnit.unit is the library enum."""
    package = importlib.import_module(release['package'])
    assert package.UnitSymbol is UnitSymbol and package.UnitMultiplier is UnitMultiplier


def test_conflicting_property_raises():
    part_a = "class X(Identity):\n    @property\n    def __package__(self):\n        return 'Core'\n"
    part_b = "class X(Identity):\n    @property\n    def __package__(self):\n        return 'Wires'\n"
    with pytest.raises(ValueError, match='parts disagree on def __package__'):
        merge_sources({'a': part_a, 'b': part_b})


def test_uml_conflict_is_logged(caplog):
    part_a = ("class X(Identity):\n"
              "    Y: Optional[A] = field(default=None, metadata={'inverse': 'A.X', 'serialize': True})\n")
    part_b = ("class X(Identity):\n"
              "    Y: Optional[B] = field(default=None, metadata={'inverse': 'B.X', 'serialize': True})\n")
    with caplog.at_level(logging.WARNING):
        merged, _ = merge_sources({'a': part_a, 'b': part_b})
    assert 'UML conflict: X.Y' in caplog.text
    assert 'Optional[A]' in merged and 'Optional[B]' not in merged


def _part_source(namespaces: dict | None) -> str:
    source = "BASE_URI = 'http://example.com/profile#'\n"
    if namespaces is not None:
        source += f'NAMESPACES = {namespaces!r}\n'
    return source


def test_merge_sources_unions_part_namespaces():
    merged, _exported = merge_sources({
        'part_a': _part_source({'cim': 'http://cim#', 'nc': 'http://nc#'}),
        'part_b': _part_source({'cim': 'http://cim#', 'gad': 'http://gad#'}),
    })
    assert ("NAMESPACES = {\n    'cim': 'http://cim#',\n    'gad': 'http://gad#',\n    'nc': 'http://nc#',\n}"
            in merged)


def test_merge_sources_rejects_a_part_without_namespaces():
    with pytest.raises(ValueError, match=r"\['part_b'\] declare no NAMESPACES"):
        merge_sources({'part_a': _part_source({'cim': 'http://cim#'}),
                       'part_b': _part_source(None)})
