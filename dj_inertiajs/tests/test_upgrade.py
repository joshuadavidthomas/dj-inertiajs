import re
from pathlib import Path
from textwrap import dedent

from django.test import SimpleTestCase

from dj_inertiajs.upgrade import REMOVED, main, upgrade_source


def upgrade(source):
    return upgrade_source(dedent(source))


class PropHelperTestCase(SimpleTestCase):
    def test_helpers_become_prop_keywords(self):
        code, manual = upgrade(
            """\
            from inertia import always, deep_merge, defer, lazy, merge, once, scroll

            props = {
                "a": defer(load, "charts", True),
                "b": merge(load),
                "c": merge(load, append="items", match_on="items.id"),
                "d": merge(load, prepend=True),
                "e": once(load, True, key="k"),
                "f": scroll(load, meta, wrapper="data", defer=True),
                "g": lazy(load),
                "h": deep_merge(load, match_on="id"),
                "i": always(load),
            }
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import Prop

                props = {
                    "a": Prop(load, defer=True, group="charts", merge=True),
                    "b": Prop(load, merge=True),
                    "c": Prop(load, merge="items", match_on="items.id"),
                    "d": Prop(load, prepend=True),
                    "e": Prop(load, once=True, fresh=True, key="k"),
                    "f": Prop(load, scroll=meta, merge="data", defer=True),
                    "g": Prop(load, optional=True),
                    "h": Prop(load, deep_merge=True, match_on="id"),
                    "i": Prop(load, always=True),
                }
                """
            ),
        )
        self.assertEqual(manual, [])

    def test_aliases_are_followed_and_other_names_left_alone(self):
        code, _ = upgrade(
            """\
            from inertia.utils import defer as later
            from myapp import defer

            x = later(load)
            y = defer(load)
            """
        )

        self.assertIn("x = Prop(load, defer=True)", code)
        self.assertIn("y = defer(load)", code)

    def test_options_splat_is_rewritten_and_reported(self):
        code, manual = upgrade(
            """\
            from inertia import merge

            x = merge(load, **options)
            """
        )

        self.assertIn("x = Prop(load, merge=True, **options)", code)
        self.assertEqual(len(manual), 1)
        self.assertIn("line 3: `merge(..., **options)`", manual[0])

    def test_calls_it_cannot_map_are_left_and_reported(self):
        code, manual = upgrade(
            """\
            from inertia import defer
            x = defer(group="g")
            y = defer(f, *a)
            z = defer(f, "g", True, 1)
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import Prop
                x = defer(group="g")
                y = defer(f, *a)
                z = defer(f, "g", True, 1)
                """
            ),
        )
        self.assertEqual(
            manual,
            [
                "line 2: `defer(...)` has no plain first argument; "
                "rewrite it as Prop(...) by hand.",
                "line 3: `defer(*...)` is not rewritten.",
                "line 4: `defer(...)` has too many arguments.",
            ],
        )

    def test_formatting_is_kept(self):
        code, _ = upgrade(
            """\
            from inertia import defer, merge, optional, scroll

            props = {
                "a": optional(
                    load,
                ),
                "b": merge(
                    load,
                    match_on="id",
                ),
                "c": defer(
                    load,
                    "charts",
                ),
                "d": optional(load,),
                "e": merge(load, deep_merge=True),
                "f": merge(load, prepend="items"),
                "g": scroll(load, meta),
                "h": merge(load, match_on="id"),
            }
            a = 1; b = 2
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import Prop

                props = {
                    "a": Prop(
                        load,
                        optional=True,
                    ),
                    "b": Prop(
                        load,
                        merge=True,
                        match_on="id",
                    ),
                    "c": Prop(
                        load,
                        defer=True,
                        group="charts",
                    ),
                    "d": Prop(load, optional=True,),
                    "e": Prop(load, deep_merge=True),
                    "f": Prop(load, prepend="items"),
                    "g": Prop(load, scroll=meta),
                    "h": Prop(load, merge=True, match_on="id"),
                }
                a = 1; b = 2
                """
            ),
        )


