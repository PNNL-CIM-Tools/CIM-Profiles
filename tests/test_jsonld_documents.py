import io
import json
from unittest import mock

import pytest

from cimprofiles.jsonld import document_prefixes, load_document, load_vocabulary_units
from cimprofiles.jsonld.context import (context_prefixes, expand, property_datatypes,
                                        vocabulary_iri, vocabulary_units)
from cimprofiles.jsonld.documents import cache_index
from cimprofiles.jsonld.qudt import pint_unit, qudt_name

EQ_IRI = 'http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0'
NEW_CONTEXT = 'https://raw.githack.com/Sveino/Inst4CIM-KG/develop/rdf-improved/cim-context-new.jsonld'

VOCABULARY = {
    '@context': {'cim': 'https://example.org/cim#', 'qudt': 'http://qudt.org/schema/qudt/',
                 'unit': 'http://qudt.org/vocab/unit/', 'owl': 'http://www.w3.org/2002/07/owl#'},
    '@graph': [
        {'@id': 'https://example.org/units', '@type': 'owl:Ontology',
         'owl:versionIRI': {'@id': 'https://example.org/units/1'}},
        {'@id': 'cim:BaseVoltage.nominalVoltage', 'qudt:hasUnit': 'unit:KiloV'},
        {'@id': 'cim:ACLineSegment.r', 'qudt:hasUnit': {'@id': 'http://qudt.org/vocab/unit/OHM'}},
        {'@id': 'cim:IdentifiedObject.name'},
    ],
}


def test_qudt_names_round_trip_and_unknowns_fail():
    assert pint_unit('KiloV') == 'kV'
    assert qudt_name('kV') == 'KiloV'
    assert pint_unit('PERCENT') == 'none'      # CIM PerCent values are already percentages
    assert qudt_name('none') == 'UNITLESS'
    with pytest.raises(KeyError, match='FURLONG'):
        pint_unit('FURLONG')


def test_vocabulary_units_and_iri_from_inline_document():
    prefixes = context_prefixes(VOCABULARY)
    assert vocabulary_units(VOCABULARY, prefixes) == {'BaseVoltage.nominalVoltage': 'kV',
                                                      'ACLineSegment.r': 'ohm'}
    assert vocabulary_iri(VOCABULARY, prefixes) == 'https://example.org/units/1'


def test_conflicting_units_fail():
    document = {'@graph': [
        {'@id': 'https://a.org/ns#X.p', 'http://qudt.org/schema/qudt/hasUnit': 'http://qudt.org/vocab/unit/W'},
        {'@id': 'https://b.org/ns#X.p', 'http://qudt.org/schema/qudt/hasUnit': 'http://qudt.org/vocab/unit/MegaW'},
    ]}
    with pytest.raises(ValueError, match='X.p has two units'):
        vocabulary_units(document, {})


def test_expand_rejects_unknown_prefix():
    assert expand('urn:uuid:1234', {}) == 'urn:uuid:1234'
    with pytest.raises(ValueError, match="prefix 'nope'"):
        expand('nope:Thing', {})


def test_cgmes_equipment_vocabulary_from_cache_by_version_iri():
    units = load_vocabulary_units(EQ_IRI)
    assert units['BaseVoltage.nominalVoltage'] == 'kV'
    assert units['ACLineSegment.r'] == 'ohm'
    assert units['RotatingMachine.ratedS'] == 'MVA'
    assert units['Conductor.length'] == 'km'


def test_instance_context_from_cache():
    context = load_document(NEW_CONTEXT)
    assert document_prefixes(context)['cim'] == 'https://cim.ucaiug.io/ns#'
    datatypes = property_datatypes(context)
    assert datatypes['ACLineSegment.r'] == 'xsd:float'
    assert datatypes['Terminal.ConductingEquipment'] == '@id'


def test_every_index_entry_loads():
    for iri in cache_index():
        assert isinstance(load_document(iri), dict)


def test_uncached_document_needs_opt_in():
    with pytest.raises(LookupError, match='allow_fetch=True'):
        load_document('https://example.org/not-cached.jsonld')


def test_fetch_is_https_only():
    with pytest.raises(ValueError, match='only https'):
        load_document('http://example.org/context.jsonld', allow_fetch=True)


def test_fetch_when_allowed():
    body = json.dumps({'@context': {'ex': 'https://example.org/ns#'}}).encode()
    with mock.patch('urllib.request.urlopen', return_value=io.BytesIO(body)) as urlopen:
        document = load_document('https://example.org/fetched.jsonld', allow_fetch=True)
    assert document['@context']['ex'] == 'https://example.org/ns#'
    assert urlopen.call_args.args[0].get_header('Accept').startswith('application/ld+json')
