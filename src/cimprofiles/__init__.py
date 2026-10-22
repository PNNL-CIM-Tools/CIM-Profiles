from enum import Enum


class CIM_PROFILE(Enum):
    RC4_2021 = 'rc4_2021'
    CIMHUB_2023 = 'cimhub_2023'
    CIMHUB_2026 = 'cimhub_2026'
    CIM16V33 = 'cim16v33'
    CIM17V40 = 'cim17v40'
    CIM18GMDM = 'cim18gmdm'


# Short profile names, as used by CIMG_CIM_PROFILE and cimgraph.data_profile -> package
PROFILE_PACKAGES = {
    'cim16v33': 'cimprofiles.cim16.cim16v33',
    'cgmes_3_0_0': 'cimprofiles.cim17.cgmes_3_0_0',
    'cim17v40': 'cimprofiles.cim17.cim17v40',
    'cimhub_2023': 'cimprofiles.cim17.cimhub_2023',
    'rc4_2021': 'cimprofiles.cim17.gridappsd_rc4_2021',
    'cim18gad': 'cimprofiles.cim18.cim18gad',
    'cim18gmdm': 'cimprofiles.cim18.cim18gmdm',
    'cimhub_2026': 'cimprofiles.cim18.cimhub_2026',
}


def profile_module(name: str) -> str:
    """
    Returns the module path of a profile given by short name, optionally with a
    sub-profile: 'cimhub_2023' -> 'cimprofiles.cim17.cimhub_2023',
    'cim18gmdm.connectivity' -> 'cimprofiles.cim18.cim18gmdm.connectivity'.
    """
    short_name, dot, sub_profile = name.partition('.')
    if short_name not in PROFILE_PACKAGES:
        raise ValueError(f'Unknown CIM profile {name!r}; known profiles: '
                         f'{", ".join(PROFILE_PACKAGES)}')
    return PROFILE_PACKAGES[short_name] + dot + sub_profile
