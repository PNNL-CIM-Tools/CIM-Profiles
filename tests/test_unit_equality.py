
import pytest
from fixture_profiles.cim17 import test_a
from fixture_profiles.cim17 import test_b as cim


def test_units_compare_by_quantity():
    assert cim.Voltage(12470) == cim.Voltage(12470)
    assert cim.Voltage(4.16, 'kV') == cim.Voltage(4160, 'V')
    assert cim.Voltage(12470) != cim.Voltage(4160)
    assert cim.Voltage(1) != cim.Resistance(1)      # another dimension


def test_units_from_two_profiles_compare_by_quantity():
    assert test_a.Voltage(12470) == cim.Voltage(12.47, 'kV')


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
        hash(test_a.Voltage(1))


