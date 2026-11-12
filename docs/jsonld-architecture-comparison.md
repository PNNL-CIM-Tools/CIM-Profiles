# JSON-LD vocabulary, profile and context: comparison of architecture options

Review of 2026-11-12. It follows `jsonld-architecture-briefing.md` and uses the same
evidence, plus six new experiments (section 3). The goal is a reference implementation
that the next IEC standard can be written against and that vendors can be graded on.
The two criteria, in order, are semantic correctness and readability.

## 1. Conclusion

**Neither Svein's published files nor the builder prototype is the right target as it
stands. Both put two different things in one artifact.** The recommended design keeps
them apart, in four layers, each with the W3C standard made for it:

| Layer | What it states | Standard | Source |
|---|---|---|---|
| Vocabulary | Each class, property and enumeration value, defined once | RDFS / OWL, in Turtle | The CIM model |
| Profile | Which terms a profile uses, with cardinality, datatype and **unit** | SHACL, described by PROF | The CIMTool profile |
| Serialisation | How terms and datatypes are written in JSON | JSON-LD context | Derived from the vocabulary |
| Conformance | Whether a dataset meets a profile | SHACL validation report | Derived by running the shapes |

Every layer is generated. Nothing is edited by hand, and nothing is patched after export.
This is option C in section 4.

Most of this is where Svein's own notes already point: one definition per term, profiles
that import rather than redefine, SHACL for constraints, PROF to describe profiles. There
are two places where the evidence disagrees with his current files or plans:

1. **Units belong to the profile, not to the property.** His vocabularies state the unit
   on the CIM property. That is consistent inside CGMES, and it breaks as soon as a second
   profile family uses the same property in another unit (section 3, experiment 1).
2. **LinkML's own generators should not produce the normative artifacts.** His plan for
   IEC 61970-501 ed. 2 generates the RDFS and SHACL "from LinkML". LinkML's standard
   generators produce a wrong context and shapes that do not meet his own SHACL draft
   (experiment 6). This is not an argument against LinkML as a source: see "LinkML as a
   future source" in section 6.

Both points need his agreement before anything is built on them. They are the first two
decisions in section 7.

## 2. What the two criteria mean here

To compare options, each criterion is written as tests an option either passes or fails.

Semantic correctness:

- **S1. One definition per term.** A class or property has one IRI and is defined in one
  place.
- **S2. Loading more never makes a statement false.** Any two conformant vocabularies or
  profiles can be loaded into one store without contradiction.
- **S3. Model and constraints are separate.** What a term means (true everywhere) is kept
  apart from what one profile requires (true for that profile).
- **S4. Datatype and unit can be found from the dataset alone.** A reader starts at the
  dataset header and reaches the datatype and unit of every number by following IRIs.
- **S5. Standard vocabularies are used as intended.** No strings where IRIs belong, no
  private stand-ins for OWL, SHACL, PROF, DCAT or QUDT terms.
- **S6. Derived artifacts are generated.** A context cannot disagree with its vocabulary,
  because it is computed from it.
- **S7. Conformance can be decided by machine.** A dataset passes or fails with a report
  that names each failure.

Readability:

- **R1. The source can be reviewed as a diff** by a domain engineer.
- **R2. Instance files are plain.** Short keys, plain values, no repeated boilerplate.
- **R3. One artifact, one job,** with a header that says what it is.
- **R4. One command rebuilds everything,** on open tools.

## 3. New evidence

All six experiments ran in this session, on Svein's files in Inst4CIM-KG, the Nordic44
equipment file, and the cim18v15 CIMTool project.

