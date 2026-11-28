import pytest

from cimprofiles import PROFILE_PACKAGES, profile_module


def test_sub_profile_name_resolves(monkeypatch):
    monkeypatch.setitem(PROFILE_PACKAGES, 'fixture', 'fixture_profiles.cim17')
    assert profile_module('fixture.test_a') == 'fixture_profiles.cim17.test_a'


def test_unknown_profile_name_is_rejected():
    with pytest.raises(ValueError, match="Unknown CIM profile 'test_z'"):
        profile_module('test_z')
