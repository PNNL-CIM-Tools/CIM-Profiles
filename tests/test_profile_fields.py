
import pytest

from cimprofiles.dedupe_profile_fields import find_duplicates, main


def test_find_duplicates_prefers_serialized_definition():
    source = '''
class RatioTapChanger:
    TransformerEnd: Optional[TransformerEnd] = field(
        default=None,
        metadata={'inverse': 'TransformerEnd.RatioTapChanger', 'serialize': True})
    """own reference"""

    TransformerEnd: Optional[TransformerEnd] = field(
        default=None,
        metadata={'inverse': 'TransformerEnd.AdditionalRatioTapChanger', 'serialize': False})
    """inverse of a different association"""
'''
    (dup,) = find_duplicates(source)
    assert dup['kind'] == 'UML conflict'
    assert dup['keep']['serialize'] is True
    assert dup['drop'][0]['inverse'] == 'TransformerEnd.AdditionalRatioTapChanger'


EXPORTER_DUPLICATE = '''
class PhaseTapChanger:
    TransformerEnd: Optional[TransformerEnd] = field(
        default=None,
        metadata={'inverse': 'TransformerEnd.PhaseTapChanger', 'serialize': False})
    """inverse end"""

    TransformerEnd: Optional[TransformerEnd] = field(
        default=None,
        metadata={'inverse': 'TransformerEnd.PhaseTapChanger', 'serialize': True})
    """own reference"""
'''


def test_dedupe_a_profile_outside_the_package(tmp_path):
    profile = tmp_path / 'my_package' / 'my_profile'
    profile.mkdir(parents=True)
    module = profile / 'my_profile.py'
    module.write_text(EXPORTER_DUPLICATE, encoding='utf-8')
    log = str(tmp_path / 'dedupe.log')

    assert main([str(profile), '--check', '--log', log]) == 1
    assert module.read_text(encoding='utf-8') == EXPORTER_DUPLICATE   # --check only reports

    assert main([str(profile), '--log', log]) == 0
    assert find_duplicates(module.read_text(encoding='utf-8')) == []
    assert "'serialize': True" in module.read_text(encoding='utf-8')
    assert "'serialize': False" not in module.read_text(encoding='utf-8')
    assert main([str(module), '--check', '--log', log]) == 0          # a module file works too


def test_dedupe_rejects_a_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError, match='No profile module or directory'):
        main([str(tmp_path / 'missing'), '--check', '--log', str(tmp_path / 'dedupe.log')])
