
import pytest

from cimprofiles import profile_module


def test_sub_profile_name_resolves():
    assert (profile_module('cim18gmdm.connectivity')
            == 'cimprofiles.cim18.cim18gmdm.connectivity')


def test_unknown_profile_name_is_rejected():
    with pytest.raises(ValueError, match='cimhub_2023'):
        profile_module('cimhub_2099')