**Experiment 1: units stated on properties conflict between profile families.**
Svein's 30 improved vocabularies (CGMES and NC) give 1,331 properties a unit, and no
property has two different units. CGMES and the GridAPPS-D cim18v15 profiles share 256
unit-bearing properties, matched by name. **117 of them have a different unit**: 39 are
MW against W, 36 are kV against V, 20 are MVAr against VAr. In 116 of the 117 the unit
symbol is the same and only the multiplier differs. (The last is one unit, rotation speed,
under two QUDT names.) The two families use
different CIM namespaces today. The CIM community has decided that from CIM18 the IRI of
a canonical term stays stable. Once both families use the same IRIs, a store that loads
both vocabularies holds `cim:BaseVoltage.nominalVoltage qudt:hasUnit unit:KiloV` and
`… unit:V` together, and no reader can tell which applies to which dataset. This is the
1000× error from the briefing, moved into the vocabulary.

**Experiment 2: the official CGMES shapes carry no units.** The CGMES 3.0 equipment
shapes (`61970-600-2_Equipment-AP-Con-Simple-SHACL`) do not mention a unit or multiplier.
Svein's SHACL draft for 501 says units "cannot be subject to validation as there is not
enough information exchanged in the instance data". So today no artifact that is scoped
to a profile says what unit a number is in.

**Experiment 3: a typed context makes JSON-LD pass the conformance shapes.** Nordic44
equipment, read with Svein's context, **conforms** to the CGMES 3.0 datatype and
cardinality shapes: no results from 10,979 shape triples, in 3 seconds with pyshacl. The
same file read with prefixes only, so that every number is a plain string as in CIM XML,
gives 3,158 datatype violations. The complex rule set (`61970-452_Equipment-AP-Con-Complex`)
reports 4 violations on the typed data (three `LinearShuntCompensator.gPerSection`, one
`ACLineSegment.x`) and crashes on the untyped data, because it sums strings. The
datatypes in the context are therefore part of conformance, not a convenience.

**Experiment 4: the published file is the canonical form of its context.** Expanding
Nordic44 and compacting it again with the same context reproduces all 2,156 nodes
exactly. "A conformant file equals its own compaction against the normative context" is
therefore a rule that can be tested, with a standard JSON-LD processor and no custom code.

**Experiment 5: Svein's context agrees with his vocabularies.** The context is assembled
by concatenating text files, so it could drift. It has not: of 5,116 properties in the
vocabularies, every non-string property is in the context with the same type. The context
has 49 extra terms that no vocabulary defines. The types depend only on each property's
range, so one context for the whole vocabulary is sound, and it can be generated.

**Experiment 6: LinkML's standard generators do not produce the artifacts needed, and
CIMTool's LinkML output loses information.** CIMTool ships a `linkml` builder. On
`electrical_balanced`:

- The output is not valid LinkML. One class has the key `value` twice, because the
  `.value` attributes of CIM datatypes leak into it. This is a builder defect.
- The output loses information the profile holds. It has none of the profile's 46 fixed
  units and multipliers and none of its 38 inverse associations. LinkML can carry both:
  it has a `unit` field on slots and types, and an `inverse` field.
- With that defect patched by hand, LinkML's context generator writes 192 terms keyed by
  the short attribute name. Many CIM attributes share a short name, so `r` maps to
  `cim:TransformerWinding.r`. Data for `ACLineSegment.r` would be read as the wrong
  property. Svein's draft mapping uses qualified slot names, which would avoid this; the
  builder does not follow it.
- LinkML's SHACL generator writes anonymous property shapes without `sh:severity`,
  `sh:message` or `sh:name`, which Svein's SHACL draft requires. It also marks 47 shapes
  `sh:closed`, so the shapes of two profile parts cannot be combined.
- LinkML's OWL generator writes 435 OWL restrictions for cardinality. In OWL these are
  statements about the world, not checks on data.

**Correction to the briefing.** The briefing said `qudt:hasQuantityKind` points at CIM
classes that are not QUDT quantity kinds. That was wrong. Svein's vocabularies type
`cim:ActivePower` and 29 others as `qudt:QuantityKind` and map them to QUDT with
`skos:exactMatch`. They also map CIM unit symbols to QUDT units, and give multipliers a
numeric `qudt:prefixMultiplier`. That is correct use of QUDT, and it means the name table
in `cimprofiles/jsonld/qudt.py` duplicates data his vocabularies already publish.

