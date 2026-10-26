from django.core.exceptions import ImproperlyConfigured
from django.test import AsyncClient, TestCase, override_settings

from django_inertia.tests.utils import ProtocolTestCase, inertia_div, inertia_page


class FirstLoadTestCase(ProtocolTestCase):
    def test_with_props(self):
        self.assertContains(
            self.client.get("/props/"),
            inertia_div(
                "props",
                props={
                    "name": "Brandon",
                    "sport": "Hockey",
                },
            ),
        )

    def test_with_template_data(self):
        response = self.client.get("/template_data/")

        self.assertContains(
            response,
            inertia_div(
                "template_data",
                template_data={
                    "name": "Brian",
                    "sport": "Basketball",
                },
            ),
        )

        self.assertContains(response, "template data:Brian, Basketball")

    def test_with_no_data(self):
        self.assertContains(self.client.get("/empty/"), inertia_div("empty"))

    def test_proper_status_code(self):
        self.assertEqual(self.client.get("/empty/").status_code, 200)

    def test_template_rendered(self):
        self.assertTemplateUsed(self.client.get("/empty/"), "layout.html")


class SubsequentLoadTestCase(ProtocolTestCase):
    def test_with_props(self):
        self.assertJSONResponse(
            self.inertia.get("/props/"),
            inertia_page(
                "props",
                props={
                    "name": "Brandon",
                    "sport": "Hockey",
                },
            ),
        )

    def test_with_template_data(self):
        self.assertJSONResponse(
            self.inertia.get("/template_data/"),
            inertia_page(
                "template_data",
                template_data={
                    "name": "Brian",
                    "sport": "Basketball",
                },
            ),
        )

    def test_with_no_data(self):
        self.assertJSONResponse(self.inertia.get("/empty/"), inertia_page("empty"))

    def test_proper_status_code(self):
        self.assertEqual(self.inertia.get("/empty/").status_code, 200)

    def test_redirects_from_inertia_views(self):
        self.assertEqual(self.inertia.get("/inertia-redirect/").status_code, 302)


class OptionalPropsTestCase(ProtocolTestCase):
    def test_optional_props_are_not_included(self):
        self.assertJSONResponse(
            self.inertia.get("/optional/"),
            inertia_page("optional", props={"name": "Brian"}),
        )

    def test_optional_props_are_included_when_requested(self):
        self.assertJSONResponse(
            self.inertia.get(
                "/optional/",
                HTTP_X_INERTIA_PARTIAL_DATA="sport,grit",
                HTTP_X_INERTIA_PARTIAL_COMPONENT="TestComponent",
            ),
            inertia_page("optional", props={"sport": "Basketball", "grit": "intense"}),
        )


class ComplexPropsTestCase(ProtocolTestCase):
    def test_nested_callable_props_work(self):
        self.assertJSONResponse(
            self.inertia.get("/complex-props/"),
            inertia_page("complex-props", props={"person": {"name": "Brandon"}}),
        )


class ShareTestCase(ProtocolTestCase):
    def test_that_shared_props_are_merged(self):
        self.assertJSONResponse(
            self.inertia.get("/share/"),
            inertia_page(
                "share",
                props={"name": "Brandon", "position": "goalie", "number": 29},
                shared_props=["position", "number"],
            ),
        )


class CSRFTestCase(ProtocolTestCase):
    def test_that_csrf_inclusion_is_automatic(self):
        response = self.inertia.get("/props/")

        self.assertIsNotNone(response.cookies.get("csrftoken"))

    def test_that_csrf_is_included_even_on_initial_page_load(self):
        response = self.client.get("/props/")

        self.assertIsNotNone(response.cookies.get("csrftoken"))


