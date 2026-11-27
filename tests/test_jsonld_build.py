import json
import sys
import types
from pathlib import Path

import pytest

import cimprofiles.cim17.cimhub_2023 as cimhub
from cimprofiles import PROFILE_PACKAGES
from cimprofiles.jsonld import build, profile_jsonld
from cimprofiles.jsonld.build import (build_context, build_vocabulary, convention_units,
                                      expand_parts, merge_contexts, part_profile, stable_version)
from cimprofiles.jsonld.context import (context_prefixes, property_datatypes, vocabulary_iri,
                                        vocabulary_units)

FIXTURES = Path(__file__).parent / 'fixture_profiles' / 'cim17'


def test_context_datatypes_follow_field_metadata():
    datatypes = property_datatypes(build_context(cimhub))
    assert datatypes['ACLineSegment.r'] == 'xsd:float'                 # CIMUnit
    assert datatypes['Terminal.ConductingEquipment'] == '@id'          # association
    assert datatypes['EnergyConsumer.phaseConnection'] == '@id'        # enumeration
    assert datatypes['ACDCTerminal.connected'] == 'xsd:boolean'
    assert datatypes['ACDCTerminal.sequenceNumber'] == 'xsd:integer'
    assert 'IdentifiedObject.name' not in datatypes                    # string is the default
    assert 'ACLineSegment.length' not in datatypes                     # declared on Conductor
    assert context_prefixes(build_context(cimhub))['cim'] == 'http://iec.ch/TC57/CIM100#'


def test_context_types_the_dataset_header():
    """Header references are IRIs and dates are dates, as in the Inst4CIM CGMES context."""
    context = build_context(cimhub)['@context']
    assert context['dct:conformsTo'] == {'@type': '@id'}
    assert context['dcat:isVersionOf'] == {'@type': '@id'}
    assert context['dct:issued'] == {'@type': 'xsd:dateTime'}


def test_merging_contexts_that_disagree_fails():
    first = {'@context': {'cim': 'http://iec.ch/TC57/CIM100#', 'cim:A.b': {'@type': 'xsd:float'}}}
    second = {'@context': {'cim': 'http://iec.ch/TC57/CIM100#', 'cim:A.b': {'@type': '@id'}}}
    assert merge_contexts([first, first]) == first
    with pytest.raises(ValueError, match='cim:A.b'):
        merge_contexts([first, second])


def test_convention_resolution_order():
    convention = {'quantity_kinds': {'ActivePower': 'kW', 'Length': 'km'},
                  'properties': {'WireInfo.radius': 'mm'}}
    units = convention_units(cimhub, convention)
    assert units['EnergyConsumer.p'][0] == 'kW'          # quantity kind default
    assert units['WireInfo.radius'][0] == 'mm'           # property override wins
    assert units['Conductor.length'][0] == 'km'
    assert units['ACLineSegment.r'][0] == 'ohm'          # CIMUnit base unit
    assert convention_units(cimhub, {})['EnergyConsumer.p'][0] == 'W'


@pytest.mark.parametrize('convention, message', [
    ({'properties': {'WireInfo.radius': 'kW'}}, 'not a unit of Length'),
    ({'properties': {'WireInfo.nope': 'mm'}}, 'WireInfo.nope'),
    ({'quantity_kinds': {'Banana': 'kW'}}, 'Banana'),
])
def test_bad_conventions_fail(convention, message):
    with pytest.raises(ValueError, match=message):
        convention_units(cimhub, convention)


def test_vocabulary_round_trips_through_the_reader():
    iri = 'https://example.org/cimhub/units-test.jsonld'
    vocabulary = build_vocabulary(cimhub, {'quantity_kinds': {'ActivePower': 'kW'}}, iri, 'test')
    prefixes = context_prefixes(vocabulary)
    assert vocabulary_iri(vocabulary, prefixes) == iri
    units = vocabulary_units(vocabulary, prefixes)
    assert units['EnergyConsumer.p'] == 'kW'
    assert units['ACLineSegment.r'] == 'ohm'
    assert 'PowerTransformerEnd.ratedU' in units
    assert 'IdentifiedObject.name' not in units


