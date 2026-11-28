"""The cimantic-graphs builders and the import pipeline, on the fixture profiles of
tests/fixtures/README.md: real CIMTool output of fixed .owl files."""
import dataclasses
import importlib
import os
import subprocess
import typing
from pathlib import Path

import pytest

from cimprofiles.dedupe_profile_fields import find_duplicates, main as dedupe
from cimprofiles.units import CIMUnit, UnitMultiplier, UnitSymbol

REPO = Path(__file__).parents[1]
CIMTOOL_OUTPUT = REPO / 'tests' / 'fixtures' / 'cimtool' / 'Profiles'
IMPORTED = REPO / 'tests' / 'fixture_profiles' / 'cim17'
PARTS = ['test_a', 'test_b', 'test_c']


def _profile(name: str):
    return importlib.import_module(f'fixture_profiles.cim17.{name}.{name}')


def test_import_pipeline_reproduces_the_fixture_packages(tmp_path):
    """import_cimtool_output.sh, then dedupe_profile_fields, turns the CIMTool output into the
    committed packages. If this fails after a pipeline change, rerun generate.sh."""
    env = {**os.environ, 'IMPORT_ROOT': str(tmp_path), 'IMPORT_PACKAGE': 'fixture_profiles'}
    for name in PARTS:
        subprocess.run([REPO / 'scripts' / 'import_cimtool_output.sh', 'cim17',
                        CIMTOOL_OUTPUT / f'{name}.cimantic-graphs.py', CIMTOOL_OUTPUT / f'{name}.__init__.py'],
                       env=env, check=True, capture_output=True)
    dedupe([str(tmp_path / 'cim17'), '--log', str(tmp_path / 'dedupe.log')])
    for name in PARTS:
        for file_name in (f'{name}.py', '__init__.py', 'context.jsonld'):
            assert (tmp_path / 'cim17' / name / file_name).read_text() \
                == (IMPORTED / name / file_name).read_text(), f'{name}/{file_name}'


def test_cimtool_writes_both_ends_of_an_association_twice():
    """Why dedupe_profile_fields runs on every import: test_a profiles both ends of
    Terminal.ConductingEquipment, and the builder writes ConductingEquipment.Terminals twice."""
    duplicates = find_duplicates((CIMTOOL_OUTPUT / 'test_a.cimantic-graphs.py').read_text())
    assert ('ConductingEquipment', 'Terminals') in {(dup['class'], dup['field']) for dup in duplicates}
    assert {dup['kind'] for dup in duplicates} == {'exporter duplicate'}
    assert find_duplicates((IMPORTED / 'test_a' / 'test_a.py').read_text()) == []


@pytest.mark.parametrize('name', PARTS)
def test_profile_declares_a_prefix_for_every_namespace_it_uses(name):
    module = _profile(name)
    used = {module.ONTOLOGY_URI}
    for value in vars(module).values():
        if dataclasses.is_dataclass(value) and isinstance(value, type):
            used |= {f.metadata['namespace'] for f in dataclasses.fields(value) if 'namespace' in f.metadata}
    assert module.NAMESPACES['cim'] == module.ONTOLOGY_URI
    assert used <= set(module.NAMESPACES.values())


@pytest.mark.parametrize('name', PARTS)
def test_profile_classes_resolve_their_type_hints(name):
    """cim-graph and cimtables reflect on the classes, so every annotation must resolve."""
    module = _profile(name)
    for value in vars(module).values():
        if dataclasses.is_dataclass(value) and isinstance(value, type):
            typing.get_type_hints(value)


@pytest.mark.parametrize('name', PARTS)
def test_profile_units_keep_cim_unit_behaviour(name):
    """Generated CIMUnit classes use @dataclass(eq=False), so CIMUnit's quantity equality
    applies, and their unit enums are the library's."""
    module = _profile(name)
    units = [value for value in vars(module).values()
             if isinstance(value, type) and issubclass(value, CIMUnit) and value is not CIMUnit]
    assert units
    for unit in units:
        assert '__eq__' not in vars(unit), unit.__name__
    assert module.UnitSymbol is UnitSymbol and module.UnitMultiplier is UnitMultiplier


def test_units_carry_their_schema_multiplier():
    test_c = _profile('test_c')
    assert test_c.KiloActivePower(5).multiplier is UnitMultiplier.k
    assert test_c.KiloActivePower(5) == _profile('test_b').ActivePower(5000)
