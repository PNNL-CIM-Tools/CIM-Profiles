"""Turn on the cimantic-graphs builders in CIMTool profiles.

CIMTool records the builders enabled for a profile as Buildlet flags in the profile's .owl
file. This adds the flags for the cimantic-graphs builders to each
file given, just before the closing </rdf:RDF>. Flags already present are left alone, so the
script can be run again after every upstream sync.

The builders, by the file extension each is imported into CIMTool with: the two Python
builders of CIMTool_plugin/, and the JSON-LD context builder of CIMTool-Builders-Library
(custom-builders/cimantic-graphs-jsonld-context).

usage: python scripts/enable_python_builders.py <profile.owl> [<profile.owl> ...]
"""
import sys
from pathlib import Path

CIMANTIC_GRAPHS_BUILDERS = ('__init__.py', 'cimantic-graphs.py', 'context.jsonld')
BUILDLET_FLAG = (
    '  <rdf:Description rdf:about="http://langdale.com.au/2007/Buildlet#{builder}">\n'
    '    <rdf:type rdf:resource="http://langdale.com.au/2005/Message#Flag"/>\n'
    '  </rdf:Description>\n'
)
CLOSING_TAG = '</rdf:RDF>'


def enable_python_builders(owl_text: str) -> str:
    """Return owl_text with a Buildlet flag for every cimantic-graphs builder not already
    enabled, in the file's own line endings."""
    if CLOSING_TAG not in owl_text:
        raise ValueError(f'no {CLOSING_TAG} closing tag; is this a CIMTool profile .owl file?')
    line_ending = '\r\n' if '\r\n' in owl_text else '\n'
    missing_flags = ''
    for builder in CIMANTIC_GRAPHS_BUILDERS:
        if f'Buildlet#{builder}"' not in owl_text:
            missing_flags += BUILDLET_FLAG.format(builder=builder).replace('\n', line_ending)
    head, tail = owl_text.rsplit(CLOSING_TAG, 1)
    return head + missing_flags + CLOSING_TAG + tail


def main(owl_paths: list[str]) -> None:
    if not owl_paths:
        sys.exit(__doc__)
    for owl_path in map(Path, owl_paths):
        with open(owl_path, encoding='utf-8', newline='') as owl_file:  # keep CRLF line endings
            owl_text = owl_file.read()
        try:
            updated = enable_python_builders(owl_text)
        except ValueError as error:
            sys.exit(f'error: {owl_path}: {error}')
        if updated == owl_text:
            print(f'{owl_path}: cimantic-graphs builders already enabled')
        else:
            with open(owl_path, 'w', encoding='utf-8', newline='') as owl_file:
                owl_file.write(updated)
            print(f'{owl_path}: enabled cimantic-graphs builders')


if __name__ == '__main__':
    main(sys.argv[1:])
