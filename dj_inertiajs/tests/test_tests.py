import pytest
from django.template.response import ContentNotRenderedError
from django.test import SimpleTestCase

from dj_inertiajs import InertiaResponse
from dj_inertiajs.test import InertiaTestCase, InertiaTestMixin


class AssertionsTestCase(InertiaTestCase):
    def test_props(self):
        response = self.client.get("/props/", inertia=False)

        self.assertPropsContain(response, {"name": "Brandon"})
        self.assertPropsEqual(response, {"name": "Brandon", "sport": "Hockey"})
        with self.assertRaises(AssertionError):
            self.assertPropsContain(response, {"name": "Brian"})
        with self.assertRaises(AssertionError):
            self.assertPropsEqual(response, {"name": "Brandon"})

    def test_template_data(self):
        response = self.client.get("/template_data/", inertia=False)

        self.assertTemplateDataContain(response, {"name": "Brian"})
        self.assertTemplateDataEqual(response, {"name": "Brian", "sport": "Basketball"})
        with self.assertRaises(AssertionError):
            self.assertTemplateDataEqual(response, {"name": "Brian"})
        with self.assertRaises(AssertionError):
            self.assertTemplateDataContain(response, {"name": "Brandon"})

    def test_component(self):
        response = self.client.get("/props/")

        self.assertComponentUsed(response, "TestComponent")
        with self.assertRaisesMessage(
            AssertionError, "Component 'TestComponent' was used, not 'Other'."
        ):
            self.assertComponentUsed(response, "Other")

    def test_assertions_reject_non_inertia_responses(self):
        response = self.client.get("/test/", inertia=False)

        with self.assertRaisesMessage(
            AssertionError, "Expected an InertiaResponse, got HttpResponse."
        ):
            self.assertComponentUsed(response, "TestComponent")

    def test_each_assertion_reads_its_own_response(self):
        first = self.client.get("/props/")
        self.client.get("/empty/")

        self.assertPropsEqual(first, {"name": "Brandon", "sport": "Hockey"})


class ClientTestCase(InertiaTestCase):
    def test_client_makes_inertia_visits_unless_told_otherwise(self):
        response = self.client.get("/props/")
        self.assertEqual(response["Content-Type"], "application/json")

        response = self.client.get("/props/", inertia=False)
        self.assertTrue(response["Content-Type"].startswith("text/html"))

    def test_inertia_false_survives_redirects(self):
        response = self.client.get("/redirect/", follow=True, inertia=False)
        self.assertTrue(response["Content-Type"].startswith("text/html"))

    async def test_async_client_makes_inertia_visits(self):
        response = await self.async_client.get("/props/")
        self.assertEqual(response["Content-Type"], "application/json")


class MixinOnSimpleTestCase(InertiaTestMixin, SimpleTestCase):
    def test_works_without_a_database(self):
        response = self.client.get("/props/")

        self.assertComponentUsed(response, "TestComponent")


def test_pytest_reads_response_inertia(client):
    response = client.get("/props/", headers={"X-Inertia": "true"})

    assert response.inertia.component == "TestComponent"
    assert response.inertia.props == {"name": "Brandon", "sport": "Hockey"}
    assert response.inertia.url == "/props/"


def test_first_load_exposes_the_page_too(client):
    response = client.get("/props/")

    assert response.inertia.props == {"name": "Brandon", "sport": "Hockey"}


def test_page_is_unavailable_before_rendering(rf):
    response = InertiaResponse(rf.get("/"), "Dashboard")

    with pytest.raises(ContentNotRenderedError):
        _ = response.inertia
