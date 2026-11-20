"""Turn on the cimantic-graphs Python builders in CIMTool profiles.

CIMTool records the builders enabled for a profile as Buildlet flags in the profile's .owl
file. This adds the flags for the two cimantic-graphs builders (see CIMTool_plugin/) to each
file given, just before the closing </rdf:RDF>. Flags already present are left alone, so the
script can be run again after every upstream sync.

usage: python scripts/enable_python_builders.py <profile.owl> [<profile.owl> ...]
"""
import sys
from pathlib import Path

PYTHON_BUILDERS = ('__init__.py', 'cimantic-graphs.py')
BUILDLET_FLAG = (
    '  <rdf:Description rdf:about="http://langdale.com.au/2007/Buildlet#{builder}">\n'
    '    <rdf:type rdf:resource="http://langdale.com.au/2005/Message#Flag"/>\n'
    '  </rdf:Description>\n'
)
CLOSING_TAG = '</rdf:RDF>'


def enable_python_builders(owl_text: str) -> str:
    """Return owl_text with a Buildlet flag for every Python builder not already enabled."""
    if CLOSING_TAG not in owl_text:
        raise ValueError(f'no {CLOSING_TAG} closing tag; is this a CIMTool profile .owl file?')
    missing_flags = ''
    for builder in PYTHON_BUILDERS:
        if f'Buildlet#{builder}"' not in owl_text:
            missing_flags += BUILDLET_FLAG.format(builder=builder)
    head, tail = owl_text.rsplit(CLOSING_TAG, 1)
    return head + missing_flags + CLOSING_TAG + tail


def main(owl_paths: list[str]) -> None:
    if not owl_paths:
        sys.exit(__doc__)
    for owl_path in map(Path, owl_paths):
        owl_text = owl_path.read_text(encoding='utf-8')
        try:
            updated = enable_python_builders(owl_text)
        except ValueError as error:
            sys.exit(f'error: {owl_path}: {error}')
        if updated == owl_text:
            print(f'{owl_path}: Python builders already enabled')
        else:
            owl_path.write_text(updated, encoding='utf-8')
            print(f'{owl_path}: enabled Python builders')


if __name__ == '__main__':
    main(sys.argv[1:])
