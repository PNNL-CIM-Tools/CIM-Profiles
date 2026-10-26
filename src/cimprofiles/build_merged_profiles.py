"""Build pre-baked merged profile packages from merge_releases.yaml.

Run with the development dependencies installed (needs pyyaml):
    uv run python -m cimprofiles.build_merged_profiles
    uv run python -m cimprofiles.build_merged_profiles --config path/to/releases.yaml
    uv run python -m cimprofiles.build_merged_profiles --release cim18v17

``--config`` builds releases for a profile package outside this repo (e.g.
cim-vfm-profiles). Each release's ``package`` must be importable; its files are
written wherever that package lives.

Each release merges the CIMTool-generated modules listed in ``parts`` into two
committed files in its package:

- ``<name>.py``: every class of every part, merged at the source level. Each
  field, enum member, property and docstring is copied verbatim from the part
  that defines it, so the file reads like CIMTool output.
- ``__init__.py``: re-exports the merged classes, like a CIMTool init file.

Classes are merged by name across parts:

- base class: the most specific one (see ``cimprofiles.merge.most_specific_base``),
  since CIMTool drops intermediate classes a profile does not use;
- ``@stereotype`` decorators: the union; ``@dataclass``: from a definition with
  the chosen base;
- fields and enum members: the union, in first-seen order; a field defined more
  than once keeps the serialized association end, else the earliest part's;
- docstrings, CIMUnit classes and properties: the first definition. A property
  or enum value that differs between parts raises;
- a profile's own ``Identity`` class is dropped in favour of
  ``cimprofiles.identity.Identity``.

Add this to the PyPI release process for any profile listed in the config.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml

from cimprofiles.dedupe_profile_fields import field_info
from cimprofiles.merge import _topo_sort, most_specific_base

_log = logging.getLogger(__name__)

_CONFIG = Path(__file__).parent / 'merge_releases.yaml'

# Defined in every part, but not exported by CIMTool init files
_UNEXPORTED = {'CIMStereotype'}
# Imported by every part from cimprofiles, and re-exported like the CIMTool init files do
_LIBRARY_EXPORTS = {'UnitMultiplier', 'UnitSymbol'}


def _load_config(config: Path) -> list[dict]:
    with open(config) as f:
        data = yaml.safe_load(f)
    return data['releases']


def _package_dir(package: str) -> Path:
    """Where *package* lives — resolved by import, so external packages work too."""
    spec = importlib.util.find_spec(package)
    if spec is None or not spec.submodule_search_locations:
        raise FileNotFoundError(
            f'Package not importable: {package}\n'
            f'Create it and add sub-profile packages before running this script.'
        )
    return Path(next(iter(spec.submodule_search_locations)))


def _module_source(module: str) -> str:
    """Source of a generated profile module, found without importing it."""
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        raise FileNotFoundError(f'Profile module not found: {module}')
    return Path(spec.origin).read_text(encoding='utf-8')


# ── splitting a part into source segments ─────────────────────────────

def _first_line(node: ast.stmt) -> int:
    decorators = getattr(node, 'decorator_list', [])
    return min([node.lineno] + [d.lineno for d in decorators])


def _is_docstring(node: ast.stmt) -> bool:
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str))


@dataclass
class _Segment:
    """One statement with its source lines up to the next statement."""
    node: ast.stmt
    text: str
    last_line: int


def _segments(body: list[ast.stmt], lines: list[str], end: int) -> list[_Segment]:
    """
    Split *body* into segments. A segment runs up to the next statement (or line
    *end*), so it carries the blank lines after it, and the docstring following
    a field or enum member is folded into that member's segment.
    """
    starts = [_first_line(node) for node in body] + [end + 1]
    segments: list[_Segment] = []
    for index, node in enumerate(body):
        last_line = starts[index + 1] - 1
        text = '\n'.join(lines[starts[index] - 1:last_line])
        if _is_docstring(node) and index > 0 and isinstance(body[index - 1], (ast.AnnAssign, ast.Assign)):
            segments[-1].text += '\n' + text
            segments[-1].last_line = last_line
        else:
            segments.append(_Segment(node, text, last_line))
    return segments


@dataclass
class _ClassDefinition:
    """One part's definition of a class."""
    node: ast.ClassDef
    docstring: str | None
    members: list[_Segment]


