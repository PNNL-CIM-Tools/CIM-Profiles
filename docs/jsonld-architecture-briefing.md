# JSON-LD vocabulary and context: architecture briefing

Prepared 2026-11-12 as input to a decision review. The question is how CIM-Profiles and
CIM-Graph should define, generate and publish the JSON-LD context and the vocabulary
(classes, properties, datatypes, units) for each CIM profile. The goals, in order, are
**semantic correctness** and **readability**, for people and for machines.

The main choice is between:

- **A. Follow Svein's design** (Inst4CIM-KG): Turtle vocabularies made from the official
  RDFS by SPARQL fix scripts, plus one CIM-wide JSON-LD context.
- **B. A CIMTool builder** (prototype on a branch of CIMTool-Builders-Library): one
  JSON-LD document per profile that is both the context and the vocabulary, generated
  from the Enterprise Architect (EA) model through CIMTool.
- **C. A hybrid** of the two, or something else.

The reviewer should write a decision record that names the chosen design, the
alternatives it rejects and why, the migration steps, and an experiment that could prove
the choice wrong.

## 1. Constraints that are already decided

- **CIMTool and the Builders Library are canonical.** The XSLT builders in
  CIMTool-Builders-Library are the reference copies. CIMTool's release-candidate cycle
  pins a specific version of the builders into its Maven build.
  `CIM-Profiles/CIMTool_plugin/` is an out-of-date copy kept for copyright purposes.
- **Profiles are merged from parts.** `cimprofiles.merge.merge_profiles` merges
  sub-profiles at run time. CIM-Graph selects a merge with a comma-separated
  `CIMG_CIM_PROFILE`. `build_merged_profiles` bakes the stable merges listed in
  `merge_releases.yaml`. Whatever vocabulary design is chosen must either mirror this
  run-time merge, or have every profile refer to one canonical merged vocabulary.
- **Instance data style follows CGMES and Nordic44.** The `@context` is a URL. The `@graph`
  is flat. References are `"urn:uuid:…"` strings, numbers are strings typed by the context,
  and enumeration values are compact IRIs such as `"cim:PhaseCode.ABC"`.
- **Documents are cached offline.** Contexts and vocabularies ship in the `cimprofiles`
  wheel. Fetching from the network happens only on opt-in (`CIMG_ALLOW_REMOTE_CONTEXT`).
- **Not all profile sources are migrated yet.** The CIMTool projects for cim16v33, cimhub,
  rc4_2021 and cgmes_3_0_0 are on a Windows CIMTool 2.1 setup and are not yet migrated to
  2.3.1. Only cim17v40 and cim18v15 are in this repository.

## 2. The current implementation and its defects

The last commits (CIM-Graph `d055762` "json-ld with context" and `669370c` "add dcat";
CIM-Profiles `ab262eb` and `1a73b73`) build contexts and unit vocabularies in
`cimprofiles/jsonld/build.py`. They are built **from the generated Python dataclasses**,
by reading each field's type annotation with a regular expression. Units come from a
custom YAML format (`jsonld/conventions/*.yaml`) and from a hand-written table of QUDT
unit names (`qudt.py`). For `cgmes_3_0_0`, the implementation uses copies of Svein's
context and vocabularies.

Defects found in review (all reproduced):

1. **Units are wrong by a factor of 1000 in CIM XML.** The CGMES RDFS fixes
   `BaseVoltage.nominalVoltage` in kV (`cims:isFixed "k"` on the multiplier). The
   generated `cgmes_3_0_0` Python classes have `multiplier = none`. `XMLFile` therefore
   reads `420` as 420 V, while `JSONLDFile` reads the same value from Nordic44 as 420 kV,
   because it takes the unit from Svein's vocabulary. Units are currently defined in four
   places (generated classes, YAML, unit vocabularies, `qudt.py`), and they disagree.
2. **Datatypes are lost.** The generated Python types DateTime, Duration and Decimal as
   `str`. Our contexts therefore cannot type them. Svein's context types 62 properties as
   `xsd:dateTime`, 25 as `xsd:duration` and 23 as `xsd:decimal`.
3. **The reader ignores a dataset header at the top level.** The ENTSO-E JSON-LD
   specification draft puts the `dcat:Dataset` properties on the top-level node.
   `JSONLDFile` reads headers only from inside `@graph`. A file that declares the kW
   convention in this layout is read in W, with no warning.