def test_profile_lookup_by_package_name():
    assert profile_jsonld('cimprofiles.cim17.cimhub_2023') == profile_jsonld('cimhub_2023')
    with pytest.raises(KeyError, match='cimhub_2099'):
        profile_jsonld('cimhub_2099')


W3C_PROFILE = """
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from cimprofiles.identity import Identity

NAMESPACES = {'gad': 'http://gridappsd.org/CIM/extension#', 'dcterms': 'http://purl.org/dc/terms/'}
DCT = 'http://purl.org/dc/terms/'

@dataclass
class Agent(Identity):
    pass

@dataclass
class Dataset(Identity):
    issued: Optional[str] = field(default=None, metadata={'type': 'Attribute', 'namespace': DCT})
    creator: Optional[Agent] = field(default=None, metadata={'type': 'Association', 'namespace': DCT})
    Agent: Optional[Agent] = field(default=None, metadata={'type': 'Association', 'namespace': NAMESPACES['gad']})
"""


def test_w3c_properties_are_terms_by_bare_name(monkeypatch):
    profile = types.ModuleType('w3c_profile')
    monkeypatch.setitem(sys.modules, profile.__name__, profile)
    exec(W3C_PROFILE, profile.__dict__)
    context = build_context(profile)['@context']
    assert context['dct:creator'] == {'@type': '@id'}
    assert context['dct:issued'] == {'@type': 'xsd:dateTime'}          # HEADER_TERMS types the literal
    assert context['gad:Dataset.Agent'] == {'@type': '@id'}            # other namespaces stay Class.property
    assert not [term for term in context if 'Dataset.issued' in term or 'Dataset.creator' in term]


def test_part_profile_names():
    assert part_profile('cimprofiles.cim18.cim18v17.connectivity_unbalanced.connectivity_unbalanced') \
        == 'cim18v17.connectivity_unbalanced'
    with pytest.raises(ValueError, match='not in a known profile package'):
        part_profile('elsewhere.part.part')


def test_shared_parts_are_built_once_and_first():
    releases = [{'name': 'a', 'parts': ['cimprofiles.cim17.cimhub_2023.x.x', 'cimprofiles.cim17.cimhub_2023.y.y']},
                {'name': 'b', 'parts': ['cimprofiles.cim17.cimhub_2023.y.y']}]
    specs = expand_parts([{'profile': 'a', 'parts': True}, {'profile': 'b', 'parts': True},
                          {'profile': 'c'}], releases)
    assert [spec['profile'] for spec in specs] == ['cimhub_2023.x', 'cimhub_2023.y', 'a', 'b', 'c']
    assert specs[3]['parts'] == ['cimhub_2023.y']
    with pytest.raises(ValueError, match='not a release'):
        expand_parts([{'profile': 'c', 'parts': True}], releases)


@pytest.mark.parametrize('installed, stable', [('0.2.0', '0.2.0'), ('0.2.0a3', '0.2.0'), ('1.10.2rc1', '1.10.2')])
def test_stable_version_drops_the_prerelease(monkeypatch, installed, stable):
    monkeypatch.setattr('importlib.metadata.version', lambda name: installed)
    assert stable_version() == stable


