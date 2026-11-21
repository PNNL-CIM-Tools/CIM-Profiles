import ast
from pathlib import Path

import pytest

import cimprofiles.cim17.cgmes_3_0_0 as cgmes
import cimprofiles.cim17.cim17v40 as cim
from cimprofiles.dedupe_profile_fields import PROFILE_ROOT


def test_units_compare_by_quantity():
    assert cim.Voltage(12470) == cim.Voltage(12470)
    assert cim.Voltage(4.16, 'kV') == cim.Voltage(4160, 'V')
    assert cim.KiloActivePower(5) == cim.ActivePower(5000)
    assert cim.Voltage(12470) != cim.Voltage(4160)
    assert cim.Voltage(1) != cim.Resistance(1)      # another dimension


def test_units_from_two_profiles_compare_by_quantity():
    assert cim.Voltage(12470) == cgmes.Voltage(12.47, 'kV')


@pytest.mark.parametrize('number', [12470, 12470.0])
def test_comparing_with_a_number_raises(number):
    voltage = cim.Voltage(12470)
    with pytest.raises(TypeError, match=r"\.to\(unit\) or float\(\)"):
        voltage == number
    with pytest.raises(TypeError):
        voltage != number
    with pytest.raises(TypeError):
        number == voltage
    assert voltage.to('V') == number
    assert float(voltage) == number


@pytest.mark.parametrize('other', [None, 'x', []])
def test_comparing_with_other_types_is_unequal(other):
    assert cim.Voltage(12470) != other
    assert not cim.Voltage(12470) == other


def test_units_are_unhashable():
    with pytest.raises(TypeError):
        hash(cgmes.Voltage(1))


def _cim_unit_dataclasses_with_generated_eq(path: Path) -> list[str]:
    """CIMUnit subclasses whose @dataclass generates an __eq__, hiding CIMUnit's."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(isinstance(base, ast.Name) and base.id == 'CIMUnit' for base in node.bases):
            continue
        for decorator in node.decorator_list:
            if not ast.unparse(decorator).startswith('dataclass'):
                continue
            keywords = decorator.keywords if isinstance(decorator, ast.Call) else []
            if not any(k.arg == 'eq' and ast.unparse(k.value) == 'False' for k in keywords):
                found.append(f'{path.relative_to(PROFILE_ROOT)} {node.name}')
    return found


def test_profile_units_inherit_cim_unit_equality():
    """Generated CIMUnit subclasses must use @dataclass(eq=False)."""
    found = []
    for path in sorted(PROFILE_ROOT.rglob('*.py')):
        found.extend(_cim_unit_dataclasses_with_generated_eq(path))
    assert found == []
