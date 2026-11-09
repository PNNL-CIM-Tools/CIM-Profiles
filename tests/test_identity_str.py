"""Identity.__str__ builds its JSON once (cim-graph RELEASE_1_0_PLAN 2.14)."""
import json

import cimprofiles.cim17.cimhub_2023 as cim


def test_str_is_valid_json_for_any_name():
    line = cim.ACLineSegment(name='Line "[1]" {a}: 12.47kV', length=cim.Length(1, 'km'))
    terminal = cim.Terminal(name='t1')
    line.Terminals.append(terminal)

    dump = json.loads(line.__str__())

    assert dump['name'] == 'Line "[1]" {a}: 12.47kV'
    assert dump['length'] == '1000.0'
    assert dump['Terminals'] == [{'@id': terminal.uri(), '@type': 'Terminal'}]


def test_str_use_names_and_show_empty():
    line = cim.ACLineSegment(name='line "a"')
    terminal = cim.Terminal(name='t1', ConductingEquipment=line)

    assert json.loads(terminal.__str__(use_names=True))['ConductingEquipment'] == 'line "a"'
    assert 'description' not in json.loads(terminal.__str__())
    assert json.loads(terminal.__str__(show_empty=True))['description'] is None
