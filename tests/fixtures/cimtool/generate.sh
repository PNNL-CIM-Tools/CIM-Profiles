#!/usr/bin/env bash
# Regenerate the test fixture profiles from their committed .owl files: run the cimantic-graphs
# builders on Profiles/test_*.owl with the CIMTool CLI, then import the outputs into
# tests/fixture_profiles/cim17/ like scripts/import_cimtool_output.sh imports a real profile.
#
# Run it after changing a builder (CIMTool_plugin/*.xsl or the JSON-LD context builder) or the
# import pipeline, and commit what changes. With --owl it first rebuilds the .owl files from
# BuildFixtures.java; do that only to change what the fixtures cover (see tests/fixtures/README.md).
#
# usage: tests/fixtures/cimtool/generate.sh [--owl]
#
# Needs Java 11+ and, unless the defaults below match your checkouts:
#   CIMTOOL_CLI           the CIMTool CLI fat jar (cimtool-cli.jar, CIMTool 2.3.1)
#   CIMTOOL_BUILDERS_LIB  a CIMTool-Builders-Library checkout: its CIMTool-Test-Project holds
#                         the schema, its custom-builders the JSON-LD context builder
set -euo pipefail

if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--owl" ]; }; then
    echo "usage: $0 [--owl]" >&2
    exit 1
fi
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
cli=${CIMTOOL_CLI:-$HOME/variable-fidelity-models/cimtool-cli.jar}
builders_lib=${CIMTOOL_BUILDERS_LIB:-$HOME/CIMTool-Builders-Library}
project="$builders_lib/builder-submissions/CIMTool-Test-Project"
schema="$project/Schema/CIM17-2_CGMES31v01_PROF-20v02_NC23v66_MS10v01_DES10v01.qea"
jsonld_xsl="$builders_lib/custom-builders/cimantic-graphs-jsonld-context/cimantic-graphs-jsonld-context.xsl"
for file in "$cli" "$schema" "$jsonld_xsl"; do
    if [ ! -f "$file" ]; then
        echo "error: $file not found; set CIMTOOL_CLI / CIMTOOL_BUILDERS_LIB" >&2
        exit 1
    fi
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
javac -nowarn -cp "$cli" -d "$work/classes" "$here/BuildFixtures.java" "$here/GenerateOutputs.java" 2>&1 \
    | { grep -v '^Note:' || true; }
# CIMTool logs schema warnings by the hundred; keep them out of the way
log="$work/cimtool.log"
run_java() {
    java -cp "$cli:$work/classes" "$@" 2>>"$log" || { tail -20 "$log" >&2; exit 1; }
}

if [ $# -eq 1 ]; then
    mkdir -p "$here/Profiles"
    run_java BuildFixtures "$project" "$schema" "$here/Profiles"
    uv run --project "$repo" python "$repo/scripts/enable_python_builders.py" "$here"/Profiles/test_*.owl
fi

# The builders by name, so CIMTool post-processes the TEXT ones as it does in Eclipse
mkdir "$work/builders"
cp "$repo/CIMTool_plugin/cimantic-graphs.xsl" "$repo/CIMTool_plugin/cimantic-graphs-init.xsl" "$jsonld_xsl" \
    "$work/builders/"
cat > "$work/builders/builders.json" <<'EOF'
{
  "cimantic-graphs": {"type": "TEXT", "style": "cimantic-graphs", "ext": "cimantic-graphs.py"},
  "cimantic-graphs-init": {"type": "TEXT", "style": "cimantic-graphs-init", "ext": "__init__.py"},
  "cimantic-graphs-jsonld-context": {"type": "TRANSFORM", "style": "cimantic-graphs-jsonld-context", "ext": "context.jsonld"}
}
EOF
run_java GenerateOutputs "$project" "$schema" "$work/builders" "$here/Profiles" "$here"/Profiles/test_*.owl

rm -rf "$repo/tests/fixture_profiles/cim17"
for owl in "$here"/Profiles/test_*.owl; do
    name=$(basename "$owl" .owl)
    IMPORT_ROOT="$repo/tests/fixture_profiles" IMPORT_PACKAGE=fixture_profiles \
        "$repo/scripts/import_cimtool_output.sh" cim17 "$here/Profiles/$name.cimantic-graphs.py" \
        "$here/Profiles/$name.__init__.py" | sed -n 1p
done
touch "$repo/tests/fixture_profiles/cim17/__init__.py"
uv run --project "$repo" python -m cimprofiles.dedupe_profile_fields "$repo/tests/fixture_profiles/cim17" \
    --log "$work/dedupe.log"
