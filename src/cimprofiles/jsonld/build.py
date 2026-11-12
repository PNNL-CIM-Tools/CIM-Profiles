"""Build a profile's JSON-LD context and unit vocabularies from its generated classes.

- Context: the dcat:Dataset header terms (HEADER_TERMS), then one term definition per
  property, from the field metadata. Associations and enumerations are
  ``{"@type": "@id"}``; CIMUnit and float are ``xsd:float``; int and bool are
  ``xsd:integer`` / ``xsd:boolean``; strings are left to the JSON-LD default.
  The published file also names itself (``@id``, its URL) and the stable cim-profiles
  release it was built for (``owl:versionInfo``, as the CGMES vocabularies do); JSON-LD
  processors use only the ``@context`` entry of a remote context, so these are ignored there.
- Unit vocabulary: one ``qudt:hasUnit`` node per unit-bearing property. Units come from a
  convention, resolved per property in order:
  ``properties`` override ('WireInfo.radius': 'mm') -> ``quantity_kinds`` default
  ('ActivePower': 'kW') -> the CIMUnit class's own unit (base SI).
  Dimensionless units other than PerCent are omitted (nothing to convert).

Conventions are YAML files in ``jsonld/conventions/<profile>.yaml`` (see those files).
Build them into ``jsonld/cache/<profile>/<version>/`` (also the GitHub Pages content), where
version is the stable cim-profiles release (``stable_version``), with::

    uv run python -m cimprofiles.jsonld.build                 # every profile
    uv run python -m cimprofiles.jsonld.build cimhub_2023     # one profile
    uv run python -m cimprofiles.jsonld.build my.yaml --base-url https://example.org/cim/ --output site

The functions above main() are pure; main() does the file I/O.
Earlier versions' documents stay in the cache: files written with them still name them.
Once a version is released its documents must not change; bump the release target in
pyproject.toml before rebuilding changed documents.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import re
import sys
from enum import Enum
from pathlib import Path

from pint.errors import DimensionalityError

from cimprofiles import profile_module
from cimprofiles.identity import Identity
from cimprofiles.jsonld.qudt import QUDT_UNIT_NAMESPACE, qudt_name
from cimprofiles.merge import merge_namespaces
from cimprofiles.units import CIMUnit, class_unit
from cimprofiles.units.units import ureg

DOCUMENT_NAMESPACES = {
    'dcat': 'http://www.w3.org/ns/dcat#',
    'dct': 'http://purl.org/dc/terms/',
    'md': 'http://iec.ch/TC57/61970-552/ModelDescription/1#',
    'owl': 'http://www.w3.org/2002/07/owl#',
    'xsd': 'http://www.w3.org/2001/XMLSchema#',
}
# The dcat:Dataset header terms of IEC 61970-552 ed3 and the ENTSO-E metadata specification,
# typed as in the Inst4CIM CGMES context (their md:FullModel counterparts in comments)
HEADER_TERMS = {
    'dct:conformsTo': {'@type': '@id'},                 # md:Model.profile
    'dct:issued': {'@type': 'xsd:dateTime'},            # md:Model.created
    'dct:references': {'@type': '@id'},                 # md:Model.DependentOn
    'dct:requires': {'@type': '@id'},                   # md:Model.DependentOn
    'dct:replaces': {'@type': '@id'},                   # md:Model.Supersedes
    'dcat:isVersionOf': {'@type': '@id'},               # md:Model.modelingAuthoritySet
    'dcat:startDate': {'@type': 'xsd:dateTimeStamp'},   # md:Model.scenarioTime
    'dcat:endDate': {'@type': 'xsd:dateTimeStamp'},
}
VOCABULARY_NAMESPACES = {
    'dct': 'http://purl.org/dc/terms/',
    'owl': 'http://www.w3.org/2002/07/owl#',
    'qudt': 'http://qudt.org/schema/qudt/',
    'unit': QUDT_UNIT_NAMESPACE,
}
_TYPE_NAME = re.compile(r'[A-Za-z_]\w*')
PAGES_URL = 'https://pnnl-cim-tools.github.io/CIM-Profiles/'


def stable_version() -> str:
    """The stable release of the installed cim-profiles: '0.2.0' for 0.2.0 and its alphas 0.2.0aN."""
    return re.match(r'\d+\.\d+\.\d+', importlib.metadata.version('cim-profiles')).group()


def profile_classes(profile) -> list[type]:
    """The CIM object classes a profile module exports (not the Identity base or CIMUnit
    datatypes), sorted by name."""
    return sorted((value for value in vars(profile).values()
                   if isinstance(value, type) and hasattr(value, '__dataclass_fields__')
                   and value.__module__ != Identity.__module__ and not issubclass(value, CIMUnit)),
                  key=lambda cls: cls.__name__)


def profile_namespace_map(profile) -> dict[str, str]:
    """The {prefix: namespace} map of the modules that define a profile's classes."""
    modules = {sys.modules[cls.__module__] for cls in profile_classes(profile)}
    return merge_namespaces(*(module.NAMESPACES for module in sorted(modules, key=lambda m: m.__name__)))