## 4. The options

**0. Today's implementation.** Contexts and units are computed from the generated Python
classes, a YAML format and a hand-written unit table. It is the baseline only. It fails
S4 and S6 (the briefing lists ten defects).

**A. Svein's published files (Inst4CIM-KG).** The official RDFS is converted to Turtle
and corrected by about twenty SPARQL scripts, each tied to an issue. One context covers
all of CIM. Units are stated on properties.

**B. The builder prototype.** A CIMTool builder writes one JSON-LD document per profile.
The document is both the context and the vocabulary. Units are stated on properties.

**C. Four layers, generated from CIMTool.** As in section 1. Builders write RDF. Standard
RDF tools serialise it and derive the context.

**D. LinkML generators as the producer.** CIMTool writes LinkML. LinkML's own generators
write the vocabulary, shapes, context and Python classes. This is one reading of the plan
in the Spec4CIM-KG README for 501 ed. 2. It is not the plan for CIMTool, which is to add
a LinkML-to-OWL engine so that LinkML becomes a second source and every builder keeps
working. That plan is compatible with option C (section 6).

## 5. Comparison

| Test | 0. Today | A. Svein | B. Prototype | C. Four layers | D. LinkML hub |
|---|---|---|---|---|---|
| S1 one definition per term | No | Partly | No | Yes | Partly |
| S2 loading more is safe | No | Within CGMES only | No | Yes | Not shown |
| S3 model apart from constraints | No | Partly | No | Yes | No |
| S4 datatype and unit from the dataset | Partly | Yes, for CGMES | Yes | Yes | No units |
| S5 standards used as intended | No | Mostly | Partly | Yes | Partly |
| S6 derived artifacts generated | No | In effect | Yes | Yes | Yes |
| S7 conformance by machine | No | Yes | No | Yes | Partly |
| R1 source reviewable as a diff | No | Yes | No | Yes | Yes |
| R2 plain instance files | Yes | Yes | Yes | Yes | Different keys |
| R3 one artifact, one job | No | Yes | No | Yes | Yes |
| R4 one command, open tools | Yes | Partly | Yes | Yes | Yes |
| Covers non-CGMES profiles | Yes | No | Yes | Yes | Yes |
| Demonstrated today | Yes | Yes | Partly | Partly | No |

Reasons for the entries that are not obvious:

**A. Svein's files.** This is the best material that exists, and experiments 3 to 5 show
it works: typed data validates, the document form is canonical, and the context matches
the vocabularies. Its weak points are ones his own notes name as unresolved:

- S1: 181 of 5,213 properties are defined in more than one vocabulary. His notes count
  875 of 7,268 terms defined more than once, and record the decision that only packages
  should define terms.
- S2 and S3: units are stated on the shared property, so they hold only while a single
  profile family uses the vocabulary (experiment 1).
- R4: the source is still the flawed RDFS export, repaired afterwards. A defect fixed by
  script comes back in every profile exported the old way, and the scripts do not exist
  for profiles outside CGMES and NC.

**B. The prototype.** It proved that CIMTool holds everything a vocabulary needs: XML
Schema datatypes, fixed units and multipliers, domains, ranges and inverses. As a design
it has three faults:

- Each profile's document defines the same terms again (S1). Across the 23 cim18v15
  profiles, 45 classes come out with different parents. Loaded together these do not
  contradict each other, because each stated parent is a true ancestor. They do break any
  tool that expects one parent per class.
- It states units on properties, like A (S2).
- One document does three jobs: context, vocabulary and profile (R3). Every tool that
  fetches the context downloads all of it.

It also writes JSON by text templating in XSLT, which needed hand-written escaping. A
builder should write RDF/XML, which XSLT does well and the existing `rdfs-2020` builder
already does, and leave Turtle and JSON-LD to RDF tools.

