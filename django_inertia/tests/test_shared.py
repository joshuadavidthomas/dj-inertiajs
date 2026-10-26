from django.test import override_settings

from django_inertia.test import InertiaTestCase

SHARED = {
    "LAYOUT": "layout.html",
    "SHARED_PROPS": ["django_inertia.tests.testapp.views.shared_props"],
}


@override_settings(INERTIA=SHARED)
class SharedPropsSettingTestCase(InertiaTestCase):
    def test_listed_functions_add_props_to_every_page(self):
        response = self.inertia.get("/props/")

        self.assertHasExactProps(
            response,
            {
                "app_name": "Scoreboard",
                "user": "Brandon",
                "name": "Brandon",
                "sport": "Hockey",
            },
        )
        self.assertEqual(response.inertia.data["sharedProps"], ["app_name", "user"])

    def test_view_props_win_over_shared_props(self):
        response = self.inertia.get("/overrides-shared/")

        self.assertIncludesProps(response, {"app_name": "From the view"})

    def test_shared_props_follow_partial_reload_rules(self):
        response = self.inertia.get(
            "/props/",
            headers={
                "X-Inertia-Partial-Component": "TestComponent",
                "X-Inertia-Partial-Data": "name",
            },
        )

        self.assertHasExactProps(response, {"user": "Brandon", "name": "Brandon"})

    def test_share_adds_to_the_listed_functions(self):
        response = self.inertia.get("/share/")

        self.assertEqual(
            response.inertia.data["sharedProps"],
            ["app_name", "user", "position", "number"],
        )


class SetErrorsTestCase(InertiaTestCase):
    def test_errors_are_sent_once_after_the_redirect(self):
        response = self.inertia.post("/set-errors/", {}, follow=True)

        self.assertHasExactProps(
            response, {"errors": {"name": "This field is required."}}
        )

        response = self.inertia.get("/empty/")
        self.assertHasExactProps(response, {})

    def test_errors_survive_a_partial_reload_for_other_props(self):
        self.inertia.post("/set-errors/", {})

        response = self.inertia.get(
            "/props/",
            headers={
                "X-Inertia-Partial-Component": "TestComponent",
                "X-Inertia-Partial-Data": "name",
            },
        )

        self.assertHasExactProps(
            response, {"errors": {"name": "This field is required."}, "name": "Brandon"}
        )

    def test_valid_form_sets_no_errors(self):
        response = self.inertia.post("/set-errors/", {"name": "Hockey"}, follow=True)

        self.assertHasExactProps(response, {})
