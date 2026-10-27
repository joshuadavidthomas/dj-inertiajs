from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from inspect import isawaitable
from typing import Any

from asgiref.sync import async_to_sync

from .request import InertiaDetails

__all__ = ["Prop", "prop"]

MergeTarget = bool | str | list[str]
SCROLL_KEYS = ("pageName", "previousPage", "nextPage", "currentPage")


class Prop:
    """A prop value plus the Inertia options that control when and how it loads.

    ``value`` may be a plain value or a callable, which is called at render
    time and only when the prop is sent. An ``async def`` callable is
    awaited, in sync and async views alike.

    Loading, at most one of:
        ``optional``: skipped on the first load; sent only when a partial
        reload asks for it.
        ``defer``: skipped on the first load; the client fetches it right
        after, together with the other props in the same ``group``.
        ``always``: sent even when a partial reload asks for other props.

    Merging into the client's existing value:
        ``merge``: append. ``True`` for the prop itself, or a path or list of
        paths inside it, such as ``"items"``.
        ``prepend``: like ``merge``, but prepends.
        ``deep_merge``: merge nested objects and arrays recursively.
        ``match_on``: paths of keys that identify records when merging.
        ``scroll``: infinite-scroll pagination metadata with ``pageName``,
        ``previousPage``, ``nextPage`` and ``currentPage``. Implies ``merge``.

    Caching on the client:
        ``once``: resolved once, then kept by the client across visits.
        ``key``: the cache key, by default the prop's path.
        ``expires_at``: a datetime, a timedelta, or seconds from now.
        ``fresh``: resolve on every request even if the client has it.

    ``rescue``: with ``defer``, an exception while resolving omits the prop
    and reports it to the client instead of failing the request.
    """

    def __init__(
        self,
        value: Any,
        *,
        optional: bool = False,
        defer: bool = False,
        group: str = "default",
        always: bool = False,
        merge: MergeTarget = False,
        prepend: MergeTarget = False,
        deep_merge: bool = False,
        match_on: str | list[str] | None = None,
        scroll: dict[str, Any] | None = None,
        once: bool = False,
        key: str | None = None,
        expires_at: datetime | timedelta | int | float | None = None,
        fresh: bool = False,
        rescue: bool = False,
    ) -> None:
        if optional + defer + always > 1:
            raise ValueError("Use at most one of optional, defer and always.")
        if group != "default" and not defer:
            raise ValueError("group requires defer=True.")
        if rescue and not defer:
            raise ValueError("rescue requires defer=True.")
        if merge is not False and prepend is not False:
            raise ValueError("merge and prepend cannot both be set.")
        if deep_merge and (merge is not False or prepend is not False):
            raise ValueError("deep_merge cannot be combined with merge or prepend.")
        if scroll is not None:
            missing = [k for k in SCROLL_KEYS if k not in scroll]
            if missing:
                raise ValueError(f"scroll is missing {', '.join(missing)}.")
            if prepend is not False or deep_merge:
                raise ValueError(
                    "scroll cannot be combined with prepend or deep_merge."
                )
            scroll = {k: scroll[k] for k in SCROLL_KEYS}
            merge = merge or True
        if match_on and merge is False and prepend is False and not deep_merge:
            raise ValueError("match_on requires merge, prepend, deep_merge or scroll.")
        if (key is not None or expires_at is not None or fresh) and not once:
            raise ValueError("key, expires_at and fresh require once=True.")

        self.value = value
        self.optional = optional
        self.defer = defer
        self.group = group
        self.always = always
        self.merge = merge
        self.prepend = prepend
        self.deep_merge = deep_merge
        self.match_on = [match_on] if isinstance(match_on, str) else match_on or []
        self.scroll = scroll
        self.once = once
        self.key = key
        self.expires_at = expires_at
        self.fresh = fresh
        self.rescue = rescue

    def __repr__(self) -> str:
        return f"Prop({self.value!r})"

    def resolve(self) -> Any:
        return resolve_value(self.value)

    @property
    def skipped_on_first_load(self) -> bool:
        return self.optional or self.defer

    @property
    def merges(self) -> bool:
        return self.merge is not False or self.prepend is not False or self.deep_merge

    def merge_paths(self, root: str, prepend: bool = False) -> list[str]:
        target = self.prepend if prepend else self.merge
        if target is True:
            return [root]
        if target is False:
            return []
        paths = [target] if isinstance(target, str) else target
        return [f"{root}.{path}" for path in paths]

    def once_key(self, path: str) -> str:
        return self.key or path

    def once_expires_at(self) -> int | None:
        value = self.expires_at
        if value is None:
            return None
        if isinstance(value, timedelta):
            value = datetime.now(timezone.utc) + value
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return int(value.timestamp() * 1000)
        return int((datetime.now(timezone.utc).timestamp() + value) * 1000)


def resolve_value(value: Any) -> Any:
    """Call a callable prop value, awaiting it if it returns an awaitable."""
    if not callable(value):
        return value
    result = value()
    if isawaitable(result):
        return async_to_sync(_await)(result)
    return result


async def _await(awaitable: Awaitable[Any]) -> Any:
    return await awaitable


SKIP_PROP = object()


