# CIM-Profiles

## Tests must not depend on profile contents

Profile artifacts are regenerated all the time, and regenerating one must never change a test result.
That covers the `.owl` files, the `.py`/`__init__.py` modules generated from them, `context.jsonld`
and the other JSON-LD output, and the entries in `releases.yaml`/`merge_releases.yaml`. So a unit
test must not:

- import a profile from `src/cimprofiles` (`cimprofiles.cim18.cim18v17.metadata`,
  `cimprofiles.cim17.cgmes_3_0_0`, ...) to assert which classes, fields, enum members, namespaces,
  serialize flags or context terms it has;
- read a profile artifact (an `.owl`, generated `.py` or `context.jsonld` under `src/` or a release
  directory) and assert on what's in it;
- assert on what a release contains, or how many releases or parts there are.

Test real behavior on the immutable fixtures instead:

- the hand-crafted `test_a`/`test_b`/`test_c` profiles (`fixture_profiles.cim17.test_*`, see
  `tests/fixtures/README.md`). To cover something new, change `BuildFixtures.java` and regenerate;
  never edit the generated output by hand;
- an inline profile source in the test (like `W3C_PROFILE` in `tests/test_jsonld_build.py`) for
  what the CIMTool test schema can't produce;
- an inline release list (like `test_shared_parts_are_built_once_and_first`) for release logic.

If an existing test breaks because a profile was regenerated, the test is wrong: move it onto a
fixture. Don't update the expected values.