4. **Exports overclaim conformance.** The writer lists all 9 CGMES profiles in
   `dct:conformsTo` for every `cgmes_3_0_0` export. Nordic44's EQ file lists only
   CoreEquipment. The design uses one property both for "conforms to" and for "units are
   defined in".
5. **Any unknown `dct:conformsTo` entry stops the file from loading.** Every entry must be
   a cached units vocabulary, so naming a standard or the Dynamics profile makes reading
   fail.
6. **The writer emits no named graph.** Without a top-level `@id`, every file's triples go
   into the default graph. A store that holds both a kW file and a W file then cannot
   tell their numbers apart.
7. **The namespace changes silently.** Nordic44 uses `https://cim.ucaiug.io/ns#`. Reading it
   with `cgmes_3_0_0` and writing it back produces `http://iec.ch/TC57/CIM100#`.
8. **Four tests fail.** They expect the unversioned CIM-Profiles URLs from before
   `1a73b73`. The CIM-Graph `uv.lock` still pins `cim-profiles<0.2`.
9. **A stale file gets published.** `jsonld/cache/cim18v17_distribution/context.jsonld` is
   not in `index.json`, but `pages.yml` publishes it.
10. **The model name is taken from free text.** `dct:description` is read as the model
    name, so Nordic44's one-sentence description becomes `CIMG_MODEL_NAME`.

## 3. Evidence from the prototype

**The CIMTool CLI runs headless on Linux.** CIMTool `linux-release-target` (2.3.1)
builds with Maven. It runs against the cim18v15 project (EA file from Git LFS) in about
20 s for one profile and 25 s for all 23 profiles. This shows that the 2.1 → 2.3.1
migration path works on Linux, at least for cim18v15.

**CIMTool's intermediate profile XML has what a vocabulary needs.** The CLI's `xml`
builder writes the Catalog XML that every builder reads. It contains:

- each attribute's XML Schema type (`xstype`: float, integer, boolean, string, dateTime,
  decimal, …);
- each CIM datatype's fixed unit and multiplier: an `Enumerated` element named `unit` or
  `multiplier`, with `@constant`. The value `''` means the profile does not fix it,
  `none` means the base unit, and `M` or `k` is a prefix;
- for every property, its IRI, domain, range, inverse and multiplicity;
- superclasses and enumeration values.

**The draft builder works.** It is `custom-builders/json-ld-vocabulary/` on branch
`jsonld-vocabulary` of CIMTool-Builders-Library, commit `4217d19`. It is **not pushed**:
the session lacked write access. A patch was saved in the session scratchpad, which does
not outlive the session. Push it or re-apply it before relying on it. It writes one
document per profile:

- `@context`: prefixes, the dataset header terms, and a type for every typed property;
- `@graph`: an `owl:Ontology` node; classes with `rdfs:subClassOf`; properties with
  `rdfs:domain`, `rdfs:range` and `owl:inverseOf`; enumeration values; and for each CIM
  datatype attribute, `cims:dataType`, `cim:unitSymbol`, `cim:unitMultiplier` and
  `qudt:hasUnit`.

Results for `electrical_balanced`, compared with the current Python-based build:

- rdflib reads 1610 triples, including 90 `qudt:hasUnit` triples. The existing cimprofiles
  loaders read the document unchanged.
- All 174 property types in today's context come out identical. The builder also types 25
  more properties correctly (date-times, and one `xsd:decimal`).
- The 90 units are identical.

Results across all 23 cim18v15 profiles:

- No two profiles disagree on a prefix, a context type, an `rdfs:range` or a unit
  (1670 typed properties, 536 units).
- 45 classes have a different `rdfs:subClassOf` in different profiles. Each profile links
  a class to the nearest superclass it selected; for example, `Equipment` →
  `IdentifiedObject` in a profile without `PowerSystemResource`. `merge.most_specific_base`
  already resolves this case for the Python classes.
- The union of the 18 parts of the `cim18v17` release contains every term in today's
  merged context and every unit in today's units vocabulary, with no unit differences.
- Two `nc_schedule` properties (`SwitchTimePoint.locked`, `.open`) come out of CIMTool as
  references with no target class. This looks like a profile defect (the project has an
  `nc_schedule.repair` file). The builder writes them untyped and prints a warning.

