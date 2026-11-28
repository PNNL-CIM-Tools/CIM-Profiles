import importlib.util
from pathlib import Path

import pytest

_script = Path(__file__).parents[1] / 'scripts' / 'enable_python_builders.py'
_spec = importlib.util.spec_from_file_location('enable_python_builders', _script)
enable_python_builders = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enable_python_builders)

OWL = '<rdf:RDF>\n  <rdf:Description rdf:about="#Terminal"/>\n</rdf:RDF>\n'


def test_adds_a_flag_for_each_python_builder():
    updated = enable_python_builders.enable_python_builders(OWL)
    assert updated.count('Buildlet#__init__.py"') == 1
    assert updated.count('Buildlet#cimantic-graphs.py"') == 1
    assert updated.count('Buildlet#context.jsonld"') == 1
    assert updated.endswith('</rdf:Description>\n</rdf:RDF>\n')


def test_keeps_crlf_line_endings():
    updated = enable_python_builders.enable_python_builders(OWL.replace('\n', '\r\n'))
    assert '\n' not in updated.replace('\r\n', '')


def test_is_idempotent():
    once = enable_python_builders.enable_python_builders(OWL)
    assert enable_python_builders.enable_python_builders(once) == once


def test_rejects_a_file_without_closing_tag():
    with pytest.raises(ValueError, match='closing tag'):
        enable_python_builders.enable_python_builders('<rdf:RDF>')