class ImportTestCase(SimpleTestCase):
    def test_imports_move_to_their_new_modules(self):
        code, manual = upgrade(
            """\
            from inertia import inertia, render
            from inertia.http import location
            from inertia.test import InertiaTestCase, inertia_page
            from inertia.utils import InertiaJsonEncoder
            from inertia.helpers import deep_transform_callables
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import inertia, render
                from dj_inertiajs import InertiaLocation
                from dj_inertiajs.test import InertiaTestCase
                from dj_inertiajs.encoders import InertiaJsonEncoder
                from inertia.helpers import deep_transform_callables
                """
            ),
        )
        self.assertEqual(len(manual), 2)
        self.assertIn("`inertia_page` was removed", manual[0])
        self.assertIn(
            "`deep_transform_callables` from `inertia.helpers` is not public API",
            manual[1],
        )

    def test_removed_names_and_uncalled_names_are_reported(self):
        code, manual = upgrade(
            """\
            from inertia import location, InertiaResponse
            from inertia.http import location as loc
            from inertia.middleware import InertiaMiddleware
            from inertia.test import BaseInertiaTestCase, ClientWithLastResponse, inertia_div
            from inertia.settings import settings
            from inertia import encrypt_history
            from . import views
            from .inertia import thing

            handler = location
            use = encrypt_history


            def view(request):
                return loc("/x")
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import InertiaLocation, InertiaResponse
                from dj_inertiajs.middleware import InertiaMiddleware
                from . import views
                from .inertia import thing

                handler = location
                use = encrypt_history


                def view(request):
                    return InertiaLocation("/x")
                """
            ),
        )
        self.assertEqual(
            [m.split(";")[0] for m in manual],
            [
                "line 2: `location` is used without being called",
                "line 4: `BaseInertiaTestCase` was removed",
                "line 4: `ClientWithLastResponse` was removed",
                "line 4: `inertia_div` was removed",
                "line 5: `settings` was removed",
                "line 10: `location` is used without being called",
                "line 11: `encrypt_history` is used without being called",
            ],
        )

    def test_one_import_split_across_new_modules(self):
        code, manual = upgrade(
            """\
            import os

            # Inertia
            from inertia.utils import defer, InertiaJsonEncoder
            x = defer(f)
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                import os

                # Inertia
                from dj_inertiajs import Prop
                from dj_inertiajs.encoders import InertiaJsonEncoder
                x = Prop(f, defer=True)
                """
            ),
        )
        self.assertEqual(manual, [])

    def test_star_import_is_reported(self):
        code, manual = upgrade("from inertia import *\n")

        self.assertEqual(code, "from inertia import *\n")
        self.assertIn("`from inertia import *` is not rewritten", manual[0])

    def test_module_import_is_reported(self):
        code, manual = upgrade("import inertia\n")

        self.assertEqual(code, "import inertia\n")
        self.assertIn("`import inertia` is not rewritten", manual[0])


class RequestHelperTestCase(SimpleTestCase):
    def test_clear_history_is_kept_and_share_and_preserve_fragment_are_reported(self):
        code, manual = upgrade(
            """\
            from inertia import share
            from inertia.http import clear_history, preserve_fragment

            def view(request):
                share(request, user=lambda: request.user)
                clear_history(request)
                preserve_fragment(request)
                return redirect("home")

            hooks = [share]
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import clear_history

                def view(request):
                    share(request, user=lambda: request.user)
                    clear_history(request)
                    preserve_fragment(request)
                    return redirect("home")

                hooks = [share]
                """
            ),
        )
        self.assertEqual(len(manual), 3)
        self.assertIn("line 5: `share()` was removed", manual[0])
        self.assertIn("line 7: `preserve_fragment(request)` is replaced", manual[1])
        self.assertIn("line 10: `share()` was removed", manual[2])


class LocationTestCase(SimpleTestCase):
    def test_location_becomes_a_response_class(self):
        code, manual = upgrade(
            """\
            from inertia import location as leave, render

            def portal(request):
                return leave("https://billing.example.com/")

            handlers = [leave]
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import InertiaLocation, render

                def portal(request):
                    return InertiaLocation("https://billing.example.com/")

                handlers = [leave]
                """
            ),
        )
        self.assertEqual(len(manual), 1)
        self.assertIn("line 6: `leave` is used without being called", manual[0])