**Svein's pipeline, as found in Inst4CIM-KG:**

- `rdfs-improved/`: the official CGMES and NC RDFS (RDF/XML) are converted to Turtle by
  owl-cli. Numbered SPARQL Update scripts (`fix01` … `fix20`, each tied to a GitHub
  issue) correct datatypes, units, quantity kinds, inverses, multiplicity, language tags
  and ontology metadata. JSON-LD copies of each vocabulary are generated as well.
- Each property gets `owl:DatatypeProperty`/`owl:ObjectProperty`, `owl:FunctionalProperty`
  where the multiplicity is 1, `cim:unitMultiplier`, `cim:unitSymbol`,
  `qudt:hasQuantityKind`, `qudt:hasUnit`, `rdfs:domain`, `rdfs:range` and
  `cims:multiplicity`.
- The ontology node carries DCAT metadata (`dct:conformsTo` the IEC standards,
  `owl:versionIRI` = the profile IRI that instance data names in `dct:conformsTo`).
- `rdf-improved/`: **one CIM-wide context** of about 5,100 property terms, assembled with
  `cat` from text fragments. There are two variants, one for each namespace generation
  (`cim-context-old` for CIM100, `cim-context-new` for `cim.ucaiug.io`). It is served from
  `raw.githack.com/.../develop` (Inst4CIM-KG issue #110 asks for a permanent location).

## 4. Candidate designs

| | A. Svein's design | B. Builder, one document per profile | C. Hybrid (sketch) |
|---|---|---|---|
| Source of truth | Official RDFS + SPARQL fix scripts | EA model → CIMTool profile | EA model → CIMTool profile |
| Vocabulary format | Turtle (+ JSON-LD copy) | JSON-LD (context + vocabulary) | Turtle written by a builder, JSON-LD derived |
| Context | One context for all of CIM, per namespace generation | One per profile; union for merged profiles | One per release (union of parts), or CIM-wide |
| Units | Fixed by SPARQL scripts | From the profile's fixed unit and multiplier | Same as B |
| Covers our profiles (cimhub, GridAPPS-D, GMDM) | No: only CGMES and NC | Yes | Yes |
| Merge story | Global context; `conformsTo` lists the parts | Context array or a baked union | Baked union |
| Fixes to defects | Made in scripts that live outside the model | Made in the profile or the builder, upstream | Same as B |

Points to weigh:

- **Readability.** Turtle is the most readable form for review, and it is what Svein's
  community reads. JSON-LD is what tools load. B writes only JSON-LD. C writes Turtle and
  derives JSON-LD from it.
- **Semantic correctness.** Both A and B attach units to properties (meta-modelling) rather
  than to quantity values. This is the established CIM convention, but it is not how QUDT
  models units. Decide this once (see section 5).
- **One context versus one per profile.** The evidence that profiles never disagree on
  types suggests that a single CIM-wide context, built as the union of the parts, is safe.
  That would also give instance files one stable context URL. A per-profile context is
  smaller and versioned with its profile.
- **Combined or separate documents.** B's document is both the context and the vocabulary,
  so the two cannot drift. But every tool that fetches the context downloads the whole
  vocabulary: 1.9 MB with comments for 23 profiles. Svein keeps them separate.

## 5. Questions on semantic correctness

1. **Units on properties.** `cim:unitSymbol`, `cim:unitMultiplier` and `qudt:hasUnit` are
   stated on a property. Keep this, or model units through QUDT quantity values? Keep both
   the CIM and the QUDT terms, or only one?
2. **`qudt:hasQuantityKind`.** Svein points it at a CIM datatype class (`cim:ActivePower`),
   not at a QUDT quantity kind (`quantitykind:ActivePower`). Use QUDT terms,
   `cims:dataType` (the prototype's choice), or `skos:exactMatch` mappings (Svein maps
   `cim:PU` to `quantitykind:DimensionlessRatio`)?
3. **A multiplier the profile does not fix.** The prototype writes `none`: instance values
   are in the base unit. Confirm this reading of CIM, or leave the multiplier out.
4. **Enumerations.** `rdfs:Class` (prototype) or `owl:Class` (Svein). The values are
   individuals of the enumeration class. Should the vocabulary add `owl:oneOf`? Should
   `cims:stereotype` be an IRI (`uml:enumeration`) or a string (`"enum"`)? Svein uses both.
5. **Multiplicity.** Svein writes `owl:FunctionalProperty` and `cims:multiplicity`. The
   prototype writes neither. Is multiplicity part of the vocabulary, or only of SHACL
   shapes (Inst4CIM-KG has `shacl-improved/`)?
6. **Superclasses differ between profiles.** Should a profile's vocabulary say what its
   profile selected (`Equipment` subClassOf `IdentifiedObject`), or what the CIM says
   (`Equipment` subClassOf `PowerSystemResource`)? The first is true but loses
   information. The second needs the full CIM hierarchy, which CIMTool has.
7. **Number types.** CIM Float is `xsd:float` (32-bit). The writer writes up to 15
   significant digits, which only `xsd:double` holds. Decide between precision and the
   standard.
8. **Header placement.** Top-level `dcat:Dataset` (ENTSO-E draft), or a node inside
   `@graph` with a top-level `@id` (Nordic44)? Should the dataset be a named graph?
9. **Meaning of `dct:conformsTo`.** Profile conformance, the source of units, or any
   standard? What does a reader do with entries it does not know?
10. **`dcat:isVersionOf` and the model name.** Model authority or model series? And where
    does a short model name go (`dct:title`?)?
11. **Namespace generations.** CIM100 (`http://iec.ch/TC57/CIM100#`) or `cim.ucaiug.io`.
    Should a reader accept both, and should a writer convert between them?

## 6. Questions on readability

- Should Turtle be published next to the JSON-LD, for review and diffs?
- Comments in the vocabulary: always, or a builder option to leave them out of the
  context-sized file?
- Prefix names for extension namespaces. The prototype uses project prefixes, then a fixed
  table (`eu`, `nc`, `gad`, `gb`, `gmdm`), then `ext1`, `ext2`, ….
- Document IRIs and versions. The builder receives `version` from the profile OWL
  ("Beta"), not the cim-profiles release. In cim18v15 every part shares one namespace,
  so the default IRI cannot be resolved. A `--param key=value` option for `cimtool-cli`
  would let the release set `vocabularyIRI`.

## 7. Open items with Svein

These are drafted in an earlier proposal (session scratchpad,
`proposal-to-svein-jsonld-context-header.md`). In short:

- one header layout;
- converter artifacts in Nordic44 (a `json-ld#base` property; `dct:issued` typed as a date);
- stable, versioned context URLs;
- a separate small context for the header terms;
- a normative rule that units are found through `dct:conformsTo`;
- the meaning of `dcat:isVersionOf`.

## 8. How to reproduce

```bash
# Build the CIMTool CLI (branch linux-release-target of AAndersn/CIMTool)
cd cimtool/cimtool-cli && mvn -q -B package -DskipTests      # target/cimtool-cli.jar
# The EA file is in Git LFS
cd CIM-Profiles && git lfs pull --include="cim18v15/Schema/*"
# Intermediate profile XML for one profile
java -jar cimtool-cli.jar --project-dir cim18v15 \
     --profile cim18v15/Profiles/electrical_balanced.owl --builder xml --output out
# Vocabulary documents for all profiles in the project
java -jar cimtool-cli.jar --project-dir cim18v15 \
     --xslt CIMTool-Builders-Library/custom-builders/json-ld-vocabulary/json-ld-vocabulary.xsl \
     --type TEXT --output-ext vocab.jsonld --output out
```

The comparison scripts were in the session scratchpad, which does not survive the
session. They:

1. parse each document with rdflib;
2. read units with `cimprofiles.jsonld.context.vocabulary_units`;
3. compare `property_datatypes` and `convention_units` against `build_context` for the
   matching generated module;
4. count disagreements between profiles per prefix, type, range, unit and superclass.

## 9. Proposed acceptance test

Once the CGMES projects are migrated to CIMTool 2.3.1, run the chosen builder on CGMES 3.0.
Compare its context and units with Svein's `cim-context-old.jsonld` and his
`rdfs-improved/CGMES` vocabularies. Every difference must be explained: either as a
defect in one of the two, or as a deliberate choice recorded in the decision record.
