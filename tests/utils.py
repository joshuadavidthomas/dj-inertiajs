from json import dumps

from dj_inertiajs.conf import settings
from dj_inertiajs.test import InertiaTestCase


class ProtocolTestCase(InertiaTestCase):
    """Base for this package's protocol tests, which compare whole page objects."""

    def assertJSONResponse(self, response, json_obj):
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json(), json_obj)


def inertia_page(
    url,
    component="TestComponent",
    props=None,
    template_data=None,
    deferred_props=None,
    merge_props=None,
    once_props=None,
    preserve_fragment=False,
    prepend_props=None,
    shared_props=None,
):
    props = props or {}
    template_data = template_data or {}
    _page = {
        "component": component,
        "props": props,
        "url": f"/{url}/",
        "version": settings.VERSION,
        "encryptHistory": False,
        "clearHistory": False,
    }

    if preserve_fragment:
        _page["preserveFragment"] = True

    if deferred_props:
        _page["deferredProps"] = deferred_props

    if merge_props:
        _page["mergeProps"] = merge_props

    if prepend_props:
        _page["prependProps"] = prepend_props

    if once_props:
        _page["onceProps"] = once_props

    if shared_props:
        _page["sharedProps"] = shared_props

    return _page


def inertia_div(*args, **kwargs):
    page = inertia_page(*args, **kwargs)
    data = (
        dumps(page)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return (
        f'<script data-page="app" type="application/json">{data}</script>'
        '\n  <div id="app"></div>'
    )
