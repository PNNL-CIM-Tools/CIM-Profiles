#!/usr/bin/env bash
# Vendor a CGMES CIMTool workspace from the UCAIug GitHub organisation (cimug-org) into
# CGMES-CIM<version>/, enable the cimantic-graphs Python builders in its profiles, and write
# a README recording the upstream commit it was copied from.
#
# usage: scripts/sync_cgmes.sh <16|17> [git ref]      (ref defaults to master; a commit SHA works)
#
# Files tracked under CGMES-CIM<version>/ are replaced by the upstream copy; untracked
# files there (e.g. CIMTool build output) are kept.
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "usage: $0 <16|17> [git ref]" >&2
    exit 1
fi
case "$1" in
    16|17) ;;
    *) echo "error: CGMES CIM version must be 16 or 17, got '$1'" >&2; exit 1 ;;
esac
name=CGMES-CIM$1
ref=${2:-master}
url=https://github.com/cimug-org/$name
repo="$(cd "$(dirname "$0")/.." && pwd)"
dest="$repo/$name"

if ! git -C "$repo" diff --quiet HEAD -- "$name"; then
    echo "error: $name/ has uncommitted changes; commit or stash them before syncing" >&2
    exit 1
fi

upstream=$(mktemp -d)
trap 'rm -rf "$upstream"' EXIT
git -C "$upstream" init --quiet
git -C "$upstream" fetch --quiet --depth 1 "$url" "$ref"
git -C "$upstream" checkout --quiet FETCH_HEAD
commit=$(git -C "$upstream" rev-parse HEAD)
commit_date=$(git -C "$upstream" log -1 --format=%cs)

# Remove the tracked files first, so files deleted upstream are deleted here too.
git -C "$repo" ls-files -z -- "$name" | (cd "$repo" && xargs -0 rm -f)
mkdir -p "$dest"
cp -r "$upstream/$name/." "$dest/"
cp "$upstream/LICENSE" "$dest/LICENSE"

python3 -I "$repo/scripts/enable_python_builders.py" "$dest"/Profiles/*.owl

cat > "$dest/README.md" <<EOF
# $name (vendored)

The CIMTool workspace for the CGMES CIM$1 profiles, copied from the UCAIug repository
<$url>. It is distributed under the Apache 2.0 license; see [LICENSE](LICENSE).

| | |
|---|---|
| Upstream | <$url> |
| Commit | [\`${commit:0:12}\`]($url/tree/$commit) ($commit_date) |

## Local changes

The only change from upstream is that the cimantic-graphs Python builders
(\`__init__.py\` and \`cimantic-graphs.py\`, see [\`CIMTool_plugin/\`](../CIMTool_plugin)) are
enabled in every \`Profiles/*.owl\`, by \`scripts/enable_python_builders.py\`.

Report problems with the profiles themselves upstream, at <$url/issues>.

## Updating

To pick up a new upstream version, run

\`\`\`bash
scripts/sync_cgmes.sh $1 [git ref]
\`\`\`

which replaces this folder with the upstream copy, enables the Python builders again and
rewrites this README. Any other change committed here is overwritten by the next sync, so
contribute profile fixes upstream instead.
EOF

echo "synced $name/ to $url at $commit"
