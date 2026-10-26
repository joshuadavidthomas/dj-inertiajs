"""Rewrite a project from inertia-django to this package.

Run ``python -m django_inertia.upgrade [--diff] PATH ...``. It rewrites, in
every Python file under each path:

- imports from ``inertia`` and its modules,
- calls to the prop helpers (``defer``, ``merge``, ...) into ``Prop(...)``,
- module-level ``INERTIA_*`` settings into one ``INERTIA`` dict,
- the ``inertia`` entries in ``MIDDLEWARE``, ``INSTALLED_APPS`` and encoder paths.

Anything it cannot rewrite safely is printed with its file and line. It does
not edit templates or test assertions; ``manage.py check`` and the guide
"Upgrading from inertia-django" cover those. Requires the ``upgrade`` extra.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

HELPERS = {
    "optional",
    "lazy",
    "always",
    "defer",
    "merge",
    "deep_merge",
    "once",
    "scroll",
}
# Positional parameters after the prop value, by helper.
POSITIONAL = {"defer": ["group", "merge"], "once": ["fresh"], "scroll": ["scroll"]}
PUBLIC = {
    "InertiaResponse",
    "clear_history",
    "encrypt_history",
    "inertia",
    "location",
    "preserve_fragment",
    "render",
    "share",
}
MOVED = {
    "InertiaJsonEncoder": "django_inertia.utils",
    "InertiaMiddleware": "django_inertia.middleware",
    "InertiaTestCase": "django_inertia.test",
}
REMOVED = {
    "BaseInertiaTestCase": "Tests",
    "ClientWithLastResponse": "Tests",
    "inertia_div": "Tests",
    "inertia_page": "Tests",
    "settings": "Settings",
}
OLD_SETTINGS = {
    "INERTIA_LAYOUT": ("LAYOUT",),
    "INERTIA_VERSION": ("VERSION",),
    "INERTIA_JSON_ENCODER": ("JSON_ENCODER",),
    "INERTIA_ENCRYPT_HISTORY": ("ENCRYPT_HISTORY",),
    "INERTIA_SSR_ENABLED": ("SSR", "ENABLED"),
    "INERTIA_SSR_URL": ("SSR", "URL"),
}
STRINGS = {
    "inertia.middleware.InertiaMiddleware": "django_inertia.middleware.InertiaMiddleware",
    "inertia.utils.InertiaJsonEncoder": "django_inertia.utils.InertiaJsonEncoder",
}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox"}


@dataclass
class Report:
    path: Path
    changed: bool = False
    manual: list[str] = field(default_factory=list)


def guide(section: str) -> str:
    return f'see "{section}" in the upgrade guide'


class Upgrade(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self) -> None:
        super().__init__()
        self.manual: list[str] = []
        self.helpers: dict[str, str] = {}  # local name -> helper
        self.imported_paths: dict[str, str] = {}  # local name -> dotted path
        self.prop_imported = False
        self.installed_apps_depth = 0

    def report(self, node: cst.CSTNode, message: str) -> None:
        line = self.get_metadata(PositionProvider, node).start.line
        self.manual.append(f"line {line}: {message}")

    # Imports

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if node.module is None or isinstance(node.names, cst.ImportStar):
            return
        module = _dotted(node.module)
        for alias in node.names:
            local = _alias_name(alias)
            self.imported_paths[local] = f"{module}.{_dotted(alias.name)}"

    def leave_Import(
        self, original_node: cst.Import, updated_node: cst.Import
    ) -> cst.Import:
        for alias in original_node.names:
            if _dotted(alias.name).split(".")[0] == "inertia":
                self.report(
                    original_node,
                    f"`import {_dotted(alias.name)}` is not rewritten; import names "
                    "from django_inertia instead.",
                )
        return updated_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.BaseSmallStatement | cst.FlattenSentinel[cst.BaseSmallStatement]:
        if original_node.module is None or original_node.relative:
            return updated_node
        module = _dotted(original_node.module)
        if module != "inertia" and not module.startswith("inertia."):
            return updated_node
        if isinstance(original_node.names, cst.ImportStar):
            self.report(
                original_node,
                f"`from {module} import *` is not rewritten; import names explicitly.",
            )
            return updated_node

        targets: dict[str, list[cst.ImportAlias]] = {}
        for alias in original_node.names:
            name = _dotted(alias.name)
            if name in HELPERS:
                self.helpers[_alias_name(alias)] = name
                if not self.prop_imported:
                    self.prop_imported = True
                    targets.setdefault("django_inertia", []).append(
                        cst.ImportAlias(cst.Name("Prop"))
                    )
                continue
            if name in REMOVED:
                self.report(
                    original_node,
                    f"`{name}` was removed; {guide(REMOVED[name])}.",
                )
                continue
            if name in PUBLIC:
                new_module = "django_inertia"
            elif name in MOVED:
                new_module = MOVED[name]
            else:
                new_module = "django_" + module
                self.report(
                    original_node,
                    f"`{name}` is not public API; check that "
                    f"`from {new_module} import {name}` still works.",
                )
            targets.setdefault(new_module, []).append(
                alias.with_changes(comma=cst.MaybeSentinel.DEFAULT)
            )

        statements = [
            cst.ImportFrom(module=_attribute(new_module), names=names)
            for new_module, names in targets.items()
        ]
        if not statements:
            return cst.RemovalSentinel.REMOVE  # type: ignore[return-value]
        return cst.FlattenSentinel(statements)

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        if not updated_node.body:
            return cst.RemovalSentinel.REMOVE
        if len(original_node.body) == 1 and len(updated_node.body) > 1:
            # One old import that now comes from several modules.
            lines = [
                cst.SimpleStatementLine(
                    body=[statement.with_changes(semicolon=cst.MaybeSentinel.DEFAULT)]
                )
                for statement in updated_node.body
            ]
            lines[0] = lines[0].with_changes(leading_lines=updated_node.leading_lines)
            return cst.FlattenSentinel(lines)  # type: ignore[return-value]
        return updated_node

    # Prop helpers

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.BaseExpression:
        func = original_node.func
        if isinstance(func, cst.Name) and func.value in self.helpers:
            return self._prop_call(
                original_node, updated_node, self.helpers[func.value]
            )
        for arg in original_node.args:
            if (
                arg.keyword is not None
                and arg.keyword.value in OLD_SETTINGS
                and isinstance(func, (cst.Name, cst.Attribute))
                and _last_name(func) == "override_settings"
            ):
                self.report(
                    original_node,
                    f"override_settings({arg.keyword.value}=...) uses an old "
                    f"setting; {guide('Settings')}.",
                )
        return updated_node

    def _prop_call(
        self, original: cst.Call, updated: cst.Call, helper: str
    ) -> cst.BaseExpression:
        args = list(updated.args)
        if not args or args[0].keyword is not None or args[0].star:
            self.report(
                original,
                f"`{helper}(...)` has no plain first argument; "
                f"rewrite it as Prop(...) by hand.",
            )
            return updated
        value, rest = args[0], args[1:]
        keywords: list[cst.Arg] = []
        for index, arg in enumerate(rest):
            if arg.star == "*":
                self.report(original, f"`{helper}(*...)` is not rewritten.")
                return updated
            if arg.keyword is None and not arg.star:
                positional = POSITIONAL.get(helper, [])
                if index >= len(positional):
                    self.report(original, f"`{helper}(...)` has too many arguments.")
                    return updated
                arg = arg.with_changes(
                    keyword=cst.Name(positional[index]),
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace(""),
                    ),
                )
            keywords.append(arg)

        names = {a.keyword.value for a in keywords if a.keyword is not None}
        if any(a.star == "**" for a in keywords):
            self.report(
                original,
                f"`{helper}(..., **options)` was rewritten, but option names changed: "
                f"append is now merge, wrapper is now merge; {guide('Props')}.",
            )

        # The flag goes right after the value and takes the value's comma, so a
        # call written one argument per line stays that way.
        if isinstance(value.comma, cst.Comma):
            flag_comma: cst.Comma | cst.MaybeSentinel = value.comma
        else:
            value = value.with_changes(
                comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
            )
            flag_comma = cst.MaybeSentinel.DEFAULT

        def flag(name: str) -> cst.Arg:
            return _keyword(name, cst.Name("True")).with_changes(comma=flag_comma)

        if helper == "merge":
            keywords = [
                _rename(a, "merge") if _is_keyword(a, "append") else a for a in keywords
            ]
            if not names & {"append", "prepend", "deep_merge"}:
                keywords.insert(0, flag("merge"))
        elif helper == "scroll":
            keywords = [
                _rename(a, "merge") if _is_keyword(a, "wrapper") else a
                for a in keywords
            ]
        elif helper in ("optional", "lazy"):
            keywords.insert(0, flag("optional"))
        else:
            keywords.insert(0, flag(helper))

        if (
            keywords
            and not isinstance(keywords[0].comma, cst.Comma)
            and len(keywords) > 1
        ):
            # Only when merge's flag was inserted before the original arguments.
            keywords[0] = keywords[0].with_changes(comma=value.comma)
        if not isinstance(value.comma, cst.Comma) or not keywords:
            value = value.with_changes(comma=cst.MaybeSentinel.DEFAULT)
        return updated.with_changes(func=cst.Name("Prop"), args=[value, *keywords])

    # Strings in settings

    def visit_Assign(self, node: cst.Assign) -> None:
        if any(_target_named(t.target, "INSTALLED_APPS") for t in node.targets):
            self.installed_apps_depth += 1

    def leave_Assign(
        self, original_node: cst.Assign, updated_node: cst.Assign
    ) -> cst.Assign:
        if any(
            _target_named(t.target, "INSTALLED_APPS") for t in original_node.targets
        ):
            self.installed_apps_depth -= 1
        return updated_node

    def visit_AugAssign(self, node: cst.AugAssign) -> None:
        if _target_named(node.target, "INSTALLED_APPS"):
            self.installed_apps_depth += 1

    def leave_AugAssign(
        self, original_node: cst.AugAssign, updated_node: cst.AugAssign
    ) -> cst.AugAssign:
        if _target_named(original_node.target, "INSTALLED_APPS"):
            self.installed_apps_depth -= 1
        return updated_node

    def leave_SimpleString(
        self, original_node: cst.SimpleString, updated_node: cst.SimpleString
    ) -> cst.SimpleString:
        value = original_node.evaluated_value
        if not isinstance(value, str):
            return updated_node
        new = STRINGS.get(value)
        if value == "inertia" and self.installed_apps_depth:
            new = "django_inertia"
        if new is None:
            return updated_node
        quote = original_node.quote
        return updated_node.with_changes(
            value=f"{original_node.prefix}{quote}{new}{quote}"
        )

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        if original_node.attr.value in OLD_SETTINGS:
            self.report(
                original_node,
                f"`{original_node.attr.value}` is read here; read "
                f"settings.INERTIA instead; {guide('Settings')}.",
            )
        return updated_node

    # INERTIA_* settings

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        found: dict[str, cst.BaseExpression] = {}
        first = None
        leading: Sequence[cst.EmptyLine] = ()
        has_inertia = False
        body: list[cst.BaseStatement] = []
        for statement in updated_node.body:
            name = _assigned_name(statement)
            if name == "INERTIA":
                has_inertia = True
            if name in OLD_SETTINGS:
                assert isinstance(statement, cst.SimpleStatementLine)
                found[name] = statement.body[0].value  # type: ignore[attr-defined]
                if first is None:
                    first = len(body)
                    leading = statement.leading_lines
                continue
            body.append(statement)
        if not found:
            return updated_node
        if has_inertia:
            self.manual.append(
                "this module sets both INERTIA and INERTIA_* settings; "
                f"merge them by hand; {guide('Settings')}."
            )
            return updated_node
        assert first is not None

        code = cst.Module(body=[]).code_for_node
        top: dict[str, str] = {}
        ssr: dict[str, str] = {}
        for name, value in found.items():
            key = OLD_SETTINGS[name]
            text = code(value)
            if name == "INERTIA_JSON_ENCODER":
                text = self._encoder_path(value, text)
            (ssr if key[0] == "SSR" else top)[key[-1]] = text
        lines = ["INERTIA = {"]
        lines += [f'    "{key}": {text},' for key, text in top.items()]
        if ssr:
            lines.append('    "SSR": {')
            lines += [f'        "{key}": {text},' for key, text in ssr.items()]
            lines.append("    },")
        lines.append("}")
        statement = cst.parse_statement("\n".join(lines) + "\n")
        body.insert(first, statement.with_changes(leading_lines=leading))
        return updated_node.with_changes(body=body)

    def _encoder_path(self, value: cst.BaseExpression, text: str) -> str:
        if isinstance(value, cst.SimpleString):
            return text
        dotted = _dotted(value) if isinstance(value, (cst.Name, cst.Attribute)) else ""
        head, _, rest = dotted.partition(".")
        path = self.imported_paths.get(head)
        if path:
            return f'"{path}.{rest}"' if rest else f'"{path}"'
        if "." in dotted:
            return f'"{dotted}"'
        self.manual.append(
            f'INERTIA["JSON_ENCODER"] must be a dotted path, not {text}; '
            f"{guide('Settings')}."
        )
        return text


def upgrade_source(source: str) -> tuple[str, list[str]]:
    transformer = Upgrade()
    module = MetadataWrapper(cst.parse_module(source)).visit(transformer)
    return module.code, transformer.manual


def python_files(paths: Sequence[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_file():
            yield path
            continue
        for file in sorted(path.rglob("*.py")):
            if not SKIP_DIRS & set(file.relative_to(path).parts):
                yield file


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m django_inertia.upgrade",
        description="Rewrite a project from inertia-django to django_inertia.",
    )
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument(
        "--diff", action="store_true", help="print the changes instead of writing them"
    )
    args = parser.parse_args(argv)

    reports: list[Report] = []
    for path in python_files(args.paths):
        source = path.read_text()
        try:
            new_source, manual = upgrade_source(source)
        except cst.ParserSyntaxError as e:
            reports.append(Report(path, manual=[f"not parsed: {e.message}"]))
            continue
        report = Report(path, changed=new_source != source, manual=manual)
        reports.append(report)
        if not report.changed:
            continue
        if args.diff:
            sys.stdout.writelines(
                difflib.unified_diff(
                    source.splitlines(keepends=True),
                    new_source.splitlines(keepends=True),
                    f"a/{path}",
                    f"b/{path}",
                )
            )
        else:
            path.write_text(new_source)

    changed = [r for r in reports if r.changed]
    todo = [(r.path, m) for r in reports for m in r.manual]
    for path, message in todo:
        print(f"{path}: {message}", file=sys.stderr)
    verb = "would change" if args.diff else "changed"
    print(
        f"{len(changed)} file(s) {verb}, {len(todo)} item(s) to fix by hand. "
        "Then run `python manage.py check`.",
        file=sys.stderr,
    )
    return 0


def _dotted(node: cst.BaseExpression) -> str:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return f"{_dotted(node.value)}.{node.attr.value}"
    raise TypeError(type(node).__name__)


def _attribute(dotted: str) -> cst.Name | cst.Attribute:
    head, *rest = dotted.split(".")
    node: cst.Name | cst.Attribute = cst.Name(head)
    for part in rest:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def _alias_name(alias: cst.ImportAlias) -> str:
    if alias.asname is not None:
        return _dotted(alias.asname.name)
    return _dotted(alias.name)


def _last_name(node: cst.Name | cst.Attribute) -> str:
    return node.value if isinstance(node, cst.Name) else node.attr.value


def _target_named(target: cst.BaseExpression, name: str) -> bool:
    return isinstance(target, cst.Name) and target.value == name


def _assigned_name(statement: cst.BaseStatement) -> str | None:
    if not isinstance(statement, cst.SimpleStatementLine) or len(statement.body) != 1:
        return None
    assign = statement.body[0]
    if isinstance(assign, cst.Assign) and len(assign.targets) == 1:
        target = assign.targets[0].target
        return target.value if isinstance(target, cst.Name) else None
    return None


def _keyword(name: str, value: cst.BaseExpression) -> cst.Arg:
    return cst.Arg(
        value=value,
        keyword=cst.Name(name),
        equal=cst.AssignEqual(
            whitespace_before=cst.SimpleWhitespace(""),
            whitespace_after=cst.SimpleWhitespace(""),
        ),
    )


def _is_keyword(arg: cst.Arg, name: str) -> bool:
    return arg.keyword is not None and arg.keyword.value == name


def _rename(arg: cst.Arg, name: str) -> cst.Arg:
    return arg.with_changes(keyword=cst.Name(name))


if __name__ == "__main__":
    raise SystemExit(main())
