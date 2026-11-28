"""Identity.__str__ builds its JSON once (cim-graph RELEASE_1_0_PLAN 2.14)."""
import json

from fixture_profiles.cim17 import test_a as cim


def test_str_is_valid_json_for_any_name():
    line = cim.ACLineSegment(name='Line "[1]" {a}: 12.47kV')
    terminal = cim.Terminal(name='t1')
    line.Terminals.append(terminal)

    dump = json.loads(line.__str__())

    assert dump['name'] == 'Line "[1]" {a}: 12.47kV'
    assert dump['Terminals'] == [{'@id': terminal.uri(), '@type': 'Terminal'}]


def test_str_writes_units_in_base_si():
    voltage = cim.BaseVoltage(nominalVoltage=cim.Voltage(12.47, 'kV'))
    assert json.loads(voltage.__str__())['nominalVoltage'] == '12470.0'


def test_str_use_names_and_show_empty():
    line = cim.ACLineSegment(name='line "a"')
    terminal = cim.Terminal(name='t1', ConductingEquipment=line)

    assert json.loads(terminal.__str__(use_names=True))['ConductingEquipment'] == 'line "a"'
    assert 'description' not in json.loads(terminal.__str__())
    assert json.loads(terminal.__str__(show_empty=True))['description'] is None
