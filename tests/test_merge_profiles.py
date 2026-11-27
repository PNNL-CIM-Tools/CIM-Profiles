"""Tests for runtime CIM profile merging, on the fixture profiles of tests/fixtures/README.md."""
from __future__ import annotations

import importlib
import sys
import typing
from dataclasses import fields, is_dataclass
from enum import Enum

import pytest
from fixture_profiles.cim17 import test_a as part_a
from fixture_profiles.cim17 import test_b as part_b
from fixture_profiles.cim17 import test_c as part_c

from cimprofiles.merge import generate_type_stubs, merge_namespaces, merge_profiles


def _field_names(cls) -> set[str]:
    return {f.name for f in fields(cls)}


def test_merged_all_is_the_union():
    merged = merge_profiles(part_a, part_b, part_c)
    assert set(part_a.__all__) | set(part_b.__all__) | set(part_c.__all__) == set(merged.__all__)


def test_overlapping_classes_get_the_union_of_their_fields():
    merged = merge_profiles(part_a, part_b)
    assert {'ACLineSegmentPhases', 'r', 'x', 'PerLengthImpedance'} <= _field_names(merged.ACLineSegment)
    assert 'length' in _field_names(merged.Conductor)       # only test_b profiles it


def test_classes_of_one_part_are_kept():
    merged = merge_profiles(part_a, part_b)
    assert 'ConnectivityNode' in merged.__all__ and is_dataclass(merged.ConnectivityNode)
    assert 'PerLengthPhaseImpedance' in merged.__all__ and is_dataclass(merged.PerLengthPhaseImpedance)


def test_flattened_bases_resolve_to_the_most_specific():
    """CIMTool roots a class at its nearest profiled ancestor: test_b has Terminal(IdentifiedObject),
    test_c ConductingEquipment(PowerSystemResource) and EnergyConsumer(ConductingEquipment)."""
    merged = merge_profiles(part_a, part_b, part_c)
    assert merged.Terminal.__bases__ == (merged.ACDCTerminal,)
    assert merged.ConductingEquipment.__bases__ == (merged.Equipment,)
    assert merged.EnergyConsumer.__bases__ == (merged.ConductingEquipment,)
    assert issubclass(merged.ACLineSegment, merged.Conductor)
    assert merged.Conductor.__bases__ == (merged.ConductingEquipment,)


def test_field_metadata_and_stereotypes_survive():
    merged = merge_profiles(part_a, part_b)
    for name in ('PerLengthImpedance', 'ACLineSegmentPhases'):
        metadata = merged.ACLineSegment.__dataclass_fields__[name].metadata
        assert {'namespace', 'serialize', 'inverse'} <= set(metadata)
    assert merged.ACLineSegment.__stereotype__.value == 'Concrete'
    assert issubclass(merged.PhaseCode, Enum)


def test_enumerations_get_the_union_of_their_members():
    # test_a restricts PhaseCode to A, B, C, ABC, N and test_b to A, B, C, AB, ABC, s1, s2
    merged = merge_profiles(part_a, part_b)
    assert list(merged.PhaseCode.__members__) == ['A', 'ABC', 'B', 'C', 'N', 'AB', 's1', 's2']
    assert merged.PhaseCode.AB.__namespace__ == 'http://iec.ch/TC57/CIM-generic#'
    assert merged.PhaseCode in typing.get_args(typing.get_type_hints(merged.Terminal)['phases'])


def test_the_serialized_association_end_wins():
    # test_c has only ConductingEquipment.Terminals, so its Terminal.ConductingEquipment is the
    # inverse end; test_a profiles both ends
    merged = merge_profiles(part_c, part_a)
    assert merged.Terminal.__dataclass_fields__['ConductingEquipment'].metadata['serialize'] is True


def test_merged_class_is_instantiable():
    merged = merge_profiles(part_a, part_b)
    line = merged.ACLineSegment(identifier='test-uuid-1234', r=merged.Resistance(0.5))
    assert line.ACLineSegmentPhases == [] and line.PerLengthImpedance is None
    assert float(line.r) == 0.5


def test_merged_class_type_hints_resolve():
    """typing.get_type_hints must work on merged classes (cimtables and cim-graph reflect on
    them): their string annotations are evaluated in the merged module."""
    merged = merge_profiles(part_a, part_b)
    hints = typing.get_type_hints(merged.ACLineSegment)
    assert merged.PerLengthImpedance in typing.get_args(hints['PerLengthImpedance'])
    assert merged.BaseVoltage in typing.get_args(hints['BaseVoltage'])
    assert sys.modules[merged.ACLineSegment.__module__] is merged


def test_runtime_merge_unions_part_namespaces():
    merged = merge_profiles(part_a, part_b, part_c)
    assert merged.NAMESPACES == {'cim': 'http://iec.ch/TC57/CIM-generic#', 'nc': 'http://entsoe.eu/ns/nc#',
                                 'eu': 'http://iec.ch/TC57/CIM100-European#'}


def test_merge_requires_two_modules():
    with pytest.raises(ValueError, match='at least two modules'):
        merge_profiles(part_a)


def test_merge_namespaces_unions_maps():
    assert merge_namespaces({'cim': 'http://cim#'}, {'cim': 'http://cim#', 'gad': 'http://gad#'}) == {
        'cim': 'http://cim#', 'gad': 'http://gad#'}


def test_merge_namespaces_rejects_a_prefix_bound_twice():
    with pytest.raises(ValueError, match="XML prefix 'cim' is bound to both"):
        merge_namespaces({'cim': 'http://cim.ucaiug.io/cim101/draft#'},
                         {'cim': 'http://cim.ucaiug.io/CIM101/draft#'})


def test_merge_namespaces_rejects_a_namespace_with_two_prefixes():
    with pytest.raises(ValueError, match='has two XML prefixes'):
        merge_namespaces({'gad': 'http://gridappsd.org/CIM/extension#'},
                         {'gridappsd': 'http://gridappsd.org/CIM/extension#'})


# ── type stubs ──────────────────────────────────────────────────────────

def _import_stubs(path):
    sys.path.insert(0, str(path.parent))
    try:
        return importlib.import_module(path.stem)
    finally:
        sys.path.pop(0)


def test_type_stubs_cover_the_merged_profile(tmp_path):
    out = tmp_path / 'cim_stubs.py'
    generate_type_stubs(part_a, part_b, part_c, output_path=str(out))
    content = out.read_text()
    assert content.startswith('# AUTO-GENERATED') and 'from __future__ import annotations' in content
    # ACLineSegment is in all three parts: a class inheriting from each
    assert 'class ACLineSegment(_p0_ACLineSegment, _p1_ACLineSegment, _p2_ACLineSegment): ...' in content
    # ConnectivityNode is only in test_a: a re-export
    assert 'from fixture_profiles.cim17.test_a import ConnectivityNode as ConnectivityNode' in content
    try:
        stubs = _import_stubs(out)
        assert set(stubs.__all__) == set(merge_profiles(part_a, part_b, part_c).__all__)
        assert isinstance(stubs.ACLineSegment, type) and hasattr(stubs, 'ConnectivityNode')
    finally:
        sys.modules.pop('cim_stubs', None)


def test_type_stubs_require_two_modules():
    with pytest.raises(ValueError, match='at least two modules'):
        generate_type_stubs(part_a, output_path='/dev/null')