class EncryptHistoryTestCase(SimpleTestCase):
    def test_calls_in_inertia_views_move_to_the_decorator(self):
        code, manual = upgrade(
            """\
            from inertia import inertia as page
            from inertia.http import encrypt_history

            @page("Account/Show")
            def account(request):
                encrypt_history(request)
                return {}

            @page("Billing")
            def billing(request):
                encrypt_history(request, False)
                return {}

            @page("Admin")
            def admin(request):
                staff = request.user.is_staff
                encrypt_history(request, staff)
                return {}

            def plain(request):
                encrypt_history(request)
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import inertia as page

                @page("Account/Show", encrypt_history=True)
                def account(request):
                    return {}

                @page("Billing", encrypt_history=False)
                def billing(request):
                    return {}

                @page("Admin")
                def admin(request):
                    staff = request.user.is_staff
                    encrypt_history(request, staff)
                    return {}

                def plain(request):
                    encrypt_history(request)
                """
            ),
        )
        self.assertEqual(len(manual), 2)
        self.assertIn("line 17: `encrypt_history(...)` is now an option", manual[0])
        self.assertIn("line 21: `encrypt_history(...)` is now an option", manual[1])

    def test_only_a_bare_call_moves_and_only_to_inertia(self):
        code, manual = upgrade(
            """\
            from inertia import encrypt_history, inertia


            @login_required()
            @inertia("A")
            def a(request):
                encrypt_history(request)
                x = encrypt_history(request)
                encrypt_history(request, value=True)
                encrypt_history(request, True, 1)
                encrypt_history(request); other()
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import inertia


                @login_required()
                @inertia("A", encrypt_history=True)
                def a(request):
                    x = encrypt_history(request)
                    encrypt_history(request, value=True)
                    encrypt_history(request, True, 1)
                    encrypt_history(request); other()
                """
            ),
        )
        self.assertEqual(
            [m.split(":")[0] for m in manual],
            ["line 8", "line 9", "line 10", "line 11"],
        )


