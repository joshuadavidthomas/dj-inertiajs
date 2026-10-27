import pickle
import socket
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.core.handlers.wsgi import WSGIRequest
from django.test import RequestFactory, SimpleTestCase

from dj_inertiajs import InertiaResponse, Prop

SCROLL = {"pageName": "page", "previousPage": None, "nextPage": 2, "currentPage": 1}


class PropOptionsTestCase(SimpleTestCase):
    def test_conflicting_options_are_rejected(self):
        cases = {
            "Use at most one of optional, defer and always.": {
                "optional": True,
                "defer": True,
            },
            "group requires defer=True.": {"group": "charts"},
            "rescue requires defer=True.": {"rescue": True, "optional": True},
            "merge and prepend cannot both be set.": {"merge": True, "prepend": True},
            "deep_merge cannot be combined with merge or prepend.": {
                "deep_merge": True,
                "merge": "items",
            },
            "scroll cannot be combined with prepend or deep_merge.": {
                "scroll": SCROLL,
                "prepend": True,
            },
            "scroll is missing nextPage.": {
                "scroll": {"pageName": "p", "previousPage": None, "currentPage": 1}
            },
            "match_on requires merge, prepend, deep_merge or scroll.": {
                "match_on": "id"
            },
            "key, expires_at and fresh require once=True.": {"fresh": True},
        }
        for message, options in cases.items():
            with self.subTest(message), self.assertRaisesMessage(ValueError, message):
                Prop(1, **options)

    def test_scroll_merges_into_the_given_path(self):
        self.assertEqual(Prop([], scroll=SCROLL).merge_paths("players"), ["players"])
        self.assertEqual(
            Prop([], scroll=SCROLL, merge="data").merge_paths("players"),
            ["players.data"],
        )
        self.assertEqual(Prop([], scroll=SCROLL).merge_paths("p", prepend=True), [])

    def test_static_and_callable_values(self):
        self.assertEqual(Prop(["basic"]).resolve(), ["basic"])
        self.assertEqual(Prop(lambda: ["basic"]).resolve(), ["basic"])


def render(props, **headers):
    """Render an Inertia visit to a "Dashboard" page and return its page object."""
    request = RequestFactory().get("/", headers={"X-Inertia": "true", **headers})
    request.session = SessionStore()
    response = InertiaResponse(request, "Dashboard", props)
    response.render()
    return response.inertia.data


def reload(props, only):
    return render(
        props,
        **{"X-Inertia-Partial-Component": "Dashboard", "X-Inertia-Partial-Data": only},
    )


def fail():
    raise RuntimeError("stats service is down")


class PropResolutionTestCase(SimpleTestCase):
    def test_rescued_deferred_prop_is_omitted_and_reported(self):
        props = {"stats": Prop(fail, defer=True, rescue=True), "plans": Prop(list)}

        page = reload(props, "stats,plans")

        self.assertEqual(page["props"], {"plans": []})
        self.assertEqual(page["rescuedProps"], ["stats"])
        self.assertNotIn("rescuedProps", reload(props, "plans"))

    def test_deferred_prop_without_rescue_fails_the_request(self):
        with self.assertRaisesMessage(RuntimeError, "stats service is down"):
            reload({"stats": Prop(fail, defer=True)}, "stats")

    def test_nested_values_are_resolved(self):
        props = {
            "filters": {},
            "empty": Prop(dict),
            "nested": Prop(lambda: Prop(lambda: "inner")),
            "items": [Prop(lambda: 1), {"a": lambda: 2}, lambda: 3],
            "rows": Prop(lambda: [lambda: 4, {"b": lambda: 5}]),
        }

        self.assertEqual(
            render(props)["props"],
            {
                "filters": {},
                "empty": {},
                "nested": "inner",
                "items": [1, {"a": 2}, 3],
                "rows": [4, {"b": 5}],
            },
        )

    def test_prepend_props_are_reported_as_prepend(self):
        page = render(
            {"feed": Prop([], prepend=True), "log": Prop({}, prepend="lines")}
        )

        self.assertEqual(page["prependProps"], ["feed", "log.lines"])
        self.assertNotIn("mergeProps", page)

    def test_scroll_metadata_keeps_only_the_pagination_keys(self):
        page = render({"players": Prop([], scroll={**SCROLL, "total": 40})})

        self.assertEqual(page["scrollProps"], {"players": {**SCROLL, "reset": False}})
        self.assertEqual(page["mergeProps"], ["players"])

    def test_once_expiry_forms(self):
        new_year = datetime(2030, 1, 1, tzinfo=timezone.utc)
        props = {
            "aware": Prop(1, once=True, expires_at=new_year),
            "naive": Prop(1, once=True, expires_at=new_year.replace(tzinfo=None)),
            "delta": Prop(1, once=True, expires_at=timedelta(minutes=1)),
            "seconds": Prop(1, once=True, expires_at=60),
        }
        before = int(time.time() * 1000)
        expiry = {k: v["expiresAt"] for k, v in render(props)["onceProps"].items()}
        after = int(time.time() * 1000)

        self.assertEqual(expiry["aware"], 1893456000000)
        self.assertEqual(expiry["naive"], 1893456000000)
        for key in ("delta", "seconds"):
            with self.subTest(key):
                self.assertGreaterEqual(expiry[key], before + 60_000)
                self.assertLessEqual(expiry[key], after + 60_000)

    def test_default_encoder_handles_django_types(self):
        props = {"price": Decimal("1.50"), "at": datetime(2030, 1, 1, 9, 30)}

        self.assertEqual(
            render(props)["props"], {"price": "1.50", "at": "2030-01-01T09:30:00"}
        )

    def test_page_json_cannot_close_the_script_tag(self):
        request = RequestFactory().get("/")
        request.session = SessionStore()
        response = InertiaResponse(
            request, "Dashboard", {"bio": "</script><b>&"}, template_name="layout.html"
        )
        response.render()

        self.assertNotIn("</script><b>", response.content.decode())
        self.assertIn(
            "\\u003c/script\\u003e\\u003cb\\u003e\\u0026", response.content.decode()
        )
        self.assertEqual(response.inertia.props, {"bio": "</script><b>&"})

    def test_rendered_response_can_be_cached(self):
        # cache_page pickles the response; a real server's request cannot be.
        server, client = socket.socketpair()
        self.addCleanup(server.close)
        self.addCleanup(client.close)
        environ = RequestFactory().get("/").environ
        environ["wsgi.input"] = server.makefile("rb")
        request = WSGIRequest(environ)
        request.session = SessionStore()
        response = InertiaResponse(request, "Dashboard", {"a": 1})
        response.render()

        cached = pickle.loads(pickle.dumps(response))

        self.assertEqual(cached.content, response.content)
        self.assertEqual(cached.inertia.props, {"a": 1})
