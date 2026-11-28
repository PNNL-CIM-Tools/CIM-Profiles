import pytest
from fixture_profiles.cim17 import test_b as cim
from fixture_profiles.cim17.test_c import KiloActivePower
from pint.errors import DimensionalityError

from cimprofiles.units import class_unit, from_unit


def test_class_unit_includes_the_class_multiplier():
    assert class_unit(cim.Voltage) == 'V'
    assert class_unit(KiloActivePower) == 'kW'


def test_from_unit_takes_a_complete_unit():
    assert from_unit(cim.Voltage, 420, 'kV').value == 420000
    assert from_unit(KiloActivePower, 5, 'MW').value == 5000      # stored in kW
    assert from_unit(KiloActivePower, 5, 'kW').value == 5
    assert from_unit(cim.Length, 12.5, 'mm').to('m') == pytest.approx(0.0125)


def test_from_unit_rejects_another_dimension():
    with pytest.raises(DimensionalityError):
        from_unit(cim.Voltage, 1, 'MW')