class SettingsTestCase(SimpleTestCase):
    def test_old_settings_become_one_dict(self):
        code, manual = upgrade(
            """\
            from myapp.encoders import Encoder

            INSTALLED_APPS = ["django.contrib.sessions", "inertia"]
            MIDDLEWARE = ['inertia.middleware.InertiaMiddleware']
            OTHER = ["inertia"]

            # Inertia
            INERTIA_LAYOUT = "base.html"
            DEBUG = True
            INERTIA_JSON_ENCODER = Encoder
            INERTIA_SSR_URL = env("SSR_URL")
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from myapp.encoders import Encoder

                INSTALLED_APPS = ["django.contrib.sessions", "dj_inertiajs"]
                MIDDLEWARE = ['dj_inertiajs.middleware.InertiaMiddleware']
                OTHER = ["inertia"]

                # Inertia
                INERTIA = {
                    "LAYOUT": "base.html",
                    "JSON_ENCODER": "myapp.encoders.Encoder",
                    "SSR": {
                        "URL": env("SSR_URL"),
                    },
                }
                DEBUG = True
                """
            ),
        )
        self.assertEqual(manual, [])

    def test_every_old_setting_and_string_path(self):
        code, manual = upgrade(
            """\
            import myapp.encoders

            MIDDLEWARE = ["inertia.middleware.InertiaMiddleware"]
            INERTIA_VERSION = "1.0"
            INERTIA_ENCRYPT_HISTORY = True
            INERTIA_SSR_ENABLED = True
            INERTIA_JSON_ENCODER = myapp.encoders.Encoder
            ENCODER = "inertia.utils.InertiaJsonEncoder"
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                import myapp.encoders

                MIDDLEWARE = ["dj_inertiajs.middleware.InertiaMiddleware"]
                INERTIA = {
                    "VERSION": "1.0",
                    "ENCRYPT_HISTORY": True,
                    "JSON_ENCODER": "myapp.encoders.Encoder",
                    "SSR": {
                        "ENABLED": True,
                    },
                }
                ENCODER = "dj_inertiajs.encoders.InertiaJsonEncoder"
                """
            ),
        )
        self.assertEqual(manual, [])

    def test_old_settings_in_tests_are_reported(self):
        _, manual = upgrade(
            """\
            @override_settings(INERTIA_LAYOUT="base.html")
            def test_index(self):
                with self.settings(INERTIA_VERSION="2"):
                    pass
            """
        )

        self.assertEqual(
            [m.split(";")[0] for m in manual],
            [
                "line 1: override_settings(INERTIA_LAYOUT=...) uses an old setting",
                "line 3: self.settings(INERTIA_VERSION=...) uses an old setting",
            ],
        )

    def test_installed_apps_extended_in_place(self):
        code, _ = upgrade('INSTALLED_APPS += ["inertia"]\nOTHER = ["inertia"]\n')

        self.assertEqual(
            code, 'INSTALLED_APPS += ["dj_inertiajs"]\nOTHER = ["inertia"]\n'
        )

    def test_encoder_that_is_not_a_name_is_reported(self):
        code, manual = upgrade("INERTIA_JSON_ENCODER = make_encoder()\n")

        self.assertIn('"JSON_ENCODER": make_encoder(),', code)
        self.assertIn(
            'INERTIA["JSON_ENCODER"] must be a dotted path, not make_encoder()',
            manual[0],
        )

    def test_encoder_strings_and_unimported_paths_are_kept(self):
        code, manual = upgrade(
            """\
            INERTIA_JSON_ENCODER = "inertia.utils.InertiaJsonEncoder"
            INERTIA_LAYOUT = layout("base.html", default=None)
            """
        )

        self.assertIn(
            '"JSON_ENCODER": "dj_inertiajs.encoders.InertiaJsonEncoder",', code
        )
        self.assertEqual(manual, [])
        code, manual = upgrade("INERTIA_JSON_ENCODER = encoders.Encoder\n")
        self.assertIn('"JSON_ENCODER": "encoders.Encoder",', code)
        self.assertEqual(manual, [])

    def test_existing_inertia_dict_is_not_merged(self):
        source = 'INERTIA = {}\nINERTIA_LAYOUT = "base.html"\n'
        code, manual = upgrade(source)

        self.assertEqual(code, source)
        self.assertIn("sets both INERTIA and INERTIA_* settings", manual[0])

    def test_old_setting_reads_are_reported(self):
        _, manual = upgrade("version = settings.INERTIA_VERSION\n")

        self.assertIn("line 1: `INERTIA_VERSION` is read here", manual[0])


class CommandTestCase(SimpleTestCase):
    def test_diff_does_not_write_and_a_second_run_changes_nothing(self):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as root:
            path = Path(root, "views.py")
            path.write_text("from inertia import defer\nx = defer(load)\n")

            out = StringIO()
            with redirect_stdout(out), redirect_stderr(StringIO()):
                main(["--diff", root])
            self.assertIn("+x = Prop(load, defer=True)", out.getvalue())
            self.assertIn("from inertia import defer", path.read_text())

            with redirect_stderr(StringIO()):
                main([root])
            written = path.read_text()
            self.assertEqual(
                written, "from dj_inertiajs import Prop\nx = Prop(load, defer=True)\n"
            )

            err = StringIO()
            with redirect_stderr(err):
                main([root])
            self.assertEqual(path.read_text(), written)
            self.assertIn("0 file(s) changed", err.getvalue())

    def test_a_file_path_and_an_unparsable_file(self):
        from contextlib import redirect_stderr
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as root:
            views = Path(root, "views.py")
            views.write_text("from inertia import defer\nx = defer(load)\n")
            broken = Path(root, "broken.py")
            broken.write_text("def f(:\n")

            err = StringIO()
            with redirect_stderr(err):
                main([str(views), str(broken)])

            self.assertIn("Prop(load, defer=True)", views.read_text())
            self.assertEqual(broken.read_text(), "def f(:\n")
            self.assertIn("not parsed", err.getvalue())


