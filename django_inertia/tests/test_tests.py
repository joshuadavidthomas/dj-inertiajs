from django.test import SimpleTestCase

from django_inertia.test import InertiaTestCase, InertiaTestMixin


class AssertionsTestCase(InertiaTestCase):
    def test_props(self):
        response = self.client.get("/props/")

        self.assertIncludesProps(response, {"name": "Brandon"})
        self.assertHasExactProps(response, {"name": "Brandon", "sport": "Hockey"})
        with self.assertRaises(AssertionError):
            self.assertIncludesProps(response, {"name": "Brian"})
        with self.assertRaises(AssertionError):
            self.assertHasExactProps(response, {"name": "Brandon"})

    def test_template_data(self):
        response = self.client.get("/template_data/")

        self.assertIncludesTemplateData(response, {"name": "Brian"})
        self.assertHasExactTemplateData(
            response, {"name": "Brian", "sport": "Basketball"}
        )
        with self.assertRaises(AssertionError):
            self.assertHasExactTemplateData(response, {"name": "Brian"})

    def test_component(self):
        response = self.inertia.get("/props/")

        self.assertComponentUsed(response, "TestComponent")
        with self.assertRaisesMessage(
            AssertionError, "Component 'TestComponent' was used, not 'Other'."
        ):
            self.assertComponentUsed(response, "Other")

    def test_assertions_reject_non_inertia_responses(self):
        response = self.client.get("/test/")

        with self.assertRaisesMessage(
            AssertionError, "Expected an InertiaResponse, got HttpResponse."
        ):
            self.assertComponentUsed(response, "TestComponent")

    def test_each_assertion_reads_its_own_response(self):
        first = self.inertia.get("/props/")
        self.inertia.get("/empty/")

        self.assertHasExactProps(first, {"name": "Brandon", "sport": "Hockey"})


class MixinOnSimpleTestCase(InertiaTestMixin, SimpleTestCase):
    def test_works_without_a_database(self):
        response = self.inertia.get("/props/")

        self.assertComponentUsed(response, "TestComponent")


def test_pytest_reads_response_inertia(client):
    response = client.get("/props/", headers={"X-Inertia": "true"})

    assert response.inertia.component == "TestComponent"
    assert response.inertia.props == {"name": "Brandon", "sport": "Hockey"}
    assert response.inertia.url == "/props/"


def test_first_load_exposes_the_page_too(client):
    response = client.get("/props/")

    assert response.inertia.props == {"name": "Brandon", "sport": "Hockey"}