def _prefix(namespaces: dict[str, str], namespace: str) -> str:
    for prefix, uri in namespaces.items():
        if uri == namespace:
            return prefix
    raise KeyError(f'Namespace {namespace} has no prefix in the profile NAMESPACES')


def _declared_fields(profile):
    """(class, attribute, field) for each attribute, on the class that declares it."""
    for cls in profile_classes(profile):
        for attribute in cls.__annotations__:
            if attribute != 'identifier' and attribute in cls.__dataclass_fields__:
                yield cls, attribute, cls.__dataclass_fields__[attribute]


def _named_type(profile, field, base: type) -> type | None:
    """The profile class of type `base` (CIMUnit or Enum) named in a field's type string."""
    for name in _TYPE_NAME.findall(str(field.type)):
        candidate = getattr(profile, name, None)
        if isinstance(candidate, type) and issubclass(candidate, base) and candidate is not base:
            return candidate
    return None


def _datatype(profile, field) -> str | None:
    """The JSON-LD @type of a field, or None for a plain string."""
    if field.metadata['type'] == 'Association' or _named_type(profile, field, Enum):
        return '@id'
    names = set(_TYPE_NAME.findall(str(field.type)))
    if _named_type(profile, field, CIMUnit) or 'float' in names:
        return 'xsd:float'
    if 'int' in names:
        return 'xsd:integer'
    if 'bool' in names:
        return 'xsd:boolean'
    return None


def build_context(profile) -> dict:
    """The JSON-LD context document of a profile module."""
    namespaces = profile_namespace_map(profile)
    context = {**namespaces, **DOCUMENT_NAMESPACES, **HEADER_TERMS}
    for cls, attribute, field in _declared_fields(profile):
        datatype = _datatype(profile, field)
        if datatype is not None:
            term = f'{_prefix(namespaces, field.metadata["namespace"])}:{cls.__name__}.{attribute}'
            context[term] = {'@type': datatype}
    return {'@context': context}


def _checked_unit(name: str, unit: str, unit_class: type) -> str:
    try:
        ureg.Quantity(1, unit).to(class_unit(unit_class))
    except DimensionalityError:
        raise ValueError(f'{name}: {unit!r} is not a unit of {unit_class.__name__} '
                         f'({class_unit(unit_class)})') from None
    return unit


def convention_units(profile, convention: dict) -> dict[str, tuple[str, type]]:
    """{'Class.attribute': (pint unit, CIMUnit class)} for every unit-bearing property,
    with the convention's overrides applied and checked against the profile."""
    quantity_kinds = convention.get('quantity_kinds') or {}
    overrides = dict(convention.get('properties') or {})
    for kind in quantity_kinds:
        if not (isinstance(getattr(profile, kind, None), type) and issubclass(getattr(profile, kind), CIMUnit)):
            raise ValueError(f'Quantity kind {kind!r} is not a CIMUnit class of the profile')

    units = {}
    for cls, attribute, field in _declared_fields(profile):
        unit_class = _named_type(profile, field, CIMUnit)
        if unit_class is None:
            continue
        name = f'{cls.__name__}.{attribute}'
        unit = overrides.pop(name, None) or quantity_kinds.get(unit_class.__name__) or class_unit(unit_class)
        units[name] = (_checked_unit(name, unit, unit_class), unit_class)
    if overrides:
        raise ValueError(f'Override properties not in the profile or not unit-bearing: {sorted(overrides)}')
    return units


