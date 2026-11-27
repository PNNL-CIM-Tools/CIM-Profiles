"""Tests for the source-level merged profile builder and base class resolution."""
from __future__ import annotations

import ast
import dataclasses
import logging
import sys
import types

import pytest

from cimprofiles.build_merged_profiles import _first_line, _module_source, build_release, merge_sources
from cimprofiles.identity import Identity
from cimprofiles.merge import merge_profiles, most_specific_base
from cimprofiles.units import UnitMultiplier, UnitSymbol

# The fixture profiles of tests/fixtures/README.md, test_c first: its Terminal.ConductingEquipment
# is the inverse end of the association that test_a serializes
FIXTURE_RELEASE = {'name': 'fixture_cab', 'package': 'fixture_profiles.cim17',
                   'parts': [f'fixture_profiles.cim17.{name}.{name}' for name in ('test_c', 'test_a', 'test_b')]}


def _field(cls, name):
    return next(f for f in dataclasses.fields(cls) if f.name == name)


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


@pytest.mark.parametrize('part', FIXTURE_RELEASE['parts'])
def test_single_part_reproduces_cimtool_class_source(part):
    """Every class of a part comes out byte-identical, so the CIMTool layout is kept."""
    source = _module_source(part)
    merged, _exported = merge_sources({part: source})

    lines = source.split('\n')
    body = ast.parse(source).body
    starts = [_first_line(node) for node in body] + [len(lines) + 1]
    for index, node in enumerate(body):
        if isinstance(node, ast.ClassDef) and node.name != 'Identity':
            block = '\n'.join(lines[starts[index] - 1:starts[index + 1] - 1])
            assert block in merged, node.name


def _module(monkeypatch, name: str, source: str) -> types.ModuleType:
    module = types.ModuleType(name)
    monkeypatch.setitem(sys.modules, name, module)
    exec(source, module.__dict__)
    # Exported like a CIMTool init file: Identity and the part's classes but CIMStereotype
    module.__all__ = ['Identity'] + [key for key, value in vars(module).items() if isinstance(value, type)
                                     and value.__module__ == name and key != 'CIMStereotype']
    return module


def test_merged_fixture_release_follows_the_merge_rules(monkeypatch):
    merged = _module(monkeypatch, 'fixture_cab', build_release(FIXTURE_RELEASE)['fixture_cab.py'])

    # CIMTool roots a class at its nearest profiled ancestor; the merge picks the most specific
    assert merged.Terminal.__bases__ == (merged.ACDCTerminal,)
    assert merged.ConductingEquipment.__bases__ == (merged.Equipment,)
    assert merged.EnergyConsumer.__bases__ == (merged.ConductingEquipment,)
    assert merged.EnergyConsumer.__stereotype__.value == 'Concrete'      # only test_b's is concrete
    assert set(merged.PhaseCode.__members__) == {'A', 'B', 'C', 'ABC', 'N', 'AB', 's1', 's2'}
    assert merged.NAMESPACES == {'cim': 'http://iec.ch/TC57/CIM-generic#', 'eu': 'http://iec.ch/TC57/CIM100-European#',
                                 'nc': 'http://entsoe.eu/ns/nc#'}
    assert _field(merged.Terminal, 'ConductingEquipment').metadata['serialize'] is True
    terminal_fields = {f.name for f in dataclasses.fields(merged.Terminal)}
    assert {'shortName', 'connected', 'phases', 'ConnectivityNode'} <= terminal_fields   # from all three parts
    assert merged.UnitSymbol is UnitSymbol and merged.UnitMultiplier is UnitMultiplier


def test_merged_source_fits_the_parts_line_width():
    merged = build_release(FIXTURE_RELEASE)['fixture_cab.py']
    part_width = max(len(line) for part in FIXTURE_RELEASE['parts'] for line in _module_source(part).split('\n'))
    assert max(len(line) for line in merged.split('\n')) <= part_width


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
