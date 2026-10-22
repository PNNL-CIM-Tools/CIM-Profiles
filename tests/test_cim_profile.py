import importlib

import pytest

from cimprofiles import CIM_PROFILE, PROFILE_PACKAGES, profile_module


def test_CIM_PROFILE():
    assert len(CIM_PROFILE) == 6
    assert CIM_PROFILE.CIM17V40.value == 'cim17v40'
    assert CIM_PROFILE.CIMHUB_2023.value == 'cimhub_2023'
    assert CIM_PROFILE.CIMHUB_2026.value == 'cimhub_2026'
    assert CIM_PROFILE.RC4_2021.value == 'rc4_2021'


def test_every_profile_name_resolves_to_an_importable_package():
    for profile in CIM_PROFILE:
        importlib.import_module(profile_module(profile.value))
    for short_name in PROFILE_PACKAGES:
        importlib.import_module(profile_module(short_name))


def test_sub_profile_name_resolves():
    assert (profile_module('cim18gmdm.connectivity')
            == 'cimprofiles.cim18.cim18gmdm.connectivity')


def test_unknown_profile_name_is_rejected():
    with pytest.raises(ValueError, match='cimhub_2023'):
        profile_module('cimhub_2099')