**C. Four layers.** It passes every test by construction, and its parts are standard.
What is shown today: CIMTool has the data and runs headless on Linux; typed JSON-LD
validates against real shapes; the canonical document form is testable; one context for
the whole vocabulary is sound. What is not shown yet is listed in section 8.

**D. LinkML generators as the producer.** Experiment 6. LinkML is a readable schema
language, and a reasonable successor to the EA model as the place where profiles are
written. Its standard generators do not produce what this project needs, so custom
generators would be required for the context and the shapes. Those custom generators
already exist in another form: they are the CIMTool builders. The normative artifacts
should stay in the W3C stack and come from the builders, whatever the source is.

## 6. The recommended design in detail

**Vocabulary.** One Turtle document per CIM package or extension namespace, with stable
term IRIs and a versioned `owl:versionIRI`. It states only what is true in every profile:
class hierarchy, domain, range, inverse, and the quantity kind of a numeric property
(`qudt:hasQuantityKind cim:ActivePower`, as Svein has it), and its unit symbol
(`cim:unitSymbol cim:UnitSymbol.W`), on which the profile families agree. It does not
state the multiplier, cardinality, or which profile uses a term.

**Profile.** One SHACL shapes graph per profile, in the profile's own namespace. Each
property shape has `sh:path`, `sh:datatype` or `sh:class`, `sh:minCount` and `sh:maxCount`,
with the name, message and severity the 501 SHACL draft requires. For a numeric property,
the same shape states the multiplier (`cim:unitMultiplier`), and for convenience the
resulting QUDT unit (`qudt:hasUnit`). The statement is about the shape, which belongs to
the profile, so two profiles can state different multipliers for one property and both
remain true. The multiplier is stated per attribute, not per datatype, so one profile can
give `Conductor.length` in km and `WireInfo.radius` in mm. A PROF descriptor names the
profile, what it is a profile of, and its artifacts with their roles.

This is a proposal, not an existing convention. Nothing in SHACL or QUDT defines where a
profile should state the unit of a property. Attaching it to the property shape is the
smallest step that passes S2. The alternative that is purest semantically is a unit on
every value, as a QUDT quantity value or a typed literal. That would make every number an
object or a compound string. It breaks with CGMES practice and with Nordic44, so it is
rejected here.

**Why the multiplier has to be a profile statement.** The canonical CIM now uses
unprefixed units, introduced by the distribution side. Every existing CGMES exchange
writes MW and kV as plain numbers. A standard that fixes one multiplier per property
forces one side to break its data. A standard that states the multiplier per profile
breaks nothing: the CGMES profiles keep `M` and `k`, which their RDFS already fixes with
`cims:isFixed`, and distribution profiles state `none`. What must not happen is a
multiplier stated on the shared property, which is what `qudt:hasUnit unit:KiloV` on
`cim:BaseVoltage.nominalVoltage` does today.

One reading rule covers every profile: the value in the unprefixed unit is the number as
written, times ten to the power of the profile's multiplier for that attribute, which is
`none` if the profile states nothing. A tool that holds data from several profiles
converts to the unprefixed unit when it loads, as CIM-Graph's `CIMUnit` does. Files are
scaled by profile; a shared store is not.

**Exponent notation.** `xsd:float` allows `"100e3"`, and Svein's header example already
writes `"220e3"`. A profile with no multiplier can use it to avoid padded zeros and to
give each attribute a natural scale: `"5.2e3"` for a conductor length, `"9.14e-3"` for a
wire radius. It needs no rule of its own, because it is ordinary number syntax and the
reading rule above already covers it. JSON-LD expansion and compaction keep the text as
written, and SHACL and SPARQL treat it as a number. A triple store may rewrite it
(rdflib writes `"5200.0"`), which changes the text and not the value. A profile can state
a preferred exponent per attribute so that files in canonical form look alike.