def _class_definition(node: ast.ClassDef, lines: list[str], end: int) -> _ClassDefinition:
    body = _segments(node.body, lines, end)
    docstring = None
    if body and _is_docstring(body[0].node):
        docstring = body.pop(0).text
    return _ClassDefinition(node, docstring, body)


def _member_key(node: ast.stmt) -> str:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return f'field {node.target.id}'
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return f'member {node.targets[0].id}'
    if isinstance(node, ast.FunctionDef):
        return f'def {node.name}'
    return f'statement {ast.unparse(node)}'


def _base_name(node: ast.ClassDef) -> str:
    if len(node.bases) != 1:
        raise ValueError(f'Expected one base class for {node.name}, got {len(node.bases)}')
    return ast.unparse(node.bases[0])


# ── merging ────────────────────────────────────────────────────────────

def _merge_member(class_name: str, key: str, candidates: list[_Segment]) -> str:
    """Pick the source text of one member defined by several parts."""
    texts = [segment.text for segment in candidates]
    if len(set(texts)) == 1:
        return texts[0]
    first = candidates[0].node
    if isinstance(first, ast.AnnAssign):
        infos = [dict(field_info(segment.node), text=segment.text)
                 for segment in candidates if isinstance(segment.node, ast.AnnAssign)]
        if len({(info['annotation'], info['inverse']) for info in infos}) > 1:
            _log.warning('UML conflict: %s.%s defined as %s', class_name, key.split()[1],
                         sorted({f"{info['annotation']} (inverse={info['inverse']})" for info in infos}))
        # The association end that is serialized, else the earliest part's
        serialized = [info for info in infos if info['serialize'] is True]
        return (serialized or infos)[0]['text']
    # Enum values and properties must agree; docstrings and spacing may not.
    if len({ast.dump(segment.node) for segment in candidates}) > 1:
        raise ValueError(f'{class_name}: parts disagree on {key}')
    return texts[0]


def _merge_class(name: str, definitions: list[_ClassDefinition],
                 parents: dict[str, set[str]]) -> str:
    """Return the merged source of one class."""
    base = most_specific_base(name, {_base_name(d.node) for d in definitions}, parents)
    with_base = next(d for d in definitions if _base_name(d.node) == base)

    stereotypes: list[str] = []
    for definition in definitions:
        for decorator in definition.node.decorator_list:
            text = f'@{ast.unparse(decorator)}'
            if not text.startswith('@dataclass') and text not in stereotypes:
                stereotypes.append(text)
    dataclass_decorators = [f'@{ast.unparse(d)}' for d in with_base.node.decorator_list
                            if ast.unparse(d).startswith('dataclass')]

    members: dict[str, list[_Segment]] = defaultdict(list)
    for definition in definitions:
        for segment in definition.members:
            members[_member_key(segment.node)].append(segment)

    lines = stereotypes + dataclass_decorators + [f'class {name}({base}):']
    docstring = next((d.docstring for d in definitions if d.docstring), None)
    if docstring:
        lines.append(docstring)
    for key, candidates in members.items():
        lines.append(_merge_member(name, key, candidates))
    if not docstring and not members:
        lines.append('    pass')
    return '\n'.join(lines)


def _merge_assignment(name: str, candidates: list[tuple[str, str]]) -> str:
    """Module-level assignments (BASE_URI, _log) come from the first part."""
    if len({text for _part, text in candidates}) > 1:
        _log.warning('Parts disagree on %s; using %s from %s', name,
                     candidates[0][1], candidates[0][0])
    return candidates[0][1]


