from __future__ import annotations

import logging
from collections import ChainMap
from collections import OrderedDict

import pytest

from dj_inertiajs.middleware import InertiaDetails
from dj_inertiajs.test import InertiaTestCase

from .utils import override_app_settings


class MiddlewareTestCase(InertiaTestCase):
    def test_anything(self):
        response = self.client.get("/test/")

        self.assertEqual(response.status_code, 200)

    def test_stale_versions_are_refreshed(self):
        response = self.inertia.get(
            "/empty/",
            HTTP_X_INERTIA_VERSION="some-nonsense",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.headers["X-Inertia-Location"], "http://testserver/empty/"
        )

    def test_redirect_status(self):
        response = self.inertia.post("/redirect/")
        self.assertEqual(response.status_code, 302)

        for http_method in ["put", "patch", "delete"]:
            response = getattr(self.inertia, http_method)("/redirect/")

            self.assertEqual(response.status_code, 303)

    def test_a_request_not_from_inertia_is_ignored(self):
        response = self.client.get(
            "/empty/",
            HTTP_X_INERTIA_VERSION="some-nonsense",
        )

        self.assertEqual(response.status_code, 200)

    def test_external_redirect_status(self):
        response = self.inertia.post("/external-redirect/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("X-Inertia-Location", response.headers)
        self.assertEqual("http://foobar.com/", response.headers["X-Inertia-Location"])


def returns_string(request):
    return "not a dict"


def returns_none(request):
    return None


def returns_list(request):
    return [1, 2, 3]


def error_prop(request):
    raise ValueError("Something went wrong!")


def chainmap_prop(request):
    return ChainMap({"a": 1}, {"b": 2})


string_prop = "This is just a string"
number_prop = 42
list_prop = [1, 2, 3]
ordered_props = OrderedDict([("first", 1), ("second", 2)])
static_dict1 = {"name": "First", "value": 1, "unique1": True}
static_dict2 = {"name": "Second", "value": 2, "unique2": True}


class TestSharedProps:
    @pytest.fixture
    def req(self, rf):
        return rf.get("/")

    @override_app_settings(SHARED_PROPS=["tests.testapp.shared_props.share_test_props"])
    def test_callable_shared_prop(self, req):
        inertia = InertiaDetails(req)

        assert inertia.shared_props == {"position": "goalie", "number": 29}

    @override_app_settings(SHARED_PROPS=["tests.testapp.shared_props.static_props"])
    def test_static_dict_shared_prop(self, req):
        inertia = InertiaDetails(req)

        assert inertia.shared_props == {
            "static": {"version": "1.0.0", "features": ["inertia", "django"]}
        }

    @override_app_settings(
        SHARED_PROPS=[
            "tests.testapp.shared_props.share_test_props",
            "tests.testapp.shared_props.static_props",
        ]
    )
    def test_multiple_shared_props_merge(self, req):
        inertia = InertiaDetails(req)

        assert inertia.shared_props == {
            "position": "goalie",
            "number": 29,
            "static": {"version": "1.0.0", "features": ["inertia", "django"]},
        }

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.ordered_props"])
    def test_ordered_dict_shared_prop(self, req):
        inertia = InertiaDetails(req)

        assert inertia.shared_props == {"first": 1, "second": 2}

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.string_prop"])
    def test_invalid_shared_prop_type_string(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert "must be a callable or a Mapping, got str" in caplog.text

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.number_prop"])
    def test_invalid_shared_prop_type_number(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert "must be a callable or a Mapping, got int" in caplog.text

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.list_prop"])
    def test_invalid_shared_prop_type_list(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert "must be a callable or a Mapping, got list" in caplog.text

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.returns_string"])
    def test_callable_returns_string(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert "returned str instead of a Mapping" in caplog.text

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.returns_none"])
    def test_callable_returns_none(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert "returned NoneType instead of a Mapping" in caplog.text

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.returns_list"])
    def test_callable_returns_list(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert "returned list instead of a Mapping" in caplog.text

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.error_prop"])
    def test_callable_raises_exception(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert "Error in shared prop 'tests.test_middleware.error_prop'" in caplog.text

    @override_app_settings(SHARED_PROPS=["nonexistent_module.some_prop"])
    def test_nonexistent_module(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert (
            "Could not import shared prop 'nonexistent_module.some_prop'" in caplog.text
        )

    @override_app_settings(SHARED_PROPS=["os.nonexistent_attribute"])
    def test_nonexistent_attribute(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        assert inertia.shared_props == {}
        assert "Could not import shared prop 'os.nonexistent_attribute'" in caplog.text

    @override_app_settings(
        SHARED_PROPS=[
            "tests.test_middleware.string_prop",  # invalid
            "tests.testapp.shared_props.share_test_props",  # valid
            "tests.test_middleware.error_prop",  # raises exception
            "tests.testapp.shared_props.static_props",  # valid
        ]
    )
    def test_mixed_valid_and_invalid_props(self, req, caplog):
        with caplog.at_level(logging.ERROR):
            inertia = InertiaDetails(req)

        # Should have the valid props
        assert inertia.shared_props == {
            "position": "goalie",
            "number": 29,
            "static": {"version": "1.0.0", "features": ["inertia", "django"]},
        }
        # Should have logged errors for invalid ones
        assert "must be a callable or a Mapping, got str" in caplog.text
        assert "Error in shared prop 'tests.test_middleware.error_prop'" in caplog.text

    @override_app_settings(
        SHARED_PROPS=[
            "tests.test_middleware.static_dict1",
            "tests.test_middleware.static_dict2",
        ]
    )
    def test_override_behavior(self, req):
        inertia = InertiaDetails(req)

        # name and value should be from dict2, but unique1 and unique2 should both exist
        assert inertia.shared_props == {
            "name": "Second",
            "value": 2,
            "unique1": True,
            "unique2": True,
        }

    @override_app_settings(SHARED_PROPS=[])
    def test_empty_shared_props_list(self, req):
        inertia = InertiaDetails(req)

        assert inertia.shared_props == {}

    @override_app_settings(SHARED_PROPS=["tests.test_middleware.chainmap_prop"])
    def test_callable_with_custom_mapping(self, req):
        inertia = InertiaDetails(req)

        assert inertia.shared_props == {"a": 1, "b": 2}
