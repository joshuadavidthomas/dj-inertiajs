"""Rewrite a project from inertia-django to this package.

Run ``python -m dj_inertiajs.upgrade [--diff] PATH ...``. It rewrites, in
every Python file under each path:

- imports from ``inertia`` and its modules,
- calls to the prop helpers (``defer``, ``merge``, ...) into ``Prop(...)``,
- calls to ``location(url)`` into ``InertiaLocation(url)``,
- ``encrypt_history(request)`` in an ``@inertia`` view into the decorator's
  ``encrypt_history=`` option,
- module-level ``INERTIA_*`` settings into one ``INERTIA`` dict,
- the ``inertia`` entries in ``MIDDLEWARE``, ``INSTALLED_APPS`` and encoder paths,
- in classes that descend from an ``inertia.test`` test case, also through
  base classes in other files among the given paths, the assertions and
  accessors that read the last response, to read it from a variable.

Anything it cannot rewrite safely is printed with its file and line. It does
not edit templates; ``manage.py check`` and the guide "Upgrading from
inertia-django" cover those. Requires the ``upgrade`` extra.
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
# Functions that took the request first and are now request.inertia methods.

PUBLIC = {"InertiaResponse", "clear_history", "inertia", "render", "share"}
MOVED = {
    "InertiaJsonEncoder": "dj_inertiajs.encoders",
    "InertiaMiddleware": "dj_inertiajs.middleware",
    "InertiaTestCase": "dj_inertiajs.test",
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
    "inertia.middleware.InertiaMiddleware": "dj_inertiajs.middleware.InertiaMiddleware",
    "inertia.utils.InertiaJsonEncoder": "dj_inertiajs.encoders.InertiaJsonEncoder",
}
# Old InertiaTestCase assertions, which now take the response first.
ASSERTIONS = {
    "assertComponentUsed": "assertComponentUsed",
    "assertHasExactProps": "assertPropsEqual",
    "assertIncludesProps": "assertPropsContain",
    "assertHasExactTemplateData": "assertTemplateDataEqual",
    "assertIncludesTemplateData": "assertTemplateDataContain",
}
# Old InertiaTestCase accessors and the expression that replaces each, given
# the response variable.
ACCESSORS = {
    "component": "{}.inertia.component",
    "props": "{}.inertia.props",
    "page": "{}.inertia.data",
    "merge_props": '{}.inertia.data["mergeProps"]',
    "deferred_props": '{}.inertia.data["deferredProps"]',
    "once_props": '{}.inertia.data["onceProps"]',
    "template_data": "{}.template_data",
    "last_response": "{}",
}
CLIENT_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox"}


@dataclass
class Report:
    path: Path
    changed: bool = False
    manual: list[str] = field(default_factory=list)


def guide(section: str) -> str:
    return f'see "{section}" in the upgrade guide'


class Imports:
    """The dotted path each imported name in one module refers to."""

    def __init__(self, module: str = "", is_package: bool = False) -> None:
        self.paths: dict[str, str] = {}
        self.package = module if is_package else module.rpartition(".")[0]

    def record_from(self, node: cst.ImportFrom) -> None:
        if isinstance(node.names, cst.ImportStar):
            return
        if node.relative:
            parts = self.package.split(".") if self.package else []
            up = len(node.relative) - 1
            if up > len(parts) or not parts:
                return
            parts = parts[: len(parts) - up]
            if node.module is not None:
                parts.append(_dotted(node.module))
            module = ".".join(parts)
        elif node.module is not None:
            module = _dotted(node.module)
        else:
            return
        for alias in node.names:
            self.paths[_alias_name(alias)] = f"{module}.{_dotted(alias.name)}"

    def record_import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = _dotted(alias.name)
            if alias.asname is not None:
                self.paths[_alias_name(alias)] = name
            else:
                head = name.split(".")[0]
                self.paths[head] = head

    def resolve(self, node: cst.BaseExpression) -> str | None:
        if not isinstance(node, (cst.Name, cst.Attribute)):
            return None
        head, _, rest = _dotted(node).partition(".")
        path = self.paths.get(head)
        if path is None:
            return None
        return f"{path}.{rest}" if rest else path


def _is_test_case_base(path: str | None, test_cases: set[str]) -> bool:
    return path is not None and (path.startswith("inertia.test.") or path in test_cases)


class ClassCollector(cst.CSTVisitor):
    """Record the resolved bases of each top-level class in one module."""

    def __init__(self, module: str, is_package: bool) -> None:
        super().__init__()
        self.module = module
        self.imports = Imports(module, is_package)
        self.classes: dict[str, list[str]] = {}
        self.depth = 0

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self.imports.record_from(node)

    def visit_Import(self, node: cst.Import) -> None:
        self.imports.record_import(node)

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        if self.depth == 0:
            bases = [self.imports.resolve(base.value) for base in node.bases]
            path = _qualify(self.module, node.name.value)
            self.classes[path] = [b for b in bases if b is not None]
            self.imports.paths[node.name.value] = path
        self.depth += 1

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self.depth -= 1

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        return False


def find_test_cases(modules: dict[str, tuple[cst.Module, bool]]) -> set[str]:
    """Return the dotted paths of every class that descends from an
    ``inertia.test`` test case, following bases across the given modules."""
    classes: dict[str, list[str]] = {}
    for module, (tree, is_package) in modules.items():
        collector = ClassCollector(module, is_package)
        tree.visit(collector)
        classes.update(collector.classes)
    test_cases: set[str] = set()
    while True:
        found = {
            path
            for path, bases in classes.items()
            if path not in test_cases
            and any(_is_test_case_base(base, test_cases) for base in bases)
        }
        if not found:
            return test_cases
        test_cases |= found


def module_name(path: Path) -> tuple[str, bool]:
    """The dotted module name of a file and whether it is a package, found by
    walking up through directories that contain ``__init__.py``."""
    path = path.resolve()
    is_package = path.stem == "__init__"
    parts = [] if is_package else [path.stem]
    directory = path.parent
    while (directory / "__init__.py").exists():
        parts.insert(0, directory.name)
        directory = directory.parent
    return ".".join(parts), is_package


class Upgrade(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        module: str = "",
        is_package: bool = False,
        test_cases: set[str] | None = None,
    ) -> None:
        super().__init__()
        self.module = module
        self.manual: list[str] = []
        self.helpers: dict[str, str] = {}  # local name -> helper
        self.preserve_names: set[str] = set()  # local names of preserve_fragment
        self.location_names: set[str] = set()  # local names of location
        self.called_location: set[int] = set()
        self.location_imported = False
        self.rewritten_calls: set[int] = set()  # ids of the Names they call
        self.encrypt_names: set[str] = set()  # local names of encrypt_history
        self.decorator_names: set[str] = set()  # local names of @inertia
        # Per function: whether it is an @inertia view, and the
        # encrypt_history value moved out of its body.
        self.inertia_views: list[bool] = []
        self.encrypt_values: list[cst.BaseExpression | None] = []
        self.moved_statements: set[int] = set()
        self.called_encrypt: set[int] = set()
        self.imports = Imports(module, is_package)
        # Dotted paths of test case classes, from other modules and this one.
        self.test_case_paths = set(test_cases or ())
        self.class_depth = 0
        self.prop_imported = False
        self.installed_apps_depth = 0
        self.in_test_case: list[bool] = []
        # Per function in a test case: the variable holding the last
        # response, and whether the function uses the old test API at all.
        self.responses: list[str | None] = []
        self.uses_old_api: list[bool] = []
        # Per function: whether it is a test case method, or nested in one.
        self.test_methods: list[bool] = []

    def report(self, node: cst.CSTNode, message: str) -> None:
        line = self.get_metadata(PositionProvider, node).start.line
        self.manual.append(f"line {line}: {message}")

    # Imports

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self.imports.record_from(node)

    def visit_Import(self, node: cst.Import) -> None:
        self.imports.record_import(node)

    def leave_Import(
        self, original_node: cst.Import, updated_node: cst.Import
    ) -> cst.Import:
        for alias in original_node.names:
            if _dotted(alias.name).split(".")[0] == "inertia":
                self.report(
                    original_node,
                    f"`import {_dotted(alias.name)}` is not rewritten; import names "
                    "from dj_inertiajs instead.",
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
                    targets.setdefault("dj_inertiajs", []).append(
                        cst.ImportAlias(cst.Name("Prop"))
                    )
                continue
            if name == "location":
                self.location_names.add(_alias_name(alias))
                if not self.location_imported:
                    self.location_imported = True
                    targets.setdefault("dj_inertiajs", []).append(
                        cst.ImportAlias(cst.Name("InertiaLocation"))
                    )
                continue
            if name == "preserve_fragment":
                self.preserve_names.add(_alias_name(alias))
                continue
            if name == "encrypt_history":
                self.encrypt_names.add(_alias_name(alias))
                continue
            if name == "inertia":
                self.decorator_names.add(_alias_name(alias))
            if name in REMOVED:
                self.report(
                    original_node,
                    f"`{name}` was removed; {guide(REMOVED[name])}.",
                )
                continue
            if name in PUBLIC:
                new_module = "dj_inertiajs"
            elif name in MOVED:
                new_module = MOVED[name]
            else:
                # Not public API, and the modules were reorganized: leave the
                # import as it is, so it fails loudly until it is replaced.
                new_module = module
                self.report(
                    original_node,
                    f"`{name}` from `{module}` is not public API and has no "
                    "replacement here; remove the import or rewrite the code "
                    "that uses it.",
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

    # Test assertions

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        is_test_case = any(
            _is_test_case_base(self.imports.resolve(base.value), self.test_case_paths)
            for base in node.bases
        )
        if self.class_depth == 0:
            path = _qualify(self.module, node.name.value)
            self.imports.paths[node.name.value] = path
            if is_test_case:
                self.test_case_paths.add(path)
        self.class_depth += 1
        self.in_test_case.append(is_test_case)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        self.class_depth -= 1
        self.in_test_case.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        in_test_case = bool(self.in_test_case) and self.in_test_case[-1]
        finder = OldTestApiFinder()
        if in_test_case:
            node.body.visit(finder)
        self.responses.append(None)
        self.uses_old_api.append(finder.found)
        self.test_methods.append(
            in_test_case or (bool(self.test_methods) and self.test_methods[-1])
        )
        self.inertia_views.append(
            any(self._is_inertia_decorator(d) for d in node.decorators)
        )
        self.encrypt_values.append(None)
        # A nested class or function is not part of this test case's scope.
        self.in_test_case.append(False)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        self.in_test_case.pop()
        self.responses.pop()
        self.uses_old_api.pop()
        self.test_methods.pop()
        self.inertia_views.pop()
        value = self.encrypt_values.pop()
        if value is None:
            return updated_node
        decorators = [
            d.with_changes(decorator=_add_arg(d.decorator, "encrypt_history", value))  # type: ignore[arg-type]
            if self._is_inertia_decorator(d)
            else d
            for d in updated_node.decorators
        ]
        return updated_node.with_changes(decorators=decorators)

    def _is_inertia_decorator(self, decorator: cst.Decorator) -> bool:
        node = decorator.decorator
        return (
            isinstance(node, cst.Call)
            and isinstance(node.func, cst.Name)
            and node.func.value in self.decorator_names
        )

    def visit_SimpleStatementLine(self, node: cst.SimpleStatementLine) -> None:
        # A bare encrypt_history(request[, value]) in an @inertia view moves
        # to the decorator.
        if not (self.inertia_views and self.inertia_views[-1]):
            return
        if len(node.body) != 1 or not isinstance(node.body[0], cst.Expr):
            return
        call = node.body[0].value
        if not (
            isinstance(call, cst.Call)
            and isinstance(call.func, cst.Name)
            and call.func.value in self.encrypt_names
            and 1 <= len(call.args) <= 2
            and all(a.keyword is None and not a.star for a in call.args)
        ):
            return
        self.encrypt_values[-1] = (
            call.args[1].value if len(call.args) == 2 else cst.Name("True")
        )
        self.moved_statements.add(id(node))
        self.rewritten_calls.add(id(call.func))

    def _response(self, node: cst.CSTNode, name: str) -> str | None:
        response = self.responses[-1] if self.responses else None
        if response is None:
            self.report(
                node,
                f"`self.{name}` needs a response, but no request comes before it "
                f"in this method; pass the response by hand; {guide('Tests')}.",
            )
        return response

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        if id(original_node) in self.moved_statements:
            return cst.RemovalSentinel.REMOVE
        if not updated_node.body:
            return cst.RemovalSentinel.REMOVE
        if self.uses_old_api and self.uses_old_api[-1] and len(original_node.body) == 1:
            statement = original_node.body[0]
            if isinstance(statement, cst.Expr) and _is_client_call(statement.value):
                # The old API read the last response implicitly; keep it.
                self.responses[-1] = "response"
                return updated_node.with_changes(
                    body=[
                        cst.Assign(
                            targets=[cst.AssignTarget(cst.Name("response"))],
                            value=updated_node.body[0].value,  # type: ignore[attr-defined]
                        )
                    ]
                )
            if (
                isinstance(statement, cst.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0].target, cst.Name)
                and _is_client_call(statement.value)
            ):
                self.responses[-1] = statement.targets[0].target.value
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
        if self.uses_old_api and self.uses_old_api[-1] and _is_self_call(func):
            assert isinstance(func, cst.Attribute)
            name = func.attr.value
            if name in ASSERTIONS and _positional_count(original_node) == 1:
                response = self._response(original_node, name)
                if response is None:
                    return updated_node
                first = cst.Arg(
                    cst.Name(response),
                    comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" ")),
                )
                func = updated_node.func.with_changes(attr=cst.Name(ASSERTIONS[name]))
                return updated_node.with_changes(
                    func=func, args=[first, *updated_node.args]
                )
            if name in ACCESSORS and not original_node.args:
                response = self._response(original_node, f"{name}()")
                if response is None:
                    return updated_node
                return cst.parse_expression(ACCESSORS[name].format(response))
            if name == "assertJSONResponse":
                self.report(
                    original_node,
                    "`assertJSONResponse` was removed; compare `response.json()` "
                    f"instead; {guide('Tests')}.",
                )
        if (
            isinstance(func, cst.Name)
            and func.value in self.encrypt_names
            and id(func) not in self.rewritten_calls
        ):
            self.rewritten_calls.add(id(func))
            self.report(
                original_node,
                "`encrypt_history(...)` is now an option: "
                '`@inertia("...", encrypt_history=True)`, `render(..., '
                "encrypt_history=True)` or `encrypt_history = True` on a "
                f"class-based view; {guide('History encryption')}.",
            )
            return updated_node
        if (
            self.test_methods
            and self.test_methods[-1]
            and isinstance(func, cst.Attribute)
            and func.attr.value in CLIENT_METHODS
            and isinstance(func.value, cst.Attribute)
            and func.value.attr.value == "client"
            and _is_self(func.value.value)
        ):
            # The old self.client made full page loads; self.client now makes
            # Inertia visits.
            return _add_arg(updated_node, "inertia", cst.Name("False"))
        if isinstance(func, cst.Name) and func.value in self.location_names:
            return updated_node.with_changes(func=cst.Name("InertiaLocation"))
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

    def visit_Call(self, node: cst.Call) -> None:
        if isinstance(node.func, cst.Name) and node.func.value in self.location_names:
            self.called_location.add(id(node.func))
        if isinstance(node.func, cst.Name) and node.func.value in self.encrypt_names:
            self.called_encrypt.add(id(node.func))

    def visit_Name(self, node: cst.Name) -> None:
        if node.value in self.location_names and id(node) not in self.called_location:
            self.report(
                node,
                f"`{node.value}` is used without being called; `location(url)` "
                f"is now `InertiaLocation(url)`; {guide('Redirects')}.",
            )
        if node.value in self.encrypt_names and id(node) not in self.called_encrypt:
            self.report(
                node,
                "`encrypt_history` is used without being called; it is now an "
                f"option of @inertia, render() and the views; {guide('History encryption')}.",
            )
        if node.value in self.preserve_names:
            self.report(
                node,
                "`preserve_fragment(request)` is replaced by an option of the "
                "redirect: `return redirect(..., preserve_fragment=True)`, with "
                f"`redirect` from dj_inertiajs; {guide('Redirects')}.",
            )

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
            new = "dj_inertiajs"
        if new is None:
            return updated_node
        quote = original_node.quote
        return updated_node.with_changes(
            value=f"{original_node.prefix}{quote}{new}{quote}"
        )

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        if (
            self.test_methods
            and self.test_methods[-1]
            and original_node.attr.value == "inertia"
            and _is_self(original_node.value)
        ):
            # The old test case's Inertia client is now self.client.
            return updated_node.with_changes(attr=cst.Name("client"))
        if (
            self.uses_old_api
            and self.uses_old_api[-1]
            and original_node.attr.value == "last_response"
            and _is_self_client(original_node.value)
        ):
            response = self._response(original_node, "last_response")
            if response is not None:
                return cst.Name(response)
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
        path = self.imports.resolve(value)
        if path is None and isinstance(value, cst.Attribute):
            path = _dotted(value)
        if path is not None:
            return f'"{path}"'
        self.manual.append(
            f'INERTIA["JSON_ENCODER"] must be a dotted path, not {text}; '
            f"{guide('Settings')}."
        )
        return text


class OldTestApiFinder(cst.CSTVisitor):
    """Find uses of the old InertiaTestCase API, which reads the last response."""

    def __init__(self) -> None:
        super().__init__()
        self.found = False

    def visit_Call(self, node: cst.Call) -> None:
        if not _is_self_call(node.func):
            return
        assert isinstance(node.func, cst.Attribute)
        name = node.func.attr.value
        if (name in ASSERTIONS and _positional_count(node) == 1) or (
            name in ACCESSORS and not node.args
        ):
            self.found = True

    def visit_Attribute(self, node: cst.Attribute) -> None:
        if node.attr.value == "last_response" and _is_self_client(node.value):
            self.found = True


def upgrade_source(
    source: str | cst.Module,
    module: str = "",
    is_package: bool = False,
    test_cases: set[str] | None = None,
) -> tuple[str, list[str]]:
    tree = cst.parse_module(source) if isinstance(source, str) else source
    transformer = Upgrade(module, is_package, test_cases)
    return MetadataWrapper(tree).visit(transformer).code, transformer.manual


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
        prog="python -m dj_inertiajs.upgrade",
        description="Rewrite a project from inertia-django to dj_inertiajs.",
    )
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument(
        "--diff", action="store_true", help="print the changes instead of writing them"
    )
    args = parser.parse_args(argv)

    reports: list[Report] = []
    parsed: dict[Path, tuple[str, cst.Module, str, bool]] = {}
    for path in python_files(args.paths):
        source = path.read_text()
        try:
            tree = cst.parse_module(source)
        except cst.ParserSyntaxError as e:
            reports.append(Report(path, manual=[f"not parsed: {e.message}"]))
            continue
        parsed[path] = (source, tree, *module_name(path))
    # Test cases may inherit from a base class in another file, so find them
    # all before rewriting any file.
    test_cases = find_test_cases(
        {module: (tree, is_package) for _, tree, module, is_package in parsed.values()}
    )

    for path, (source, tree, module, is_package) in parsed.items():
        new_source, manual = upgrade_source(tree, module, is_package, test_cases)
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


def _qualify(module: str, name: str) -> str:
    return f"{module}.{name}" if module else name


def _is_self(node: cst.BaseExpression) -> bool:
    return isinstance(node, cst.Name) and node.value == "self"


def _is_self_call(func: cst.BaseExpression) -> bool:
    return isinstance(func, cst.Attribute) and _is_self(func.value)


def _is_self_client(node: cst.BaseExpression) -> bool:
    return (
        isinstance(node, cst.Attribute)
        and _is_self(node.value)
        and node.attr.value in ("client", "inertia")
    )


def _is_client_call(node: cst.BaseExpression) -> bool:
    return (
        isinstance(node, cst.Call)
        and isinstance(node.func, cst.Attribute)
        and node.func.attr.value in CLIENT_METHODS
        and _is_self_client(node.func.value)
    )


def _positional_count(call: cst.Call) -> int:
    return sum(1 for arg in call.args if arg.keyword is None and not arg.star)


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


def _add_arg(call: cst.Call, name: str, value: cst.BaseExpression) -> cst.Call:
    args = list(call.args)
    new = _keyword(name, value)
    if args and isinstance(args[-1].comma, cst.Comma):
        # A trailing comma means one argument per line: the new argument
        # goes on its own line, indented like the first, and keeps the
        # trailing comma.
        new = new.with_changes(comma=args[-1].comma)
        args[-1] = args[-1].with_changes(
            comma=cst.Comma(whitespace_after=call.whitespace_before_args)
        )
    elif args:
        args[-1] = args[-1].with_changes(
            comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
        )
    return call.with_changes(args=[*args, new])


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
