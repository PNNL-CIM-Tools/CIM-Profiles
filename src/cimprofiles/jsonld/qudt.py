"""QUDT unit names <-> pint unit strings understood by CIMUnit.

Vocabularies name each property's unit with a QUDT IRI (``qudt:hasUnit unit:KiloV``).
CIMUnit converts with pint, so each QUDT local name maps to a pint unit string from
``cimprofiles/units/cim_units/units.txt`` (CIM UnitSymbol spellings where they exist).

The table is explicit on purpose: an unknown unit is an error, never a guess. Names
marked "CGMES" or "not in QUDT" follow the QUDT naming pattern but are not defined by
QUDT itself; the CGMES vocabularies use the first, our per-km conventions the second.
"""
from __future__ import annotations

QUDT_UNIT_NAMESPACE = 'http://qudt.org/vocab/unit/'

QUDT_UNITS = {
    # time
    'SEC': 's', 'MIN': 'min', 'HR': 'h',
    # power and energy
    'W': 'W', 'KiloW': 'kW', 'MegaW': 'MW',
    'V-A': 'VA', 'KiloV-A': 'kVA', 'MegaV-A': 'MVA',
    'V-A_Reactive': 'VAr', 'KiloV-A_Reactive': 'kVAr', 'MegaV-A_Reactive': 'MVAr',
    'W-HR': 'Wh', 'KiloW-HR': 'kWh', 'MegaW-HR': 'MWh',
    'J': 'J',
    'W-PER-SEC': 'WPers',                      # CGMES
    'W-PER-A': 'WPerA', 'MegaW-PER-A': 'MWPerA',  # CGMES
    'MegaW-PER-HZ': 'MWPerHz',                 # CGMES
    'W-PER-M2': 'WPerm2',
    # voltage and current
    'V': 'V', 'KiloV': 'kV', 'MegaV': 'MV', 'A': 'A',
    'V-PER-V-A_Reactive': 'VPerVAr', 'KiloV-PER-V-A_Reactive': 'kVPerVAr',  # CGMES
    # impedance and admittance
    'OHM': 'ohm', 'OHM-PER-M': 'ohmPerm', 'S': 'S', 'S-PER-M': 'SPerm',
    'FARAD': 'F', 'FARAD-PER-M': 'FPerm', 'H': 'H', 'H-PER-M': 'HPerm',
    'OHM-PER-KiloM': 'ohm/km', 'MicroFARAD-PER-KiloM': 'uF/km',
    'MicroS-PER-KiloM': 'uS/km', 'MilliH-PER-KiloM': 'mH/km',  # not in QUDT
    # frequency and angle; units.txt defines Hz as a rotation rate, so 1 rev/s is 1 Hz
    'HZ': 'Hz', 'REV-PER-SEC': 'Hz', 'DEG': 'deg', 'RAD': 'rad',
    # length, area, volume, flow
    'M': 'm', 'MilliM': 'mm', 'KiloM': 'km', 'M2': 'm2', 'M3': 'm3',
    'M-PER-SEC': 'mPers', 'M3-PER-SEC': 'm3Pers',
    # mechanical and thermal
    'DEG_C': 'degC', 'PA': 'Pa', 'N': 'N', 'NanoT': 'nT',
    'GM': 'g', 'KiloGM': 'kg', 'KiloGM-PER-M': 'kgPerm', 'KiloGM-PER-M3': 'kgPerm3',
    'KiloGM-PER-J': 'kgPerJ',
    # dimensionless: CIM PerCent values are already percentages (UnitSymbol.none)
    'UNITLESS': 'none', 'PERCENT': 'none',
}

# QUDT names that share a pint unit with a preferred name; read-only aliases
_READ_ONLY_NAMES = {'REV-PER-SEC', 'PERCENT'}
_QUDT_NAMES = {pint: name for name, pint in QUDT_UNITS.items() if name not in _READ_ONLY_NAMES}


def pint_unit(qudt_name: str) -> str:
    """The pint unit string for a QUDT unit local name (e.g. 'KiloV' -> 'kV')."""
    if qudt_name not in QUDT_UNITS:
        raise KeyError(f'QUDT unit {qudt_name!r} has no CIMUnit equivalent; add it to '
                       f'cimprofiles.jsonld.qudt.QUDT_UNITS')
    return QUDT_UNITS[qudt_name]


def qudt_name(pint_unit_text: str) -> str:
    """The QUDT unit local name for a pint unit string (e.g. 'kV' -> 'KiloV')."""
    if pint_unit_text not in _QUDT_NAMES:
        raise KeyError(f'Unit {pint_unit_text!r} has no QUDT name; add it to '
                       f'cimprofiles.jsonld.qudt.QUDT_UNITS')
    return _QUDT_NAMES[pint_unit_text]
