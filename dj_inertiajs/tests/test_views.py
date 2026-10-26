from django.core.exceptions import ImproperlyConfigured

from dj_inertiajs import prop
from dj_inertiajs.test import InertiaTestCase
from dj_inertiajs.tests.testapp.models import Sport
from dj_inertiajs.views import InertiaView


class InertiaViewTestCase(InertiaTestCase):
    def test_declared_props_and_url_kwargs(self):
        response = self.client.get("/dashboard/penguins/")

        self.assertComponentUsed(response, "Dashboard")
        self.assertPropsEqual(
            response,
            {"plans": ["basic", "pro"], "motto": "get_stats", "team": "penguins"},
        )
        self.assertEqual(response.inertia.data["deferredProps"], {"default": ["stats"]})
        self.assertEqual(
            response.inertia.data["onceProps"],
            {"plans": {"prop": "plans", "expiresAt": None}},
        )

    def test_declared_prop_method_runs_when_requested(self):
        response = self.client.get(
            "/dashboard/penguins/",
            headers={
                "X-Inertia-Partial-Component": "Dashboard",
                "X-Inertia-Partial-Data": "stats",
            },
        )

        self.assertPropsEqual(response, {"stats": {"wins": 3}})

    def test_missing_component(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "MissingComponentView requires either a definition of 'component'",
        ):
            self.client.get("/missing-component/")

    def test_prop_decorator_validates_its_options(self):
        with self.assertRaisesMessage(ValueError, "group requires defer=True."):

            class View(InertiaView):
                @prop(group="charts")
                def stats(self):
                    return {}


class GenericViewTestCase(InertiaTestCase):
    def test_list_view(self):
        Sport.objects.create(name="Hockey", season="Winter")
        Sport.objects.create(name="Baseball", season="Summer")

        response = self.client.get("/sports/")

        self.assertComponentUsed(response, "Sports/Index")
        self.assertPropsEqual(response, {"sports": ["Hockey", "Baseball"]})

    def test_form_view_renders_errors_and_redirects_on_success(self):
        response = self.client.post("/sports/create/", {})

        self.assertComponentUsed(response, "Sports/Create")
        self.assertPropsEqual(response, {"errors": {"name": "This field is required."}})

        response = self.client.post("/sports/create/", {"name": "Hockey"})
        self.assertRedirects(response, "/empty/", fetch_redirect_response=False)

    def test_form_errors_survive_a_partial_submit(self):
        response = self.client.post(
            "/sports/create/",
            {},
            headers={
                "X-Inertia-Partial-Component": "Sports/Create",
                "X-Inertia-Partial-Data": "other",
            },
        )

        self.assertPropsEqual(response, {"errors": {"name": "This field is required."}})
