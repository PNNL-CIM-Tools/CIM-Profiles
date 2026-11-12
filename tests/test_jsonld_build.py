import importlib
import json

import pytest
import yaml

import cimprofiles.cim17.cimhub_2023 as cimhub
from cimprofiles import PROFILE_PACKAGES
from cimprofiles.jsonld import load_document, load_vocabulary_units, profile_jsonld
from cimprofiles.jsonld.build import (build_context, build_profile, build_vocabulary, convention_units,
                                      stable_version)
from cimprofiles.jsonld.context import (context_prefixes, property_datatypes, vocabulary_iri,
                                        vocabulary_units)
from cimprofiles.jsonld.documents import CACHE

CONVENTIONS = CACHE.joinpath('..', 'conventions')


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


def test_cgmes_context_matches_the_published_cgmes_context():
    cgmes = importlib.import_module(PROFILE_PACKAGES['cgmes_3_0_0'])
    ours = property_datatypes(build_context(cgmes))
    published = property_datatypes(load_document(profile_jsonld('cgmes_3_0_0')['context']))
    differ = {name for name in set(ours) & set(published) if ours[name] != published[name]}
    # Money is xsd:decimal in CGMES; generated profiles type it as float
    assert differ == {'GeneratingUnit.variableCost', 'GeneratingUnit.startupCost'}


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


def test_every_profile_resolves_offline():
    for profile in json.loads(CACHE.joinpath('profiles.json').read_text()):
        entry = profile_jsonld(profile)
        load_document(entry['context'])
        assert entry['default'] in entry['conventions']
        for iris in entry['conventions'].values():
            for iri in iris:
                load_vocabulary_units(iri)


def test_profile_lookup_by_package_name():
    assert profile_jsonld('cimprofiles.cim17.cimhub_2023') == profile_jsonld('cimhub_2023')
    with pytest.raises(KeyError, match='cimhub_2099'):
        profile_jsonld('cimhub_2099')


def test_cgmes_default_units_are_transmission_units():
    units = {}
    for iri in profile_jsonld('cgmes_3_0_0')['conventions']['cgmes']:
        units.update(load_vocabulary_units(iri))
    assert units['BaseVoltage.nominalVoltage'] == 'kV'
    assert units['EnergyConsumer.p'] == 'MW'


@pytest.mark.parametrize('spec_file', sorted(p.name for p in CONVENTIONS.iterdir() if p.name.endswith('.yaml')))
def test_cache_is_up_to_date(spec_file):
    spec = yaml.safe_load(CONVENTIONS.joinpath(spec_file).read_text())
    # The cached version, not the installed one: a profile keeps the release that last
    # changed its documents
    version = profile_jsonld(spec['profile']).get('version', stable_version())
    documents, entry = build_profile(spec, version)
    for path, document in documents.items():
        assert json.loads(CACHE.joinpath(path).read_text()) == document, \
            f'{path} is stale: run python -m cimprofiles.jsonld.build {spec["profile"]}'
    assert profile_jsonld(spec['profile']) == entry


def test_documents_are_versioned_in_their_url():
    """A generated context names its stable release in its URL and in owl:versionInfo."""
    entry = profile_jsonld('cimhub_2023')
    directory = f'https://pnnl-cim-tools.github.io/CIM-Profiles/cimhub_2023/{entry["version"]}/'
    assert entry['context'] == directory + 'context.jsonld'
    context = load_document(entry['context'])
    assert context['@id'] == entry['context']
    assert context['owl:versionInfo'] == entry['version']
    assert all(iri.startswith(directory) for iris in entry['conventions'].values() for iri in iris)


@pytest.mark.parametrize('installed, stable', [('0.2.0', '0.2.0'), ('0.2.0a3', '0.2.0'), ('1.10.2rc1', '1.10.2')])
def test_stable_version_drops_the_prerelease(monkeypatch, installed, stable):
    monkeypatch.setattr('importlib.metadata.version', lambda name: installed)
    assert stable_version() == stable


def test_documents_freeze_at_their_stable_release(tmp_path, monkeypatch):
    """Alphas rebuild a release's documents in place; a released version's are frozen, and a
    profile gets a new version directory only when its documents change."""
    from cimprofiles.jsonld import build

    def run(version):
        monkeypatch.setattr(build, 'stable_version', lambda: version)
        build.main(['cim18gmdm', '--output', str(tmp_path)])
        return json.loads((tmp_path / 'profiles.json').read_text())['cim18gmdm']['version']

    assert run('9.0.0') == '9.0.0'
    monkeypatch.setitem(build.HEADER_TERMS, 'dct:alpha', {'@type': '@id'})
    assert run('9.0.0') == '9.0.0'                              # an alpha rebuild, in place
    assert 'dct:alpha' in json.loads((tmp_path / 'cim18gmdm/9.0.0/context.jsonld').read_text())['@context']
    assert run('9.0.1') == '9.0.0'                              # unchanged: still 9.0.0
    assert not (tmp_path / 'cim18gmdm/9.0.1').exists()
    monkeypatch.setitem(build.HEADER_TERMS, 'dct:fix', {'@type': '@id'})
    assert run('9.0.1') == '9.0.1'                              # changed: a new directory
    assert (tmp_path / 'cim18gmdm/9.0.0/context.jsonld').exists()

    monkeypatch.setattr(build, 'CACHE_DIR', tmp_path)          # the shipped cache
    monkeypatch.setattr(build, '_released', lambda version: True)
    assert run('9.0.1') == '9.0.1'                              # unchanged: nothing to freeze
    monkeypatch.setitem(build.HEADER_TERMS, 'dct:late', {'@type': '@id'})
    with pytest.raises(SystemExit, match='9.0.1 is released'):
        run('9.0.1')
