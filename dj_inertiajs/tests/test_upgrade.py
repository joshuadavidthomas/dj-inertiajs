from textwrap import dedent

from django.test import SimpleTestCase

from dj_inertiajs.upgrade import main, upgrade_source


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
                from dj_inertiajs import location
                from dj_inertiajs.test import InertiaTestCase
                from dj_inertiajs.utils import InertiaJsonEncoder
                from dj_inertiajs.helpers import deep_transform_callables
                """
            ),
        )
        self.assertEqual(len(manual), 2)
        self.assertIn("`inertia_page` was removed", manual[0])
        self.assertIn("`deep_transform_callables` is not public API", manual[1])

    def test_module_import_is_reported(self):
        code, manual = upgrade("import inertia\n")

        self.assertEqual(code, "import inertia\n")
        self.assertIn("`import inertia` is not rewritten", manual[0])


class RequestMethodTestCase(SimpleTestCase):
    def test_helpers_become_request_inertia_methods(self):
        code, manual = upgrade(
            """\
            from inertia import render, share
            from inertia.http import clear_history

            def view(request):
                share(
                    request,
                    user=lambda: request.user,
                )
                clear_history(self.request)
                return render(request, "Page")
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from dj_inertiajs import render

                def view(request):
                    request.inertia.share(
                        user=lambda: request.user,
                    )
                    self.request.inertia.clear_history()
                    return render(request, "Page")
                """
            ),
        )
        self.assertEqual(manual, [])

    def test_uses_it_cannot_rewrite_are_reported(self):
        code, manual = upgrade(
            """\
            from inertia import share

            callbacks = [share]
            share(request=request, x=1)
            """
        )

        self.assertIn("share(request=request, x=1)", code)
        self.assertEqual(len(manual), 2)
        self.assertIn("line 3: `share` is used without being called", manual[0])
        self.assertIn("line 4: `share(...)` has no plain request argument", manual[1])


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

                def plain(request):
                    encrypt_history(request)
                """
            ),
        )
        self.assertEqual(len(manual), 1)
        self.assertIn("line 15: `encrypt_history(...)` is now an option", manual[0])


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
                        response = self.client.get("/first/")
                        with self.settings(DEBUG=True):
                            page = self.inertia.get("/second/")
                        self.assertComponentUsed(page, "Event/Index", msg_prefix="x")
                        assert page.inertia.props["name"] == page
                        assert page.inertia.data["deferredProps"] == {}
                """
            ),
        )
        self.assertEqual(manual, [])

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

    def test_methods_on_the_new_api_are_left_alone(self):
        source = dedent(
            """\
            from inertia.test import InertiaTestCase


            class EventTests(InertiaTestCase):
                def test_index(self):
                    self.client.get("/warm-up/")
                    response = self.inertia.get("/")
                    self.assertComponentUsed(response, "Event/Index")
            """
        )

        code, manual = upgrade_source(source)

        self.assertEqual(
            code, source.replace("from inertia.test", "from dj_inertiajs.test")
        )
        self.assertEqual(manual, [])


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
