#!/usr/bin/env bash
# Rebuild one merged profile release from its CIMTool output: re-import every part
# listed in src/cimprofiles/merge_releases.yaml from the release's `source` folder,
# remove duplicate fields, rebuild the merged packages and JSON-LD documents, and run the tests.
#
# usage: scripts/build_release.sh <release name>      e.g. scripts/build_release.sh cim18v17
#
# A part cimprofiles.<cim version>.<package path>.<module> is imported from
# <source>/<stem>.cimantic-graphs.py and <source>/<stem>.__init__.py, where <stem> is
# <module>, or <source_prefix><Module> (CamelCase) when the release sets a source_prefix.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $0 <release name>" >&2
    exit 1
fi
release=$1
repo="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo"

# One line per part: <cim version> <package path> <module> <stem>, after a first line with the source
plan=$(uv run python - "$release" <<'EOF'
import sys
from cimprofiles.build_merged_profiles import _CONFIG, _load_config

name = sys.argv[1]
release = next((r for r in _load_config(_CONFIG) if r['name'] == name), None)
if release is None:
    sys.exit(f"error: no release named {name!r} in {_CONFIG}")
if 'source' not in release:
    sys.exit(f"error: release {name!r} has no 'source' folder in {_CONFIG}")
print(release['source'])
prefix = release.get('source_prefix')
for part in release['parts']:
    _root, cim_version, *package, module = part.split('.')
    if prefix is None:
        stem = module
    else:
        stem = prefix + ''.join(word.capitalize() for word in module.split('_'))
    print(cim_version, '/'.join(package), module, stem)
EOF
)

source_dir=$(head -1 <<< "$plan")
# Check every part was generated before importing any of them
missing=0
while read -r cim_version package module stem; do
    for file in "$source_dir/$stem.cimantic-graphs.py" "$source_dir/$stem.__init__.py"; do
        if [ ! -f "$file" ]; then
            echo "error: $file not found; run the cimantic-graphs builders in CIMTool" >&2
            missing=1
        fi
    done
done < <(tail -n +2 <<< "$plan")
[ "$missing" -eq 0 ] || exit 1

while read -r cim_version package module stem; do
    scripts/import_cimtool_output.sh "$cim_version" "$source_dir/$stem.cimantic-graphs.py" \
        "$source_dir/$stem.__init__.py" "$package" "$module" | sed -n 1p  # sed reads to the end; head would SIGPIPE the import
done < <(tail -n +2 <<< "$plan")

uv run python -m cimprofiles.dedupe_profile_fields --log dedupe_profile_fields.log
# Every release and JSON-LD set: other releases share these parts (cim18v17 and its
# distribution and transmission flavors), and unchanged ones rebuild to the same files
uv run python -m cimprofiles.build_merged_profiles
uv run python -m cimprofiles.jsonld.build
uv run pytest -q tests