class PropsResolver:
    """Resolve props once and collect Inertia v3 metadata by dotted path."""

    def __init__(self, request: InertiaDetails, component: str, props: dict[str, Any]):
        self.request = request
        self.component = component
        self.props = props
        self.metadata: dict[str, Any] = {
            "deferredProps": {},
            "mergeProps": [],
            "prependProps": [],
            "deepMergeProps": [],
            "matchPropsOn": [],
            "scrollProps": {},
            "onceProps": {},
            "rescuedProps": [],
        }

    def resolve(self) -> tuple[dict[str, Any], dict[str, Any]]:
        resolved = self._resolve_mapping(self.props)
        return resolved, {key: value for key, value in self.metadata.items() if value}

    def _resolve_mapping(
        self, props: dict[str, Any], prefix: str = "", parent_resolved: bool = False
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, prop in props.items():
            path = f"{prefix}.{key}" if prefix else key
            value = self._resolve_prop(prop, path, parent_resolved)
            if value is not SKIP_PROP:
                resolved[key] = value
        return resolved

    def _resolve_prop(self, prop: Any, path: str, parent_resolved: bool = False) -> Any:
        if (
            not parent_resolved
            and not (isinstance(prop, Prop) and prop.always)
            and self._excluded_by_partial_request(path)
        ):
            return SKIP_PROP

        if isinstance(prop, dict):
            if not prop:
                return {}
            resolved = self._resolve_mapping(prop, path, parent_resolved)
            return resolved if resolved else SKIP_PROP
        if isinstance(prop, list):
            return self._resolve_list(prop, path, parent_resolved)

        is_cached_once_prop = self._should_skip_loaded_once_prop(prop, path)
        self._collect_metadata(
            prop,
            path,
            include_deferred=not is_cached_once_prop,
        )
        if is_cached_once_prop:
            return SKIP_PROP
        if (
            not self._is_partial()
            and isinstance(prop, Prop)
            and prop.skipped_on_first_load
        ):
            return SKIP_PROP

        try:
            value = prop.resolve() if isinstance(prop, Prop) else resolve_value(prop)
        except Exception:
            if isinstance(prop, Prop) and prop.rescue:
                self.metadata["rescuedProps"].append(path)
                return SKIP_PROP
            raise

        if isinstance(value, Prop):
            return self._resolve_prop(value, path, parent_resolved=True)
        if isinstance(value, dict):
            if not value:
                return {}
            resolved = self._resolve_mapping(value, path, parent_resolved=True)
            return resolved if resolved else SKIP_PROP
        if isinstance(value, list):
            return self._resolve_list(value, path, parent_resolved=True)
        return value

    def _resolve_list(
        self, values: list[Any], path: str, parent_resolved: bool
    ) -> list[Any]:
        resolved: list[Any] = []
        for index, value in enumerate(values):
            item = self._resolve_list_item(value, path, index, parent_resolved)
            if item is not SKIP_PROP:
                resolved.append(item)
        return resolved

    def _resolve_list_item(
        self, value: Any, path: str, index: int, parent_resolved: bool
    ) -> Any:
        item_path = f"{path}.{index}"
        if isinstance(value, dict):
            return self._resolve_mapping(value, item_path, parent_resolved)
        if isinstance(value, Prop):
            return self._resolve_prop(value, item_path, parent_resolved)
        return resolve_value(value)

    def _is_partial(self) -> bool:
        return self.request.is_partial(self.component)

    def _excluded_by_partial_request(self, path: str) -> bool:
        if not self._is_partial():
            return False
        only = self.request.partial_data
        if only is not None and not any(self._paths_overlap(path, key) for key in only):
            return True
        except_keys = self.request.partial_except or []
        return any(path == key or path.startswith(f"{key}.") for key in except_keys)

    @staticmethod
    def _paths_overlap(left: str, right: str) -> bool:
        return (
            left == right
            or left.startswith(f"{right}.")
            or right.startswith(f"{left}.")
        )

    def _should_skip_loaded_once_prop(self, prop: Any, path: str) -> bool:
        return (
            bool(self.request)
            and not self._is_partial()
            and isinstance(prop, Prop)
            and prop.once
            and not prop.fresh
            and prop.once_key(path) in self.request.except_once_props
        )

    def _collect_metadata(
        self, prop: Any, path: str, *, include_deferred: bool = True
    ) -> None:
        if not isinstance(prop, Prop):
            return
        if include_deferred and prop.defer and not self._is_partial():
            self.metadata["deferredProps"].setdefault(prop.group, []).append(path)
        if prop.merges:
            self._collect_merge_metadata(prop, path)
        if prop.once:
            self.metadata["onceProps"][prop.once_key(path)] = {
                "prop": path,
                "expiresAt": prop.once_expires_at(),
            }

    def _collect_merge_metadata(self, prop: Prop, path: str) -> None:
        reset = path in self.request.reset
        if prop.scroll is not None:
            self.metadata["scrollProps"][path] = {**prop.scroll, "reset": reset}
        if reset:
            return
        if prop.deep_merge:
            self.metadata["deepMergeProps"].append(path)
        else:
            prepend_paths = prop.merge_paths(path, prepend=True)
            append_paths = prop.merge_paths(path)
            if prepend_paths:
                self.metadata["prependProps"].extend(prepend_paths)
            elif self._is_partial() and self.request.merge_intent == "prepend":
                self.metadata["prependProps"].extend(append_paths)
            else:
                self.metadata["mergeProps"].extend(append_paths)
        self.metadata["matchPropsOn"].extend(
            f"{path}.{match}" for match in prop.match_on
        )


PROP_ATTR = "inertia_prop"


def prop(method: Callable[..., Any] | None = None, /, **options: Any) -> Any:
    """Declare a class-based view method as a prop, like ``@property``.

    The prop is named after the method and takes ``Prop``'s options. The
    method is called only when the prop is sent, and may be ``async def``::

        class Dashboard(InertiaView):
            component = "Dashboard"

            @prop(defer=True)
            def stats(self):
                return Stats.objects.summary()
    """

    def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
        # Validates the options when the class is defined.
        setattr(method, PROP_ATTR, Prop(method, **options))
        return method

    return decorate(method) if method is not None else decorate
