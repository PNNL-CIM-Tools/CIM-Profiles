# CGMES-CIM17 (vendored)

The CIMTool workspace for the CGMES CIM17 profiles, copied from the UCAIug repository
<https://github.com/cimug-org/CGMES-CIM17>. It is distributed under the Apache 2.0 license; see [LICENSE](LICENSE).

| | |
|---|---|
| Upstream | <https://github.com/cimug-org/CGMES-CIM17> |
| Commit | [`1c7708f5d3bd`](https://github.com/cimug-org/CGMES-CIM17/tree/1c7708f5d3bde53e154201707f31961573868cf2) (2026-06-23) |

## Local changes

The only change from upstream is that the cimantic-graphs Python builders
(`__init__.py` and `cimantic-graphs.py`, see [`CIMTool_plugin/`](../CIMTool_plugin)) are
enabled in every `Profiles/*.owl`, by `scripts/enable_python_builders.py`.

Report problems with the profiles themselves upstream, at <https://github.com/cimug-org/CGMES-CIM17/issues>.

## Updating

To pick up a new upstream version, run

```bash
scripts/sync_cgmes.sh 17 [git ref]
```

which replaces this folder with the upstream copy, enables the Python builders again and
rewrites this README. Any other change committed here is overwritten by the next sync, so
contribute profile fixes upstream instead.
