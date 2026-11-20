"""Read JSON-LD contexts and unit vocabularies (pure functions on loaded documents).

A JSON-LD context gives prefixes and each property's datatype (``{"@type": "@id"}``,
``"xsd:float"``). It cannot carry units: JSON-LD 1.1 rejects unknown keys in term
definitions. Units live in the profile vocabulary instead, one node per property:
``{"@id": "cim:BaseVoltage.nominalVoltage", "qudt:hasUnit": "unit:KiloV"}``. A data
file names its vocabulary with ``dct:conformsTo``, which matches the vocabulary's
``owl:versionIRI``.

Properties are keyed by local name ('BaseVoltage.nominalVoltage') so that one
vocabulary serves every CIM namespace revision of the same profile.
"""
from __future__ import annotations

from cimprofiles.jsonld.qudt import QUDT_UNIT_NAMESPACE, pint_unit

OWL_ONTOLOGY = 'http://www.w3.org/2002/07/owl#Ontology'
OWL_VERSION_IRI = 'http://www.w3.org/2002/07/owl#versionIRI'
QUDT_HAS_UNIT = 'http://qudt.org/schema/qudt/hasUnit'


def local_name(iri: str) -> str:
    """The part of an IRI after its last '#' or '/' ('…/ns#ACLineSegment.r' -> 'ACLineSegment.r')."""
    return iri.rsplit('#', 1)[-1] if '#' in iri else iri.rsplit('/', 1)[-1]


def context_definitions(document: dict) -> dict:
    """The term definitions of a context document's inline ``@context`` (lists merged in order).
    Remote contexts (strings) inside it are not resolved here; see documents.document_prefixes."""
    context = document.get('@context', {})
    definitions = {}
    for part in context if isinstance(context, list) else [context]:
        if isinstance(part, dict):
            definitions.update(part)
    return definitions


def remote_contexts(document: dict) -> list[str]:
    """The URLs of remote contexts a document's ``@context`` refers to."""
    context = document.get('@context', [])
    return [part for part in (context if isinstance(context, list) else [context])
            if isinstance(part, str)]


def context_prefixes(document: dict) -> dict[str, str]:
    """The {prefix: namespace IRI} entries of a document's inline ``@context``."""
    return {term: value for term, value in context_definitions(document).items()
            if isinstance(value, str) and not term.startswith('@') and value.endswith(('#', '/'))}


def property_datatypes(document: dict) -> dict[str, str]:
    """The {local property name: '@id' | 'xsd:float' | ...} coercions of a context document."""
    datatypes = {}
    for term, value in context_definitions(document).items():
        if isinstance(value, dict) and '@type' in value:
            datatypes[local_name(term.split(':', 1)[-1])] = value['@type']
    return datatypes


def expand(compact: str, prefixes: dict[str, str]) -> str:
    """Expand a compact IRI ('unit:KiloV') with prefixes; absolute IRIs pass through."""
    prefix, separator, rest = compact.partition(':')
    if separator and prefix in prefixes:
        return prefixes[prefix] + rest
    if '://' in compact or compact.startswith('urn:'):
        return compact
    raise ValueError(f'Cannot expand {compact!r}: prefix {prefix!r} is not defined')


def _iri_value(value, prefixes: dict[str, str]) -> str:
    """An IRI written as a string or as {"@id": ...}, expanded."""
    return expand(value['@id'] if isinstance(value, dict) else value, prefixes)


def _expanded_items(node: dict, prefixes: dict[str, str]):
    """(expanded key, value) pairs of a node, skipping keywords and unexpandable keys."""
    for key, value in node.items():
        if key.startswith('@'):
            continue
        try:
            yield expand(key, prefixes), value
        except ValueError:
            continue  # annotation props from unrelated vocabularies (e.g. 'cims:...') are not needed


def _graph(document: dict) -> list[dict]:
    graph = document.get('@graph', [])
    return graph if isinstance(graph, list) else [graph]


def vocabulary_iri(document: dict, prefixes: dict[str, str]) -> str:
    """The ``owl:versionIRI`` of a vocabulary document's ``owl:Ontology`` node."""
    for node in _graph(document):
        types = node.get('@type', [])
        types = types if isinstance(types, list) else [types]
        if OWL_ONTOLOGY not in [expand(t, prefixes) for t in types]:
            continue
        for key, value in _expanded_items(node, prefixes):
            if key == OWL_VERSION_IRI:
                return _iri_value(value, prefixes)
    raise ValueError('Vocabulary has no owl:Ontology node with an owl:versionIRI')


def vocabulary_units(document: dict, prefixes: dict[str, str]) -> dict[str, str]:
    """The {local property name: pint unit} map of a vocabulary's ``qudt:hasUnit`` nodes,
    e.g. {'BaseVoltage.nominalVoltage': 'kV', 'ACLineSegment.r': 'ohm'}."""
    units = {}
    for node in _graph(document):
        for key, value in _expanded_items(node, prefixes):
            if key != QUDT_HAS_UNIT:
                continue
            unit_iri = _iri_value(value, prefixes)
            if not unit_iri.startswith(QUDT_UNIT_NAMESPACE):
                raise ValueError(f'{node["@id"]} unit {unit_iri} is not a QUDT unit')
            name = local_name(expand(node['@id'], prefixes))
            unit = pint_unit(unit_iri[len(QUDT_UNIT_NAMESPACE):])
            if units.get(name, unit) != unit:
                raise ValueError(f'{name} has two units in one vocabulary: {units[name]} and {unit}')
            units[name] = unit
    return units
