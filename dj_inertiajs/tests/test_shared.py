from django import forms
from django.test import SimpleTestCase, TestCase, override_settings

from dj_inertiajs.request import error_messages
from dj_inertiajs.test import InertiaClient, InertiaTestCase

SHARED = {
    "LAYOUT": "layout.html",
    "SHARED_PROPS": ["dj_inertiajs.tests.testapp.views.shared_props"],
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


class ErrorMessagesTestCase(SimpleTestCase):
    def test_non_field_and_formset_errors(self):
        class SportForm(forms.Form):
            name = forms.CharField()
            season = forms.CharField(required=False)

            def clean(self):
                raise forms.ValidationError("Pick a season.")

        form = SportForm({"name": ""})
        self.assertEqual(
            error_messages(form),
            {"name": "This field is required.", "__all__": "Pick a season."},
        )

        SportFormSet = forms.formset_factory(SportForm, max_num=1, validate_max=True)
        formset = SportFormSet(
            {
                "sports-TOTAL_FORMS": "2",
                "sports-INITIAL_FORMS": "0",
                "sports-0-name": "Hockey",
                "sports-1-season": "Winter",
            },
            prefix="sports",
        )
        self.assertEqual(
            error_messages(formset),
            {
                "sports": "Please submit at most 1 form.",
                "sports.0.__all__": "Pick a season.",
                "sports.1.name": "This field is required.",
                "sports.1.__all__": "Pick a season.",
            },
        )


class FormErrorsSettingTestCase(TestCase):
    @override_settings(
        INERTIA={
            "LAYOUT": "layout.html",
            "FORM_ERRORS": "dj_inertiajs.tests.testapp.views.all_error_messages",
        }
    )
    def test_form_errors_setting_converts_errors(self):
        response = InertiaClient().post("/set-errors/", {}, follow=True)

        self.assertEqual(
            response.inertia.props, {"errors": {"name": ["This field is required."]}}
        )

        response = InertiaClient().post("/sports/create/", {})
        self.assertEqual(
            response.inertia.props["errors"], {"name": ["This field is required."]}
        )