**Units conventions become profiles.** A dataset in kW and a dataset in W conform to
different profiles, and should say so with different IRIs in `dct:conformsTo`. The
`distribution` and `si` conventions in `jsonld/conventions/*.yaml` become two profiles
that share node shapes and differ in unit statements. The YAML format goes away.

**Context.** Generated from the vocabulary by one query: each property with a class range
gets `"@type": "@id"`, each with an XML Schema range gets that type, strings are left out.
There is one context per vocabulary version, at a versioned IRI. A second, small context
holds the dataset header terms. An instance file lists the ones it uses:
`"@context": [header, cim, extension]`. Profiles need no context of their own, so merging
profile parts never touches the context.

**Instance files.** As Nordic44: flat `@graph`, `cim:Class.property` keys, references as
IRI strings, numbers as strings typed by the context. Short keys such as `"r"` would read
better. Svein's notes examine them and find them unproven: they need a context scoped by
type, subclass reasoning, and a type on every node, which difference models do not have.
The canonical form of a file is its compaction against the normative contexts
(experiment 4).

**Merged profiles.** With this split, the run-time merge needs no vocabulary merge. The
context and vocabulary are the same for every part. The header's `dct:conformsTo` lists
the parts whose classes are in the file. The shapes of the parts are loaded together,
which is how SHACL is meant to be used. A pre-built release, such as `cim18v17`, publishes
a PROF descriptor that lists its parts. Two parts that state different units for one
property are a real conflict, and the reader should refuse them as it does today.

**Conformance.** A dataset is graded in three steps, each with a standard tool:

1. It parses as JSON-LD and equals its own compaction against the normative contexts.
2. Its header names at least one known profile in `dct:conformsTo`.
3. It validates against the shapes of those profiles. The grade is the SHACL validation
   report.

**Generation.**

```
EA model ─ CIMTool ─┬─ builder rdfs-2020 (exists) ───── RDF/XML ─┐
  (profile .owl)    ├─ builder for profile shapes (new) ─ RDF/XML ─┼─ RDF tools ─┬─ Turtle (reviewed, published)
                    ├─ builder for PROF descriptor (new)  RDF/XML ─┘             ├─ JSON-LD copies
                    └─ builder cimantic-graphs (exists) ─ Python classes         └─ context (derived by query)
```

**LinkML as a future source.** LinkML is expected to replace the EA model as the source
of truth in about five years. CIMTool will get a LinkML-to-OWL engine, so that a profile
written in LinkML feeds the same builders. This fits the design, because the builders'
input is the one stable interface: the four layers do not change when the source does.
It adds one requirement. Everything the layers need has to survive the path through
LinkML:

- the fixed unit and multiplier of each CIM datatype (LinkML `unit`);
- the XML Schema type of each attribute, including date-time, duration and decimal;
- inverse associations (LinkML `inverse`);
- the IRI and namespace of every class, property and enumeration value;
- cardinality, abstract classes and the true parent class.

The test is a round trip: EA model → `linkml` builder → LinkML-to-OWL engine → every
other builder, compared with the same builders run directly on the EA model. The result
must be identical. Today's `linkml` builder would fail it (experiment 6): it loses units
and inverses, and writes one invalid key. It also writes attributes inside each class,
where Svein's UML-to-LinkML draft uses qualified top-level slots
(`ConductingEquipment.Terminals`). The engine needs one mapping, and 501 ed. 2 is the
place to fix it.

A unit stated per profile has a natural form in LinkML. The CIM datatype is a LinkML
type, and a profile sets the unit on the slot, or in a class's `slot_usage`. That matches
decision 1 in section 7.

Builders live in CIMTool-Builders-Library, as now. cim-profiles keeps the post-processing
(serialise, derive the context, check the shapes against the SHACL-for-SHACL shapes,
publish versioned files) and the run-time loaders. CIM-Graph's readers, for both CIM XML
and JSON-LD, take datatypes and units from the profile's shapes. That removes the four
separate unit definitions and the 1000× difference between the two readers.