def merge_sources(parts: dict[str, str]) -> tuple[str, list[str]]:
    """
    Merge CIMTool-generated profile modules at the source level.

    Args:
        parts: module path -> module source, in merge order.

    Returns:
        The merged module source (without a module docstring) and the exported names.
    """
    imports: dict[tuple, str] = {}
    assignments: dict[str, list[tuple[str, str]]] = defaultdict(list)
    classes: dict[str, list[_ClassDefinition]] = defaultdict(list)

    for part, source in parts.items():
        lines = source.split('\n')
        tree = ast.parse(source)
        for segment in _segments(tree.body, lines, len(lines)):
            node = segment.node
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = frozenset(alias.name for alias in node.names)
                imports.setdefault((getattr(node, 'module', None), names), ast.unparse(node))
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                assignments[node.targets[0].id].append((part, ast.unparse(node)))
            elif isinstance(node, ast.ClassDef) and node.name == 'Identity':
                # Profiles that select the CIM Identity class redefine it; the
                # real cimprofiles.identity.Identity (uri(), uuid(), ...) is used.
                continue
            elif isinstance(node, ast.ClassDef):
                classes[node.name].append(_class_definition(node, lines, segment.last_line))
            elif not _is_docstring(node):
                raise ValueError(f'{part}: unexpected top-level statement {ast.unparse(node)!r}')

    parents = {name: {_base_name(d.node) for d in definitions}
               for name, definitions in classes.items()}
    # A class depends on its bases and on anything its decorators use
    # (e.g. CIMStereotype), so those are defined first.
    deps = {name: set(parents[name]) | {
                n.id for d in definitions for decorator in d.node.decorator_list
                for n in ast.walk(decorator) if isinstance(n, ast.Name)}
            for name, definitions in classes.items()}
    order = _topo_sort(list(classes), deps)

    sections = [
        '\n'.join(imports.values()),
        '\n'.join(_merge_assignment(name, candidates)
                  for name, candidates in assignments.items()) + '\n',
    ]
    sections += [_merge_class(name, classes[name], parents) for name in order]
    exported = ['Identity'] + sorted((set(classes) - _UNEXPORTED) | _LIBRARY_EXPORTS)
    return '\n'.join(sections), exported


# ── files ──────────────────────────────────────────────────────────────

def _module_docstring(release: dict) -> str:
    parts = '\n'.join(f'    {part}' for part in release['parts'])
    return (f"'''\n"
            f"Merged CIMantic Graphs data profile {release['package']}\n"
            f"{release.get('description', '')}\n\n"
            f"Generated by cimprofiles.build_merged_profiles from:\n{parts}\n"
            f"Do not edit by hand; re-run the builder after regenerating a part.\n"
            f"'''\n")


def _init_source(release: dict, exported: list[str]) -> str:
    module = f"{release['package']}.{release['name']}"
    imports = ''.join(f'    {name},\n' for name in exported)
    all_entries = ''.join(f"    '{name}',\n" for name in exported)
    return (f"'''\n"
            f"    Merged CIMantic Graphs data profile init file for {release['name']}\n"
            f"    Generated by cimprofiles.build_merged_profiles\n"
            f"'''\n"
            f"from {module} import (\n{imports})\n\n"
            f"__all__ = [\n{all_entries}]\n")


def build_release(release: dict) -> dict[str, str]:
    """Return {file name: content} for one release entry."""
    parts = {part: _module_source(part) for part in release['parts']}
    merged, exported = merge_sources(parts)
    return {
        f"{release['name']}.py": _module_docstring(release) + merged,
        '__init__.py': _init_source(release, exported),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Build pre-baked merged profile packages.')
    parser.add_argument('--config', type=Path, default=_CONFIG,
                        help=f'releases yaml (default: {_CONFIG.name})')
    parser.add_argument('--release', help='build only the release with this name')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    releases = _load_config(args.config)
    if args.release:
        releases = [release for release in releases if release['name'] == args.release]
        if not releases:
            parser.error(f'no release named {args.release!r} in {args.config}')

    for release in releases:
        package = release['package']
        print(f'Building {package} ...')
        package_dir = _package_dir(package)
        for file_name, content in build_release(release).items():
            (package_dir / file_name).write_text(content, encoding='utf-8')
            print(f'  wrote {package_dir / file_name}')

        # Smoke-test: the written package must be importable and expose __all__.
        for name in [m for m in sys.modules if m == package or m.startswith(package + '.')]:
            del sys.modules[name]
        mod = importlib.import_module(package)
        assert hasattr(mod, '__all__'), f'{package}.__all__ missing after write'
        print(f'  ok — {len(mod.__all__)} classes exported')


if __name__ == '__main__':
    main()
