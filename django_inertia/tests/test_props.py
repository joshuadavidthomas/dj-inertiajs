from django.test import SimpleTestCase

from django_inertia import Prop

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
