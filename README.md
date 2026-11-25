# CIM-Profiles

![GitHub Tag](https://img.shields.io/github/v/tag/PNNL-CIM-Tools/CIM-Profiles)
![GitHub Release Date](https://img.shields.io/github/release-date-pre/PNNL-CIM-Tools/CIM-Profiles)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/PNNL-CIM-Tools/CIM-Profiles/release.yml)
![Libraries.io dependency status for GitHub repo](https://img.shields.io/librariesio/github/PNNL-CIM-Tools/CIM-Profiles)


![PyPI - Version](https://img.shields.io/pypi/v/cim-profiles)
![PyPI - Downloads](https://img.shields.io/pypi/dm/cim-profiles?label=pypi%20downloads)
![PyPI - Format](https://img.shields.io/pypi/format/cim-profiles)


![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/PNNL-CIM-Tools/CIM-Profiles)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr/PNNL-CIM-Tools/CIM-Profiles)
![GitHub commit activity](https://img.shields.io/github/commit-activity/t/PNNL-CIM-Tools/CIM-Profiles)

![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/PNNL-CIM-Tools/CIM-Profiles/total?label=git%20downloads)
![GitHub License](https://img.shields.io/github/license/PNNL-CIM-Tools/CIM-Profiles)

**cim-profiles** gives you the [Common Information Model (CIM)](https://cimug.ucaiug.org/) for
power systems as plain Python dataclasses. Each CIM *profile* is a Python package with one class
per CIM class (`ACLineSegment`, `Breaker`, `PowerTransformer`, ...), with typed attributes and
associations and with the UML documentation as docstrings. The package also includes the small
object model the classes are built on: identity and deterministic UUIDs (`Identity`), physical
quantities with units (`CIMUnit`, backed by [pint](https://pint.readthedocs.io/)), and merging
several profiles into one.

It is the data model behind [CIMantic Graphs (cim-graph)](https://github.com/PNNL-CIM-Tools/CIM-Graph),
but it has no database or graph dependencies (only `pint`). Any tool that needs the CIM classes
can use it. Because it is released separately from cim-graph, profile updates (new classes,
new profiles) don't have to wait for a cim-graph release.

## Installation

```bash
pip install cim-profiles
```

## Usage

```python
import cimprofiles.cim18.cim18v17 as cim

line = cim.ACLineSegment(name='line_1')
line.length = cim.Length(2.5, 'km')
```

Profiles are grouped by CIM version (`cimprofiles.cim16`, `cim17`, `cim18`). They include
CGMES 2.4 and 3.0, the IEC CIM 16/17 base models, CIMHub, GridAPPS-D and the EPRI GMDM split
profiles. The full list, and how to combine sub-profiles at runtime, is in
[`src/cimprofiles/README.md`](src/cimprofiles/README.md).

cim-graph 0.6 and later depend on this package. The old `cimgraph.data_profile.*` import paths
still work there, with a `DeprecationWarning`.

## How the profiles are made

The profiles are not written by hand. They are generated from the CIM UML with
[CIMTool](https://cimtool.ucaiug.io/), the open-source UCAIug tool for defining CIM profiles.
A profile is a selected subset of the CIM classes and attributes for one use case.

This repository ships the source profiles as **CIMTool projects** (`cim17v40/`, `cim18v15/`).
Each project contains the CIM UML model (`Schema/`) and the profile definitions (`Profiles/*.owl`).
The Python code is produced by the **cimantic-graphs builders**, two XSLT transforms from the
[UCAIug CIMTool Builders Library](https://cimtool-builders.ucaiug.io/):

- [`cimantic-graphs.xsl`](https://cimtool-builders.ucaiug.io/shipped-builders/cimantic-graphs/builder.html)
  generates the dataclasses for a profile.
- [`cimantic-graphs-init.xsl`](https://cimtool-builders.ucaiug.io/shipped-builders/cimantic-graphs/builder.html)
  generates the package `__init__.py`.

These builders ship with CIMTool 2.3.0 and later. Copies are kept in `CIMTool_plugin/`, along
with their documentation.

To open a project, clone with [Git LFS](https://git-lfs.com/) (the Sparx EA `.eap` models are
stored in LFS). Then import the project folder into a CIMTool workspace with *File > Import >
Existing Projects into Workspace* (see
[Exchange a project](https://cimtool.ucaiug.io/how-to/exchange-a-project/)).

## Where the profiles come from

![The CIM toolchain and its licenses: the UCAIug Apache 2.0 open-source artifacts, draft standards
available to UCA members, the IEC copyrighted standards, and the PNNL-CIM-Tools BSD-3 Python
libraries](https://raw.githubusercontent.com/PNNL-CIM-Tools/CIM-Profiles/refs/heads/develop/UCA-Licensing.png)

The CIM starts as a UML information model. The UCAIug publishes the model and two tools that work
with it, jCleanCIM and CIMTool, as open source under the Apache 2.0 license. CIMTool selects the
classes and properties a profile needs from the model and saves them as an OWL profile, from
which it generates RDFS and XSD schemas.

The jCleanCIM output and the schemas go into the draft standards documents, which UCA members can
read through the UCAIug liaison agreement. Once published, they become the IEC 61970, 61968, 62325
and 62746 standards, which are copyrighted by the IEC.

The PNNL-CIM-Tools Python libraries start from the OWL profiles alone, so they use only the
Apache 2.0 artifacts and are released under the BSD 3-Clause license. This repository is the
first step: its CIMTool workspaces hold the OWL profiles, and the cimantic-graphs builders in
`CIMTool_plugin/` turn them into the `cimprofiles` package.
[CIMantic Graphs](https://github.com/PNNL-CIM-Tools/CIM-Graph) (cim-graph) builds on the
package, and two chains of libraries build on cim-graph:

- CIM-Tables → CIM-Builder → CIMHub, which converts models for OpenDSS, GridLAB-D, ArcGIS and
  other tools
- CIM-Loader → CIM-Validator → CIM-Repair

### CIM releases

The CIM is a living standard, and the UML model is updated continuously between editions of
the IEC standards.

- **Major releases** are the CIM versions, for example CIM 16, 17 and 18. Each new version
  becomes the basis for the next editions of the IEC standards.
- **Minor releases** are numbered within a version. For example, CIM17v40 is the model behind
  IEC 61970-301 Ed 7.1, and Grid18v16 is an interim release of the CIM 18 work in progress.

The workspace folders here are named after the release they are built from (`cim17v40/`,
`cim18v15/`). Each UCAIug task force publishes its releases on its own site. Every release
there has its release notes and a change log of the UML changes since the previous release:

| Grid | Enterprise | Market |
|---|---|---|
| IEC 61970 | IEC 61968 | IEC 62325 |
| <https://utf13-releases.ucaiug.io/> | <https://utf14-releases.ucaiug.io/> | <https://utf16-releases.ucaiug.io/> |

## Repository layout

| Path | Contents |
|---|---|
| `cim17v40/`, `cim18v15/` | CIMTool workspaces. The Sparx EA `.eap` models are stored with Git LFS. |
| `CGMES-CIM16/`, `CGMES-CIM17/` | CGMES CIMTool workspaces vendored from the UCAIug repositories [cimug-org/CGMES-CIM16](https://github.com/cimug-org/CGMES-CIM16) and [cimug-org/CGMES-CIM17](https://github.com/cimug-org/CGMES-CIM17), with the Python builders enabled. Each folder's README records the upstream commit. The `.qea` models are stored with Git LFS. |
| `scripts/sync_cgmes.sh` | Copies in a new upstream version of a CGMES workspace and enables the Python builders again |
| `CIMTool_plugin/` | The cimantic-graphs XSLT builders and their documentation |
| `src/cimprofiles/` | The Python package, with profiles grouped by CIM version (`cim16/`, `cim17/`, `cim18/`). See [`src/cimprofiles/README.md`](src/cimprofiles/README.md) for the available profiles and how merging works. |
| `scripts/import_cimtool_output.sh` | Copies a profile generated by CIMTool into `src/cimprofiles/` and rewrites its imports |
| `src/cimprofiles/jsonld/` | JSON-LD contexts, QUDT unit vocabularies and their offline cache (see below) |
| `tests/` | Tests for `Identity`, UUIDs, merging and the generated profiles |

## Seeded UUIDs

Downstream converters (ArcGIS, OpenDSS, ...) need the same equipment to get the same RDF ID on
every run, so identifiers are deterministic. This section is the specification. `Identity.identifier` is a UUID (CIM 18):
either the one given, or a deterministic construct. There are two cases.

**Read from a file:** the `rdf:ID`/`rdf:about` *is* the UUID, in any serialization
(`urn:uuid:…`, `#_…`, `_…`, any case). The name is not used. An identifier that is not a UUID is
replaced, with a warning, by the UUID seeded from it (below), so reading the same file again
gives the same UUIDs. The original string is kept as the mRID, unless the file has an mRID.
Readers key their graphs with `cimprofiles.identity.read_identifier`, which gives the same UUID.

**Built** (converters, notebooks, `.cimtbl`): a new object, deterministic only for the same model
authority, model and class, plus one of two keys. A UUID given as the mRID is used directly.

- **mRID route** - with a (non-UUID) mRID, the mRID is the key and the name is not used, so a
  renamed object keeps its UUID. CIM 18 relaxes the mRID to a freeform string unique within the
  model, so this is the route for models keyed by mRID.
- **Name route** - with no mRID, the name is the key, so a renamed object (bus 300 to bus 301) is
  a different object and gets a different UUID.

The seeded UUID is version 5 (RFC 9562 §5.5):

```python
namespace = uuid5(NAMESPACE_URL, model_authority)
uuid = uuid5(namespace, f'{model_name}+{ClassName}+{mRID}+{name}+{seed}')
```

- `model_authority` is a URI (`CIMG_MODEL_AUTHORITY`, default
  `https://github.com/PNNL-CIM-Tools/CIM-Graph`), as in `md:Model.modelingAuthoritySet`, so
  each authority's UUIDs live in its own namespace. cim-graph writes the authority URI as
  `md:Model.modelingAuthoritySet` in every file header, and its readers restore it from there.
  In CIM XML the header is by default an `md:FullModel` followed by a `cim:ModelAuthority`
  object whose identifier is this namespace (`write_xml`). JSON-LD files (`write_json_ld`), and
  CIM XML written with `write_xml(header=...)`, have a `dcat:Dataset` header instead, with no
  `cim:ModelAuthority` object.
- `model_name` comes from `CIMG_MODEL_NAME` (default empty).
- `mRID` is the object's mRID, or the non-UUID `rdf:ID`/`rdf:about` of an object read from a
  file. It is normalized so every serialization of one object agrees: surrounding whitespace, a
  `urn:uuid:` prefix, everything up to the last `#` and one leading `_` are removed.
  `rdf:ID="_LINE1"`, `rdf:about="#_LINE1"` and `mRID="LINE1"` give the same UUID. Case is kept.
- `name` (whitespace-trimmed) is used only when there is no mRID, so one of the two is always
  empty. `seed` (passed to `obj.uuid(seed=...)`) is optional.
- Every component keeps its position even when empty, and `%` and `+` inside a component are
  escaped as `%25` and `%2B`, so two different inputs never produce the same string.
- No identifying input at all (or only empty/blank values) gives a random version 4 UUID.

`obj.uri()` returns the bare UUID: lowercase, or uppercase if it was read uppercase (CIMHub and
GridAPPS-D data), so writing a file back reproduces its identifiers. Underscores and
`urn:uuid:` prefixes belong to the serialization style and are added by cim-graph's writers
and queries (`CIMG_IEC61970_552`: `552-NEW`, `552-LEGACY` or `CGMES`).

`cimprofiles.identity.seeded_uuid` and `model_authority_namespace` implement the seeded UUID, and any
language with a UUID library can reproduce it from this description.

## Updating a profile

1. In CIMTool, edit the profile in its project and regenerate it with the cimantic-graphs
   builders (see [How the profiles are made](#how-the-profiles-are-made)), including the
   JSON-LD context builder (`custom-builders/cimantic-graphs-jsonld-context` of the
   CIMTool-Builders-Library, imported as a `TEXT` builder with the extension `context.jsonld`). CIMTool writes the output
   next to the profile, in `Profiles/`.
2. Import it. This copies the context into the package as `context.jsonld` and rewrites the
   `cimgraph.data_profile` imports emitted by CIMTool before 2.3.1:
   ```bash
   scripts/import_cimtool_output.sh cim17 <Profiles/name.py> <Profiles/name.__init__.py>
   ```
   The first argument is the CIM version directory. A fourth argument names the package
   directory when it differs from the envelope name (`gridappsd_rc4_2021` for `rc4_2021`),
   or places a part of a merged profile (`cim18v17/substation`).
3. Remove duplicate field definitions, and rebuild the pre-baked merged profiles (cim18gmdm,
   cgmes_3_0_0, cim18v17 and its distribution and transmission flavors) if it is one of their parts:
   ```bash
   uv run python -m cimprofiles.dedupe_profile_fields
   uv run python -m cimprofiles.build_merged_profiles
   ```
4. Rebuild its JSON-LD documents (below): `uv run python -m cimprofiles.jsonld.build <profile>`.
5. Run the tests: `uv run pytest`.

## JSON-LD contexts and units

Each profile has a JSON-LD context and one or more unit vocabularies, published at
`https://pnnl-cim-tools.github.io/CIM-Profiles/<profile>/<version>/` and shipped in the
package (`src/cimprofiles/jsonld/cache`) so they resolve offline. The version is a stable
cim-profiles release, in the URL as CGMES puts versions in its IRIs:

- While a release is in alpha (`0.2.1a1`, `a2`, ...), its directory (`0.2.1/`) is rebuilt in
  place as often as needed. Alpha documents resolve offline from the alpha wheel; Pages
  publishes stable releases only.
- Once the release is on PyPI its documents are frozen, since files written with it name them.
  Rebuilding changed documents for a released version fails and asks for the next release
  target in `pyproject.toml`.
- A profile gets a new directory only when its documents change; otherwise it keeps naming the
  release that last changed them. Earlier directories stay published.

- **Context** (`context.jsonld`): prefixes, and each property's datatype (`{"@type": "@id"}` for
  references and enumerations, else the XSD type of its values: `xsd:float`, `xsd:decimal`,
  `xsd:integer`, `xsd:boolean`, `xsd:dateTime`, ...), plus the `dcat:Dataset` header terms, all
  typed as in the Inst4CIM CGMES context (`dct:conformsTo`, `dcat:isVersionOf` as IRIs,
  `dct:issued` as `xsd:dateTime`). It is generated from the profile's `.owl` by the CIMTool
  context builder and imported into the profile's package; a merged release's context is the
  union of its parts'. Profiles whose `.owl` is not in this repo (cim16v33, cim18gmdm,
  cimhub_2023, cimhub_2026, rc4_2021) have theirs built from their classes instead, which types
  only floats, integers and booleans and leaves dates as strings. Next to `@context`, the file
  records its `@id` (its URL) and `owl:versionInfo` (the full release, e.g. `0.2.0`); JSON-LD processors read only
  `@context` from a remote context. A JSON-LD context cannot carry units.
- **Unit vocabulary** (`units-<convention>.jsonld`): `qudt:hasUnit` per property, the CGMES way.
  A data file names the vocabulary its numbers use in `dct:conformsTo`; the vocabulary's
  `owl:versionIRI` is its URL.

Units are a publishing convention, set per profile in `src/cimprofiles/jsonld/conventions/<profile>.yaml`.
Each property's unit is its `properties` override, else its `quantity_kinds` default, else the
CIMUnit base unit (SI):

```yaml
profile: cimhub_2023
default: si
conventions:
  si: {}
  distribution:
    quantity_kinds: {ActivePower: kW, ReactivePower: kVAr, ApparentPower: kVA}
    properties: {WireInfo.radius: mm}
```

`cgmes_3_0_0` uses the published CGMES 3.0 context and vocabularies (MW, kV, km, ...) instead
(copies from [Inst4CIM-KG](https://github.com/Sveino/Inst4CIM-KG), Apache-2.0).

```bash
uv run python -m cimprofiles.jsonld.build                  # rebuild every profile into the cache
uv run python -m cimprofiles.jsonld.build my-units.yaml --base-url https://example.org/cim/ --output site
```

The second form builds your own convention for hosting elsewhere. Readers resolve it from its URL
when fetching is allowed (`cimprofiles.jsonld.load_document(iri, allow_fetch=True)`); only the
shipped cache is used otherwise.

## Development

```bash
uv sync
uv run pytest
```

## License

BSD 3-Clause. See [LICENSE](LICENSE). The vendored `CGMES-CIM16/` and `CGMES-CIM17/` workspaces
keep the UCAIug Apache 2.0 license; see the `LICENSE` in each folder.


## Attribution and Disclaimer

This software was created under a project sponsored by the U.S. Department of Energy’s Office of Electricity, an agency of the United States Government.  Neither the United States Government nor the United States Department of Energy, nor Battelle, nor any of their employees, nor any jurisdiction or organization that has cooperated in the development of these materials, makes any warranty, express or implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or any information, apparatus, product, software, or process disclosed, or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or service by trade name, trademark, manufacturer, or otherwise does not necessarily constitute or imply its endorsement, recommendation, or favoring by the United States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions of authors expressed herein do not necessarily state or reflect those of the United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by
BATTELLE
for the
UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830