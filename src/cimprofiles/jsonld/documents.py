"""Load JSON-LD contexts and vocabularies by URL or IRI, offline first.

Documents ship with the package in ``jsonld/cache`` and are listed in
``cache/index.json`` as ``{url_or_iri: relative path}``. A vocabulary is listed under
both its published URL and its ``owl:versionIRI`` (what data files name in
``dct:conformsTo``). Anything else is fetched over HTTPS only when the caller opts in
with ``allow_fetch=True``; there is no silent network access.

Loaded documents are memoised per process and shared: treat them as read-only.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from functools import cache
from importlib import resources

from cimprofiles import PROFILE_PACKAGES
from cimprofiles.jsonld.context import context_prefixes, remote_contexts, vocabulary_units

_log = logging.getLogger(__name__)

CACHE = resources.files('cimprofiles.jsonld').joinpath('cache')
FETCH_TIMEOUT_SECONDS = 30
FETCH_MAX_BYTES = 20_000_000


@cache
def cache_index() -> dict[str, str]:
    """The {url_or_iri: cache-relative path} index of shipped documents."""
    return json.loads(CACHE.joinpath('index.json').read_text(encoding='utf-8'))


def _fetch(url: str) -> dict:
    if not url.startswith('https://'):
        raise ValueError(f'Refusing to fetch {url}: only https:// URLs are fetched')
    _log.info(f'Fetching JSON-LD document {url}')
    request = urllib.request.Request(url, headers={'Accept': 'application/ld+json, application/json'})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        content = response.read(FETCH_MAX_BYTES + 1)
    if len(content) > FETCH_MAX_BYTES:
        raise ValueError(f'{url} is larger than {FETCH_MAX_BYTES} bytes')
    return json.loads(content)


@cache
def load_document(iri: str, allow_fetch: bool = False) -> dict:
    """The JSON-LD document at a URL or IRI: from the shipped cache, else fetched if allowed."""
    path = cache_index().get(iri)
    if path is not None:
        return json.loads(CACHE.joinpath(path).read_text(encoding='utf-8'))
    if not allow_fetch:
        raise LookupError(f'{iri} is not in the cimprofiles JSON-LD cache. Allow fetching it '
                          f'(allow_fetch=True; in CIM-Graph CIMG_ALLOW_REMOTE_CONTEXT=true) '
                          f'or add it to cimprofiles/jsonld/cache.')
    return _fetch(iri)


def document_prefixes(document: dict, allow_fetch: bool = False) -> dict[str, str]:
    """All {prefix: namespace} entries of a document's context, remote contexts included.
    Inline entries override remote ones, as later contexts do in JSON-LD."""
    prefixes = {}
    for url in remote_contexts(document):
        prefixes.update(document_prefixes(load_document(url, allow_fetch), allow_fetch))
    prefixes.update(context_prefixes(document))
    return prefixes


def load_vocabulary_units(iri: str, allow_fetch: bool = False) -> dict[str, str]:
    """The {local property name: pint unit} map of the vocabulary at a URL or versionIRI."""
    document = load_document(iri, allow_fetch)
    return vocabulary_units(document, document_prefixes(document, allow_fetch))


@cache
def _profiles_manifest() -> dict[str, dict]:
    return json.loads(CACHE.joinpath('profiles.json').read_text(encoding='utf-8'))


def profile_jsonld(profile: str) -> dict:
    """
    The published JSON-LD documents of a profile, by short name ('cimhub_2023') or
    package ('cimprofiles.cim17.cimhub_2023'):
    {'context': url, 'default': convention name, 'conventions': {name: [vocabulary IRIs]}}.
    """
    short_names = {package: name for name, package in PROFILE_PACKAGES.items()}
    name = short_names.get(profile, profile)
    manifest = _profiles_manifest()
    if name not in manifest:
        raise KeyError(f'Profile {profile!r} has no published JSON-LD documents; '
                       f'known: {", ".join(manifest)}')
    return manifest[name]
