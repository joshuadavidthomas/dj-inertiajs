from textwrap import dedent

from django.test import SimpleTestCase

from django_inertia.upgrade import main, upgrade_source


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
                from django_inertia import Prop

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
            from inertia import inertia, render, share
            from inertia.http import clear_history
            from inertia.test import InertiaTestCase, inertia_page
            from inertia.utils import InertiaJsonEncoder
            """
        )

        self.assertEqual(
            code,
            dedent(
                """\
                from django_inertia import inertia, render, share
                from django_inertia import clear_history
                from django_inertia.test import InertiaTestCase
                from django_inertia.utils import InertiaJsonEncoder
                """
            ),
        )
        self.assertEqual(len(manual), 1)
        self.assertIn("`inertia_page` was removed", manual[0])

    def test_module_import_is_reported(self):
        code, manual = upgrade("import inertia\n")

        self.assertEqual(code, "import inertia\n")
        self.assertIn("`import inertia` is not rewritten", manual[0])


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

                INSTALLED_APPS = ["django.contrib.sessions", "django_inertia"]
                MIDDLEWARE = ['django_inertia.middleware.InertiaMiddleware']
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
                written, "from django_inertia import Prop\nx = Prop(load, defer=True)\n"
            )

            err = StringIO()
            with redirect_stderr(err):
                main([root])
            self.assertEqual(path.read_text(), written)
            self.assertIn("0 file(s) changed", err.getvalue())
