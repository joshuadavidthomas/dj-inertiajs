from django.core.exceptions import ImproperlyConfigured

from django_inertia.test import InertiaTestCase
from django_inertia.tests.testapp.models import Sport


class InertiaViewTestCase(InertiaTestCase):
    def test_declared_props_and_url_kwargs(self):
        response = self.inertia.get("/dashboard/penguins/")

        self.assertComponentUsed(response, "Dashboard")
        self.assertHasExactProps(
            response, {"plans": ["basic", "pro"], "team": "penguins"}
        )
        self.assertEqual(response.inertia.data["deferredProps"], {"default": ["stats"]})
        self.assertEqual(
            response.inertia.data["onceProps"],
            {"plans": {"prop": "plans", "expiresAt": None}},
        )

    def test_declared_prop_method_runs_when_requested(self):
        response = self.inertia.get(
            "/dashboard/penguins/",
            headers={
                "X-Inertia-Partial-Component": "Dashboard",
                "X-Inertia-Partial-Data": "stats",
            },
        )

        self.assertHasExactProps(response, {"stats": {"wins": 3}})

    def test_missing_component(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "MissingComponentView requires either a definition of 'component'",
        ):
            self.inertia.get("/missing-component/")

    def test_declared_prop_naming_a_missing_method(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "BadMethodNameView.stats names 'get_missing', which is not a method",
        ):
            self.inertia.get("/bad-method-name/")


class GenericViewTestCase(InertiaTestCase):
    def test_list_view(self):
        Sport.objects.create(name="Hockey", season="Winter")
        Sport.objects.create(name="Baseball", season="Summer")

        response = self.inertia.get("/sports/")

        self.assertComponentUsed(response, "Sports/Index")
        self.assertHasExactProps(response, {"sports": ["Hockey", "Baseball"]})

    def test_form_view_renders_errors_and_redirects_on_success(self):
        response = self.inertia.post("/sports/create/", {})

        self.assertComponentUsed(response, "Sports/Create")
        self.assertHasExactProps(
            response, {"errors": {"name": "This field is required."}}
        )

        response = self.inertia.post("/sports/create/", {"name": "Hockey"})
        self.assertRedirects(response, "/empty/", fetch_redirect_response=False)
