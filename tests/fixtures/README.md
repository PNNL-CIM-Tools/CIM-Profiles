# Test fixture profiles

The tests run on three small CIMTool profiles, `test_a`, `test_b` and `test_c`, instead of the
real profiles in `src/cimprofiles`. Those change whenever an `.owl` file is regenerated or a release is
added to `merge_releases.yaml`; a test that depends on them breaks for reasons unrelated to the code.
These fixtures change only when someone deliberately regenerates them.

They are real CIMTool output: profiles of the CIMTool-Test-Project schema
(`CIM17-2_CGMES31v01_PROF-20v02_NC23v66_MS10v01_DES10v01.qea` in
[CIMTool-Builders-Library](https://github.com/AAndersn/CIMTool-Builders-Library/tree/main/builder-submissions/CIMTool-Test-Project)),
run through the cimantic-graphs builders and the same import pipeline as a real profile.

## Layout

| Path | What | Changes when |
|---|---|---|
| `cimtool/Profiles/test_*.owl` | The profiles, as the CIMTool editor saves them | Never, unless the fixtures need to cover something new |
| `cimtool/Profiles/test_*.{cimantic-graphs.py,__init__.py,context.jsonld}` | Raw CIMTool builder output | A builder changes |
| `../fixture_profiles/cim17/test_*/` | The imported packages (`fixture_profiles.cim17.test_a`, ...) the tests use | A builder or the import pipeline changes |
| `cimtool/BuildFixtures.java` | Writes the `.owl` files with the CIMTool profile API; the class lists in it are the profile definitions | |
| `cimtool/GenerateOutputs.java`, `cimtool/generate.sh` | Run the builders and the import | |

The `.owl` files contain random blank-node IDs, so `generate.sh --owl` rewrites them even when nothing
changed. The outputs generated from them do not change. Commit new `.owl` files only along with a change to
`BuildFixtures.java`.

## What each profile covers

All three use the schema's `cim` namespace `http://iec.ch/TC57/CIM-generic#`.

| | test_a: connectivity | test_b: electrical | test_c: location and datatypes |
|---|---|---|---|
| Hierarchy | Complete, IdentifiedObject → … → ACLineSegment | Leaves out PowerSystemResource, Equipment, ConductingEquipment and ACDCTerminal: `Conductor`, `Terminal` and `EnergyConsumer` are rooted at `IdentifiedObject` | Leaves out Equipment and EnergyConnection: `ConductingEquipment(PowerSystemResource)`, `EnergyConsumer(ConductingEquipment)` |
| Associations | Both ends of Terminal–ConductingEquipment, Terminal–ConnectivityNode and ACLineSegment–ACLineSegmentPhase, so CIMTool writes duplicate fields that dedupe removes | ACLineSegment–PerLengthImpedance | Only `ConductingEquipment.Terminals`, so its `Terminal.ConductingEquipment` is the unserialized end |
| Enumerations | `PhaseCode` restricted to A, B, C, ABC, N | `PhaseCode` restricted to A, B, C, AB, ABC, s1, s2 | |
| Datatypes | Voltage, Boolean, Integer | ActivePower, PerCent, Resistance, Reactance, Length, ResistancePerLength | KiloActivePower (multiplier `k`), Money (`xsd:decimal`), PU, DateTime, a compound (`StreetAddress`) |
| Extensions | None | `nc:EnergyConsumer.participationFactor`, `nc:EnergyConsumer.maxEconomicP` | `eu:IdentifiedObject.shortName` |
| Concrete | ACLineSegment, Terminal, … | ACLineSegment, EnergyConsumer, … | Not ACLineSegment or EnergyConsumer, so merging unions the `@stereotype` decorators |

Not covered, because the schema can't produce it: a profile's own `Identity` class, W3C (`dct:`) properties,
and a UML conflict (two associations that share a role name). Inline sources in the tests cover these.

## Regenerating

```bash
tests/fixtures/cimtool/generate.sh          # after changing CIMTool_plugin/*.xsl, the JSON-LD context
                                            # builder or scripts/import_cimtool_output.sh
tests/fixtures/cimtool/generate.sh --owl    # after changing BuildFixtures.java
```

Then review and commit the diff: it shows what the builder change does to real output.
`test_import_pipeline_reproduces_the_fixture_packages` fails if the imported packages are out of date.

It needs Java 11+, the CIMTool 2.3.1 CLI fat jar (`CIMTOOL_CLI`, default
`~/variable-fidelity-models/cimtool-cli.jar`) and a CIMTool-Builders-Library checkout (`CIMTOOL_BUILDERS_LIB`,
default `~/CIMTool-Builders-Library`), which provides the schema and the JSON-LD context builder. The `.qea`
schema is 50 MB, so it is not copied here. CIMTool logs hundreds of warnings while parsing it; they are
from the schema and don't affect these classes.

The CLI runs a custom `--xslt` without the TEXT post-processing that renders CIMTool's indent markup, so
`GenerateOutputs.java` registers the builders by name instead. The profile API links a class only to its
direct parent, so `BuildFixtures.java` links each class to its nearest profiled ancestor itself, as the
Eclipse editor does.