def test_documents_freeze_at_their_stable_release(tmp_path, monkeypatch):
    """Alphas rebuild a release's documents in place; a released version's are frozen, and a
    profile gets a new version directory only when its documents change."""
    monkeypatch.setitem(PROFILE_PACKAGES, 'test_a', 'fixture_profiles.cim17.test_a')
    spec = tmp_path / 'test_a.yaml'
    output = tmp_path / 'site'

    def run(version, voltage_unit):
        spec.write_text(f'profile: test_a\ndefault: si\nconventions:\n'
                        f'  si: {{quantity_kinds: {{Voltage: {voltage_unit}}}}}\n')
        monkeypatch.setattr(build, 'stable_version', lambda: version)
        build.main([str(spec), '--output', str(output)])
        return json.loads((output / 'profiles.json').read_text())['test_a']['version']

    def voltage_unit(version):
        vocabulary = json.loads((output / f'test_a/{version}/units-si.jsonld').read_text())
        return vocabulary_units(vocabulary, context_prefixes(vocabulary))['BaseVoltage.nominalVoltage']

    assert run('9.0.0', 'V') == '9.0.0'
    assert run('9.0.0', 'kV') == '9.0.0'                        # an alpha rebuild, in place
    assert voltage_unit('9.0.0') == 'kV'
    assert run('9.0.1', 'kV') == '9.0.0'                        # unchanged: still 9.0.0
    assert not (output / 'test_a/9.0.1').exists()
    assert run('9.0.1', 'MV') == '9.0.1'                        # changed: a new directory
    assert voltage_unit('9.0.0') == 'kV' and voltage_unit('9.0.1') == 'MV'

    monkeypatch.setattr(build, 'CACHE_DIR', output)             # the shipped cache
    monkeypatch.setattr(build, '_released', lambda version: True)
    assert run('9.0.1', 'MV') == '9.0.1'                        # unchanged: nothing to freeze
    with pytest.raises(SystemExit, match='9.0.1 is released'):
        run('9.0.1', 'V')


def test_a_release_context_is_the_union_of_its_parts_contexts(monkeypatch):
    """The CIMTool contexts of the parts, merged; a part without one fails."""
    parts = [f'fixture_profiles.cim17.{name}.{name}' for name in ('test_a', 'test_b', 'test_c')]
    monkeypatch.setattr(build, '_releases', lambda: [{'name': 'fixture_abc', 'parts': parts}])
    context = build.profile_context('fixture_abc', None)['@context']
    for name in ('test_a', 'test_b', 'test_c'):
        part = json.loads((FIXTURES / name / 'context.jsonld').read_text())['@context']
        assert part.items() <= context.items()
    assert context['cim:GeneratingUnit.startupCost'] == {'@type': 'xsd:decimal'}     # Money
    assert context['nc:EnergyConsumer.participationFactor'] == {'@type': 'xsd:float'}

    without_context = 'fixture_profiles.cim17.module'            # in a package with no context.jsonld
    monkeypatch.setattr(build, '_releases', lambda: [{'name': 'fixture_abc', 'parts': parts + [without_context]}])
    with pytest.raises(ValueError, match='parts without a CIMTool context.jsonld'):
        build.profile_context('fixture_abc', None)


def test_vocabulary_units_of_the_cim_datatypes():
    """KiloActivePower keeps its kW, PerCent is qudt PERCENT, and dimensionless PU and Money
    carry no unit."""
    from fixture_profiles.cim17 import test_b, test_c

    def units(profile, convention):
        vocabulary = build_vocabulary(profile, convention, 'https://example.org/units', 'test')
        return vocabulary_units(vocabulary, context_prefixes(vocabulary))

    units_b = units(test_b, {})
    units_c = units(test_c, {'properties': {'WireInfo.radius': 'mm'}})
    assert units_b['EnergyConsumer.pfixed'] == 'W'
    assert units_b['EnergyConsumer.maxEconomicP'] == 'W'                # an NC extension property
    assert units_b['EnergyConsumer.pfixedPct'] == 'none'               # qudt PERCENT
    assert units_c['ShortCircuitTest.loss'] == 'kW'
    assert units_c['WireInfo.radius'] == 'mm' and units_c['WireInfo.gmr'] == 'm'
    assert 'GeneratingUnit.governorMPL' not in units_c and 'GeneratingUnit.startupCost' not in units_c