class TestAssertionTestCase(SimpleTestCase):
    def test_assertions_read_the_latest_response(self):
        code, manual = upgrade(
            """\
            from inertia.test import InertiaTestCase


            class EventTests(InertiaTestCase):
                def test_index(self):
                    self.client.get("/first/")
                    with self.settings(DEBUG=True):
                        page = self.inertia.get("/second/")
                    self.assertComponentUsed("Event/Index", msg_prefix="x")
                    assert self.props()["name"] == self.inertia.last_response
                    assert self.deferred_props() == {}
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs.test import InertiaTestCase


                class EventTests(InertiaTestCase):
                    def test_index(self):
                        response = self.client.get("/first/", inertia=False)
                        with self.settings(DEBUG=True):
                            page = self.client.get("/second/")
                        self.assertComponentUsed(page, "Event/Index", msg_prefix="x")
                        assert page.inertia.props["name"] == page
                        assert page.inertia.data["deferredProps"] == {}
                """
            ),
        )
        self.assertEqual(manual, [])

    def test_every_assertion_accessor_and_client_method(self):
        code, manual = upgrade(
            """\
            from inertia.test import InertiaTestCase


            class EventTests(InertiaTestCase):
                def test_reads(self):
                    self.client.put("/events/1/")
                    self.assertHasExactProps({"a": 1})
                    self.assertIncludesProps({"a": 1})
                    self.assertHasExactTemplateData({})
                    self.assertIncludesTemplateData({})
                    assert self.component() == "C"
                    assert self.page()["url"] == "/"
                    assert self.merge_props() == []
                    assert self.deferred_props() == {}
                    assert self.once_props() == {}
                    assert self.template_data() == {}
                    assert self.last_response().status_code == 200
                    assert self.client.last_response.status_code == 200

                def test_methods(self):
                    self.client.patch("/")
                    self.client.delete("/")
                    self.client.head("/")
                    self.client.options("/")
                    self.client.trace("/")
                    self.inertia.post("/")
                    self.assertComponentUsed("C")

                def test_nested_scopes(self):
                    def helper():
                        return 1

                    class Local:
                        pass

                    self.inertia.get("/")
                    self.assertComponentUsed("C")
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs.test import InertiaTestCase


                class EventTests(InertiaTestCase):
                    def test_reads(self):
                        response = self.client.put("/events/1/", inertia=False)
                        self.assertPropsEqual(response, {"a": 1})
                        self.assertPropsContain(response, {"a": 1})
                        self.assertTemplateDataEqual(response, {})
                        self.assertTemplateDataContain(response, {})
                        assert response.inertia.component == "C"
                        assert response.inertia.data["url"] == "/"
                        assert response.inertia.data["mergeProps"] == []
                        assert response.inertia.data["deferredProps"] == {}
                        assert response.inertia.data["onceProps"] == {}
                        assert response.template_data == {}
                        assert response.status_code == 200
                        assert response.status_code == 200

                    def test_methods(self):
                        response = self.client.patch("/", inertia=False)
                        response = self.client.delete("/", inertia=False)
                        response = self.client.head("/", inertia=False)
                        response = self.client.options("/", inertia=False)
                        response = self.client.trace("/", inertia=False)
                        response = self.client.post("/")
                        self.assertComponentUsed(response, "C")

                    def test_nested_scopes(self):
                        def helper():
                            return 1

                        class Local:
                            pass

                        response = self.client.get("/")
                        self.assertComponentUsed(response, "C")
                """
            ),
        )
        self.assertEqual(manual, [])

    def test_new_style_calls_and_other_objects_are_left_alone(self):
        code, manual = upgrade(
            """\
            from inertia.test import InertiaTestCase


            class EventTests(InertiaTestCase):
                def test_index(self):
                    response = self.client.get("/")
                    self.assertComponentUsed(response, "C")
                    event = self.make_event()
                    assert event.props() == {}
                    assert self.props() == {}

                def test_last_response_only(self):
                    self.client.get("/")
                    assert self.client.last_response.status_code == 200

                def test_no_request(self):
                    assert self.props() == {}

                def test_new_style(self):
                    self.client.get("/")
                    assert event.props() == {}
                    self.assertComponentUsed(response, "C")
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs.test import InertiaTestCase


                class EventTests(InertiaTestCase):
                    def test_index(self):
                        response = self.client.get("/", inertia=False)
                        self.assertComponentUsed(response, "C")
                        event = self.make_event()
                        assert event.props() == {}
                        assert response.inertia.props == {}

                    def test_last_response_only(self):
                        response = self.client.get("/", inertia=False)
                        assert response.status_code == 200

                    def test_no_request(self):
                        assert self.props() == {}

                    def test_new_style(self):
                        self.client.get("/", inertia=False)
                        assert event.props() == {}
                        self.assertComponentUsed(response, "C")
                """
            ),
        )
        self.assertEqual(len(manual), 1)
        self.assertIn("line 17: `self.props()` needs a response", manual[0])

    def test_removed_assert_json_response_is_reported(self):
        _, manual = upgrade(
            """\
            from inertia.test import InertiaTestCase


            class EventTests(InertiaTestCase):
                def test_index(self):
                    response = self.client.get("/events/")
                    self.assertJSONResponse(response, {})
            """
        )

        self.assertEqual(len(manual), 1)
        self.assertIn("line 7: `assertJSONResponse` was removed", manual[0])

    def test_only_inertia_test_cases_and_their_subclasses_are_rewritten(self):
        code, _ = upgrade(
            """\
            from django.test import TestCase
            from inertia.test import InertiaTestCase as Base


            class Shared(Base):
                pass


            class EventTests(Shared):
                def test_index(self):
                    self.client.get("/")
                    self.assertComponentUsed("Event/Index")


            class Other(TestCase):
                def test_view(self):
                    self.client.get("/")
                    self.assertEqual(self.props(), {})
            """
        )

        self.assertIn('self.assertComponentUsed(response, "Event/Index")', code)
        self.assertIn("self.assertEqual(self.props(), {})", code)
        self.assertEqual(code.count("response = "), 1)
        self.assertEqual(code.count("inertia=False"), 1)

    def test_assertion_without_a_request_is_reported(self):
        code, manual = upgrade(
            """\
            from inertia.test import InertiaTestCase


            class EventTests(InertiaTestCase):
                def assertIndex(self):
                    self.assertComponentUsed("Event/Index")
            """
        )

        self.assertIn('self.assertComponentUsed("Event/Index")', code)
        self.assertEqual(len(manual), 1)
        self.assertIn("line 6: `self.assertComponentUsed` needs a response", manual[0])

    def test_clients_and_assertion_names_change_and_a_second_run_does_not(self):
        code, manual = upgrade(
            """\
            from inertia.test import InertiaTestCase


            class EventTests(InertiaTestCase):
                def test_index(self):
                    self.client.get(
                        "/warm-up/",
                        follow=True,
                    )
                    response = self.inertia.get("/")
                    self.assertComponentUsed(response, "Event/Index")
                    self.assertHasExactProps({})
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs.test import InertiaTestCase


                class EventTests(InertiaTestCase):
                    def test_index(self):
                        response = self.client.get(
                            "/warm-up/",
                            follow=True,
                            inertia=False,
                        )
                        response = self.client.get("/")
                        self.assertComponentUsed(response, "Event/Index")
                        self.assertPropsEqual(response, {})
                """
            ),
        )
        self.assertEqual(manual, [])
        self.assertEqual(upgrade_source(code), (code, []))