def build_vocabulary(profile, convention: dict, vocabulary_iri: str, title: str) -> dict:
    """The unit vocabulary document of a profile under a convention, identified by vocabulary_iri."""
    namespaces = profile_namespace_map(profile)
    field_namespaces = {f'{cls.__name__}.{attribute}': field.metadata['namespace']
                        for cls, attribute, field in _declared_fields(profile)}
    graph = [{'@id': vocabulary_iri, '@type': 'owl:Ontology',
              'owl:versionIRI': {'@id': vocabulary_iri}, 'dct:title': title}]
    for name, (unit, unit_class) in sorted(convention_units(profile, convention).items()):
        if unit_class.__name__ == 'PerCent':
            unit_name = 'PERCENT'
        elif unit == 'none':
            continue
        else:
            unit_name = qudt_name(unit)
        graph.append({'@id': f'{_prefix(namespaces, field_namespaces[name])}:{name}',
                      'qudt:hasUnit': f'unit:{unit_name}',
                      'qudt:hasQuantityKind': f'cim:{unit_class.__name__}'})
    return {'@context': {**namespaces, **VOCABULARY_NAMESPACES}, '@graph': graph}


def build_profile(spec: dict, version: str, base_url: str = PAGES_URL) -> tuple[dict[str, dict], dict]:
    """
    Build the documents of one convention spec (a parsed conventions YAML) for the
    cim-profiles release `version`. Generated documents are published under
    ``<profile>/<version>/`` (the CGMES style of a version in the IRI), so a file keeps
    naming the documents it was written with; the context also records the version
    (``owl:versionInfo``).

    Returns ({relative path: document}, manifest entry). The manifest entry is
    {'context': url, 'default': name, 'conventions': {name: [vocabulary IRIs]}}, plus the
    'version' when documents are generated. A spec may name a published `context` and
    per-convention `vocabularies` instead of generating them.
    """
    name = spec['profile']
    profile = importlib.import_module(profile_module(name))
    directory = f'{name}/{version}/'
    documents = {}
    context_url = spec.get('context')
    if context_url is None:
        context_url = f'{base_url}{directory}context.jsonld'
        documents[f'{directory}context.jsonld'] = {**build_context(profile), '@id': context_url,
                                                   'owl:versionInfo': version}
    conventions = {}
    for convention_name, convention in spec['conventions'].items():
        if 'vocabularies' in convention:
            conventions[convention_name] = list(convention['vocabularies'])
            continue
        path = f'{directory}units-{convention_name}.jsonld'
        documents[path] = build_vocabulary(profile, convention, base_url + path,
                                           f'{name} {version} JSON-LD units: {convention_name}')
        conventions[convention_name] = [base_url + path]
    if spec['default'] not in conventions:
        raise ValueError(f'{name}: default convention {spec["default"]!r} is not one of {sorted(conventions)}')
    entry = {'context': context_url, 'default': spec['default'], 'conventions': conventions}
    if documents:
        entry['version'] = version
    return documents, entry


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> None:
    import yaml  # build-time (dev) dependency only

    conventions_dir = Path(__file__).parent / 'conventions'
    parser = argparse.ArgumentParser(description='Build JSON-LD contexts and unit vocabularies')
    parser.add_argument('specs', nargs='*', help='profile names or conventions YAML paths (default: all)')
    parser.add_argument('--base-url', default=PAGES_URL, help='URL the output directory is published at')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'cache')
    args = parser.parse_args(argv)
    base_url = args.base_url if args.base_url.endswith('/') else args.base_url + '/'

    paths = [Path(spec) if spec.endswith('.yaml') else conventions_dir / f'{spec}.yaml' for spec in args.specs]
    index = _read_json(args.output / 'index.json')
    manifest = _read_json(args.output / 'profiles.json')
    for path in paths or sorted(conventions_dir.glob('*.yaml')):
        spec = yaml.safe_load(path.read_text(encoding='utf-8'))
        documents, entry = build_profile(spec, stable_version(), base_url)
        for relative_path, document in documents.items():
            _write_json(args.output / relative_path, document)
            index[base_url + relative_path] = relative_path
        manifest[spec['profile']] = entry
        print(f'{spec["profile"]}: {len(documents)} documents')

    # Every document the manifest names must resolve offline
    for profile, entry in manifest.items():
        iris = [entry['context']] + [iri for iris in entry['conventions'].values() for iri in iris]
        missing = [iri for iri in iris if iri not in index]
        if missing:
            raise SystemExit(f'error: {profile} names documents not in {args.output}/index.json: {missing}')
    _write_json(args.output / 'index.json', dict(sorted(index.items())))
    _write_json(args.output / 'profiles.json', dict(sorted(manifest.items())))


if __name__ == '__main__':
    main()