## 7. Decisions needed

In order of how much depends on them:

1. **Where the multiplier is stated: on the property (Svein today) or on the profile's
   property shape (this proposal).** The unit symbol can stay on the property, since both
   families agree on it. Experiment 1 is the argument, and so is the need to keep every
   CGMES exchange valid while distribution uses unprefixed units. A reader can support
   both during a transition: use the shape if the profile has one, otherwise the property.
2. **What "generated from LinkML" means in 501 ed. 2.** The standard should define the
   mapping, that is, which RDF a given model produces, and leave the tool open. CIMTool
   builders and LinkML generators can then both be tested against it. Experiment 6 shows
   that LinkML's generators do not meet it today.
3. **Where the true class hierarchy comes from.** A CIMTool profile lists the nearest
   selected parent, not the CIM parent. The vocabulary needs the CIM parent. It has to come
   from the whole model, not from a profile (first experiment in section 8).
4. **Dataset header layout.** The ENTSO-E draft makes the top-level node the
   `dcat:Dataset`, with the data in `@graph`. Nordic44 puts a dataset node inside `@graph`.
   The first is the standard JSON-LD pattern for describing a named graph, and is the
   better default. Readers should accept both.
5. **Whether `sh:datatype xsd:float` stays.** The CIM primitive is a 32-bit float. Writers
   that convert units produce up to 15 significant digits, which need `xsd:double`.

## 8. What would prove this wrong

Each item is an experiment with a result that would change the recommendation.

| Experiment | The design fails if |
|---|---|
| Export the whole CIM model's terms from CIMTool, with true parents | CIMTool cannot do it headless. The vocabulary layer then needs another source, such as Svein's files for CGMES. |
| Write a shapes builder; run it on CGMES equipment once that project is on CIMTool 2.3.1; compare with the official CGMES shapes and Svein's units | There are differences that are neither a defect in one side nor a recorded choice. |
| Read Nordic44 with units taken from profile shapes | Any value differs from today's reading. |
| Load the shapes of all 18 parts of `cim18v17` together and validate the IEEE 13 export | The combined shapes reject valid data, or need merge code. |
| Round trip a profile through LinkML: EA model → `linkml` builder → LinkML-to-OWL engine → builders | Any builder output differs from the direct run. Until the engine exists, the first half can be tested: the LinkML output must hold every unit, inverse and datatype of the profile. |
| Derive the context from Svein's vocabularies by query | It differs from his published context, apart from the 49 extra terms. |

## 9. What carries over from the work so far

- **Keep:** the offline document cache and loaders; the `dcat:Dataset` header reading and
  writing in CIM-Graph; the round-trip tests; the headless CIMTool run; the prototype's
  proof that the profile XML holds datatypes and fixed units.
- **Replace:** `jsonld/build.py` (types from Python annotations); the conventions YAML;
  the unit name table in `qudt.py`; the per-profile contexts.
- **Rework:** the `json-ld-vocabulary` prototype builder becomes the shapes builder. It
  already reads the right fields. It should write RDF/XML, state units on shapes, and
  stop redefining terms.
- **Fix now, whatever is decided:** the reader ignores a top-level header, so a kW file is
  read as W (briefing defect 3), and CIM XML reads CGMES values 1000× too small (defect 1).

## 10. Limits of this review

- QUDT's own schema could not be read from this session (no network access to qudt.org).
  The statement that neither placement of `qudt:hasUnit` is defined by QUDT rests on
  Svein's notes and on general knowledge, not on a check of the schema.
- The discussion in Inst4CIM-KG issue 152, a follow-up on units, was not read.
- The CGMES comparison uses name matching across two CIM namespaces. It shows that the
  units differ. It does not show a contradiction in a live store today.
- pyshacl was the only SHACL engine used. The 4 violations on Nordic44 were not checked
  against a second engine.
- Option C is not built. Section 8 lists what has to be shown before it is.
