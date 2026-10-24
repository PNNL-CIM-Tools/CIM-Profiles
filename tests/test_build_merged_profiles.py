"""Tests for the source-level merged profile builder and base class resolution."""
from __future__ import annotations

import ast
import dataclasses
import importlib
import logging
from pathlib import Path

import pytest

from cimprofiles.build_merged_profiles import (_CONFIG, _first_line, _load_config,
                                               _module_source, _package_dir, build_release,
                                               merge_sources)
from cimprofiles.merge import merge_profiles, most_specific_base

RELEASES = _load_config(_CONFIG)
CIM18V17 = next(release for release in RELEASES if release['name'] == 'cim18v17')


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


def test_runtime_merge_resolves_flattened_bases():
    """asset declares Terminal(Identity), substation Terminal(ACDCTerminal)."""
    from cimprofiles.cim18.cim18v17 import asset, substation

    merged = merge_profiles(asset, substation)
    assert issubclass(merged.Terminal, merged.ACDCTerminal)


def test_cim18v17_unions_fields_across_parts():
    import cimprofiles.cim18.cim18v17 as cim

    field_names = {f.name for f in dataclasses.fields(cim.ACLineSegment)}
    assert 'r' in field_names                     # electrical_balanced
    assert 'WireConfiguration' in field_names     # electrical_unbalanced
    assert issubclass(cim.Terminal, cim.ACDCTerminal)
    assert cim.Identity is importlib.import_module('cimprofiles.identity').Identity


def test_cim18v17_keeps_the_serialized_association_end():
    """asset serializes Asset.AssetDeployment; asset_deployment only has the inverse end."""
    import cimprofiles.cim18.cim18v17 as cim

    assert _field(cim.Asset, 'AssetDeployment').metadata['serialize'] is True


def test_cim18v17_unions_enum_members():
    import cimprofiles.cim18.cim18v17 as cim

    members = set(cim.SinglePhaseKind.__members__)
    for part in ('electrical_balanced', 'construction', 'connectivity_unbalanced'):
        module = importlib.import_module(f'cimprofiles.cim18.cim18v17.{part}')
        assert set(module.SinglePhaseKind.__members__) <= members


def test_cim18v17_source_keeps_field_docstrings_and_line_width():
    merged = (_package_dir(CIM18V17['package']) / 'cim18v17.py').read_text(encoding='utf-8')
    part_width = max(len(line) for part in CIM18V17['parts']
                     for line in _module_source(part).split('\n'))

    assert max(len(line) for line in merged.split('\n')) <= part_width
    assert "    mRID: Optional[str] = field(\n        default=None,\n" in merged
    assert 'Master resource identifier issued by a model authority.' in merged


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