class DeferredPropsTestCase(ProtocolTestCase):
    def test_deferred_props_are_set(self):
        self.assertJSONResponse(
            self.inertia.get("/defer/"),
            inertia_page(
                "defer", props={"name": "Brian"}, deferred_props={"default": ["sport"]}
            ),
        )

    def test_deferred_props_are_grouped(self):
        self.assertJSONResponse(
            self.inertia.get("/defer-group/"),
            inertia_page(
                "defer-group",
                props={"name": "Brian"},
                deferred_props={"group": ["sport", "team"], "default": ["grit"]},
            ),
        )

    def test_deferred_props_are_included_when_requested(self):
        self.assertJSONResponse(
            self.inertia.get(
                "/defer/",
                HTTP_X_INERTIA_PARTIAL_DATA="sport",
                HTTP_X_INERTIA_PARTIAL_COMPONENT="TestComponent",
            ),
            inertia_page("defer", props={"sport": "Basketball"}),
        )

    def test_only_deferred_props_in_group_are_included_when_requested(self):
        self.assertJSONResponse(
            self.inertia.get(
                "/defer-group/",
                HTTP_X_INERTIA_PARTIAL_DATA="sport,team",
                HTTP_X_INERTIA_PARTIAL_COMPONENT="TestComponent",
            ),
            inertia_page("defer-group", props={"sport": "Basketball", "team": "Bulls"}),
        )

        self.assertJSONResponse(
            self.inertia.get(
                "/defer-group/",
                HTTP_X_INERTIA_PARTIAL_DATA="grit",
                HTTP_X_INERTIA_PARTIAL_COMPONENT="TestComponent",
            ),
            inertia_page("defer-group", props={"grit": "intense"}),
        )


class MergePropsTestCase(ProtocolTestCase):
    def test_merge_props_are_included_on_initial_load(self):
        self.assertJSONResponse(
            self.inertia.get("/merge/"),
            inertia_page(
                "merge",
                props={
                    "name": "Brandon",
                    "sport": "Hockey",
                },
                merge_props=["sport", "team"],
                deferred_props={"default": ["team"]},
            ),
        )

    def test_deferred_merge_props_are_included_on_subsequent_load(self):
        self.assertJSONResponse(
            self.inertia.get(
                "/merge/",
                HTTP_X_INERTIA_PARTIAL_DATA="team",
                HTTP_X_INERTIA_PARTIAL_COMPONENT="TestComponent",
            ),
            inertia_page(
                "merge",
                props={
                    "team": "Penguins",
                },
                merge_props=["team"],
            ),
        )

    def test_merge_props_are_not_included_when_reset(self):
        self.assertJSONResponse(
            self.inertia.get(
                "/merge/",
                HTTP_X_INERTIA_PARTIAL_DATA="sport,team",
                HTTP_X_INERTIA_PARTIAL_COMPONENT="TestComponent",
                HTTP_X_INERTIA_RESET="sport,team",
            ),
            inertia_page(
                "merge",
                props={
                    "sport": "Hockey",
                    "team": "Penguins",
                },
            ),
        )


class MisconfiguredLayoutTestCase(ProtocolTestCase):
    def test_with_props(self):
        with (
            override_settings(INERTIA={}),
            self.assertRaisesMessage(
                ImproperlyConfigured,
                'Set INERTIA["LAYOUT"] in your Django settings',
            ),
        ):
            self.client.get("/props/")


class LazyResponseTestCase(ProtocolTestCase):
    def test_template_response_middleware_can_add_props(self):
        response = self.inertia.get("/template-response-middleware/")

        self.assertJSONResponse(
            response,
            inertia_page(
                "template-response-middleware",
                props={"name": "Brandon", "added": "by middleware"},
            ),
        )

    def test_render_passes_status(self):
        response = self.inertia.get("/status/")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["props"], {"name": "Brandon"})


class AsyncViewTestCase(TestCase):
    async def test_decorated_async_view_renders(self):
        response = await AsyncClient().get("/async/", headers={"X-Inertia": "true"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), inertia_page("async", props={"name": "Brandon"})
        )


class LayoutTestCase(ProtocolTestCase):
    root = (
        '<main><script data-page="root" type="application/json">'
        '{"component": "TestComponent"'
    )

    def test_render_takes_a_layout_per_view(self):
        response = self.client.get("/other-layout/")

        self.assertTemplateUsed(response, "other_layout.html")
        self.assertContains(response, self.root)
        self.assertContains(response, '</script>\n  <div id="root"></div></main>')

    def test_class_based_view_takes_a_layout(self):
        response = self.client.get("/other-layout-view/")

        self.assertTemplateUsed(response, "other_layout.html")
        self.assertContains(response, self.root)

    def test_tags_render_nothing_outside_an_inertia_response(self):
        response = self.client.get("/plain-layout/")

        self.assertEqual(
            response.content.decode(), "head----head\n\ntemplate data:Brian, \n"
        )