class CrossFileTestCaseTestCase(SimpleTestCase):
    FILES = {
        "myproject/__init__.py": "",
        "myproject/testing.py": """\
            from inertia.test import InertiaTestCase


            class AppTestCase(InertiaTestCase):
                pass
            """,
        "events/__init__.py": "",
        "events/tests/__init__.py": "",
        "events/tests/base.py": """\
            from myproject.testing import AppTestCase


            class EventTestCase(AppTestCase):
                pass
            """,
        "events/tests/test_views.py": """\
            from django.test import TestCase

            from .base import EventTestCase


            class IndexTests(EventTestCase):
                def test_index(self):
                    self.client.get("/")
                    self.assertComponentUsed("Event/Index")


            class PlainTests(TestCase):
                def test_view(self):
                    self.client.get("/")
                    self.assertEqual(self.props(), {})
            """,
        "events/tests/test_api.py": """\
            import myproject.testing


            class ApiTests(myproject.testing.AppTestCase):
                def test_index(self):
                    self.inertia.get("/")
                    assert self.props() == {}
            """,
    }

    def run_upgrade(self, root, *paths):
        from contextlib import redirect_stderr
        from io import StringIO
        from pathlib import Path

        for name, source in self.FILES.items():
            path = Path(root, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dedent(source))
        with redirect_stderr(StringIO()):
            main([str(Path(root, p)) for p in paths])
        return {name: Path(root, name).read_text() for name in self.FILES}

    def test_bases_are_followed_through_imports_in_other_files(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as root:
            files = self.run_upgrade(root, ".")

        views = files["events/tests/test_views.py"]
        self.assertIn('self.assertComponentUsed(response, "Event/Index")', views)
        self.assertIn("self.assertEqual(self.props(), {})", views)
        self.assertEqual(views.count("response = "), 1)
        self.assertIn(
            "assert response.inertia.props == {}", files["events/tests/test_api.py"]
        )

    def test_module_names_do_not_depend_on_the_path_given(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as root:
            files = self.run_upgrade(root, "myproject", "events/tests")

        self.assertIn(
            'self.assertComponentUsed(response, "Event/Index")',
            files["events/tests/test_views.py"],
        )

    def test_relative_aliased_and_chained_bases_and_skipped_dirs(self):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory

        files = {
            "proj/__init__.py": "",
            "proj/core/__init__.py": "",
            "proj/core/testing.py": """\
                from typing import Generic

                from inertia.test import InertiaTestCase


                class AppTestCase(Generic[T], InertiaTestCase):
                    class Meta:
                        pass
                """,
            "proj/events/__init__.py": "",
            "proj/events/base.py": """\
                import proj.core.testing


                class EventBase(proj.core.testing.AppTestCase):
                    pass
                """,
            "proj/events/tests/__init__.py": "",
            "proj/events/tests/test_a.py": """\
                from ..base import EventBase
                from .. import base
                import proj.core.testing as t


                class A(EventBase):
                    def test_a(self):
                        self.assertComponentUsed("A")


                class B(base.EventBase):
                    def test_b(self):
                        self.assertComponentUsed("B")


                class C(t.AppTestCase):
                    def test_c(self):
                        self.assertComponentUsed("C")
                """,
            ".venv/lib/m.py": "from inertia import defer\n",
            "node_modules/x/m.py": "from inertia import defer\n",
        }
        with TemporaryDirectory() as root:
            for name, source in files.items():
                path = Path(root, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(dedent(source))
            out, err = StringIO(), StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                status = main(["--diff", root])

        self.assertEqual(status, 0)
        test_a = f"{root}/proj/events/tests/test_a.py"
        self.assertEqual(
            err.getvalue().splitlines(),
            [
                f"{test_a}: line 8: `self.assertComponentUsed` needs a response, "
                f"but no request comes before it in this method; pass the response "
                f'by hand; see "Tests" in the upgrade guide.',
                f"{test_a}: line 13: `self.assertComponentUsed` needs a response, "
                f"but no request comes before it in this method; pass the response "
                f'by hand; see "Tests" in the upgrade guide.',
                f"{test_a}: line 18: `self.assertComponentUsed` needs a response, "
                f"but no request comes before it in this method; pass the response "
                f'by hand; see "Tests" in the upgrade guide.',
                "1 file(s) would change, 3 item(s) to fix by hand. "
                "Then run `python manage.py check`.",
            ],
        )
        self.assertIn(f"--- a/{root}/proj/core/testing.py\n", out.getvalue())
        self.assertIn(f"+++ b/{root}/proj/core/testing.py\n", out.getvalue())
        self.assertIn(
            "-from inertia.test import InertiaTestCase\n"
            "+from dj_inertiajs.test import InertiaTestCase\n",
            out.getvalue(),
        )
        self.assertNotIn("m.py", out.getvalue())


class GuideSectionTestCase(SimpleTestCase):
    def test_every_section_named_by_the_codemod_and_checks_exists(self):
        package = Path(__file__).parents[1]
        guide = package.parent / "docs/guide/upgrading-from-inertia-django.md"
        headings = set(re.findall(r"^#+ (.+)$", guide.read_text(), re.MULTILINE))
        for module in ("upgrade.py", "checks.py"):
            source = (package / module).read_text()
            named = set(re.findall(r"""guide\(["']([^"']+)["']\)""", source))
            if module == "upgrade.py":
                named |= set(REMOVED.values())
            with self.subTest(module):
                self.assertTrue(named)
                self.assertEqual(named - headings, set())
