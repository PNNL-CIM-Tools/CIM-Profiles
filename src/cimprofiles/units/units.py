
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import cache
from importlib import resources as impresources
from typing import Optional

from pint import Quantity, UnitRegistry

import cimprofiles.units.cim_units as cim_units
from cimprofiles.units.cim_units import UnitMultiplier, UnitSymbol

units_file = impresources.files(cim_units).joinpath('units.txt')
ureg = UnitRegistry()

# units.txt intentionally overrides several pint built-in symbols (Hz, VAr, Nm,
# bit, arcmin, ...) with CIM-specific definitions. Mute pint's "Redefining ..."
# warnings for the duration of the load only; the prior level is restored after.
_pint_log = logging.getLogger('pint.util')
_prev_level = _pint_log.level
_pint_log.setLevel(logging.ERROR)
ureg.load_definitions(units_file) # pyright: ignore[reportArgumentType]
_pint_log.setLevel(_prev_level)


class CIMUnit():
    value: Optional[float]|CIMUnit
    unit: UnitSymbol
    multiplier: UnitMultiplier

    def __pint__(self, value:float|CIMUnit, input_unit:str, input_multiplier:Optional[str]=None):

        if input_unit is None:
            input_unit = self.unit.value

        if input_multiplier is not None:
            input_unit = input_multiplier + input_unit

        if isinstance(value, CIMUnit):
            value = value.quantity.to(input_unit).magnitude

        if isinstance(value,ureg.Quantity):
            value = value.to(input_unit).magnitude

        if self.multiplier.value != 'none':
            self.quantity = ureg.Quantity(value=float(value), units=self.multiplier.value+input_unit)
            self.quantity = self.quantity.to(self.multiplier.value+self.unit.value)

        else:
            self.quantity = ureg.Quantity(value=float(value), units=input_unit)
            self.quantity = self.quantity.to(self.unit.value)

        self.value = self.quantity.magnitude

    def __repr__(self):
        return str(self.quantity)

    def __float__(self):
        return float(self.quantity.magnitude)

    def __int__(self):
        return int(self.quantity.magnitude)

    def to(self, unit:str):
        return self.quantity.to(unit).magnitude


@cache
def class_unit(unit_class: type) -> str:
    """The pint unit a CIMUnit class stores values in: its multiplier and symbol
    ('V' for Voltage, 'kW' for KiloActivePower)."""
    sample = unit_class(0)
    if sample.multiplier.value == 'none':
        return sample.unit.value
    return sample.multiplier.value + sample.unit.value


def from_unit(unit_class: type, value: float, unit: str) -> CIMUnit:
    """
    A unit_class value from a number in any pint unit of the same dimension
    ('MW', 'kV', 'mm'). Unlike the constructor's input_unit, which is a unit symbol that
    the class multiplier applies to (KiloActivePower(5, 'W') is 5 kW), `unit` here is
    the complete unit. A unit of another dimension raises pint's DimensionalityError.
    """
    return unit_class(ureg.Quantity(float(value), unit).to(class_unit(unit_class)).magnitude)
