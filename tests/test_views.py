from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.sessions.backends.base import SessionBase

from dj_inertiajs.views import InertiaView


def test_inertia_view_basic(rf):
    class TestView(InertiaView):
        component_name = "TestComponent"

        def get_prop_data(self, **kwargs):
            return {"users": ["Alice", "Bob"]}

    view = TestView.as_view()
    request = rf.get("/")
    request.session = SessionBase()

    # Mock render_to_string to avoid template not found error
    with patch("dj_inertiajs.http.render_to_string") as mock_render:
        mock_render.return_value = '<div id="app" data-page="{}">TestComponent</div>'
        response = view(request)

    assert response.status_code == 200
    assert b"TestComponent" in response.content


def test_custom_template_names(rf):
    class CustomTemplateView(InertiaView):
        component_name = "TestComponent"
        template_name = "custom_inertia.html"
        ssr_template_name = "custom_ssr.html"

        def get_prop_data(self, **kwargs):
            return {"custom": True}

    view = CustomTemplateView()
    assert view.get_template_name() == "custom_inertia.html"
    assert view.get_ssr_template_name() == "custom_ssr.html"

    request = rf.get("/")
    request.session = SessionBase()
    view.request = request

    # Mock render_to_string to avoid template not found error
    with patch("dj_inertiajs.http.render_to_string") as mock_render:
        mock_render.return_value = "<html>test</html>"
        response = view.get(request)

    assert response.status_code == 200
    assert response.template_name == "custom_inertia.html"
    assert response.ssr_template_name == "custom_ssr.html"


def test_inertia_request_with_headers(rf):
    class TestView(InertiaView):
        component_name = "TestComponent"

        def get_prop_data(self, **kwargs):
            return {"users": ["Alice", "Bob"]}

    view = TestView.as_view()
    request = rf.get("/", HTTP_X_INERTIA="true")
    request.session = SessionBase()

    response = view(request)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert response["X-Inertia"] == "true"

    data = json.loads(response.content)

    assert data["component"] == "TestComponent"
    assert data["props"]["users"] == ["Alice", "Bob"]


def test_inertia_view_with_post(rf):
    class PostView(InertiaView):
        component_name = "TestComponent"

        def post(self, request, *args, **kwargs):
            context = self.get_context_data(**kwargs)
            return self.render_to_response(context)

        def get_prop_data(self, **kwargs):
            return {"message": "Posted!", "data": self.request.POST.dict()}

    view = PostView.as_view()
    request = rf.post("/", {"name": "Test User"}, HTTP_X_INERTIA="true")
    request.session = SessionBase()

    response = view(request)

    assert response.status_code == 200

    data = json.loads(response.content)

    assert data["props"]["message"] == "Posted!"
    assert data["props"]["data"]["name"] == "Test User"


def test_serialize_props_integration(rf):
    class MockSerializer:
        def __init__(self, data, **kwargs):
            self._data = data
            self.context = kwargs.get("context", {})

        @property
        def data(self):
            return {"serialized": True, "original": self._data}

    class SerializedView(InertiaView):
        component_name = "TestComponent"
        serializer_class = MockSerializer

        def get_prop_data(self, **kwargs):
            return {"users": ["Alice", "Bob"]}

    view = SerializedView()
    request = rf.get("/", HTTP_X_INERTIA="true")
    request.session = SessionBase()
    view.request = request

    response = view.get(request)

    assert response.status_code == 200

    data = json.loads(response.content)

    assert data["props"]["serialized"] is True
    assert data["props"]["original"] == {"users": ["Alice", "Bob"]}


def test_serializer_context(rf):
    context_received = {}

    class ContextAwareSerializer:
        def __init__(self, data, **kwargs):
            self._data = data
            self.context = kwargs.get("context", {})
            context_received.update(self.context)

        @property
        def data(self):
            return {
                "data": self._data,
                "has_request": "request" in self.context,
                "has_view": "view" in self.context,
            }

    class SerializedView(InertiaView):
        component_name = "TestComponent"
        serializer_class = ContextAwareSerializer

        def get_prop_data(self, **kwargs):
            return {"test": "data"}

    view = SerializedView()
    request = rf.get("/", HTTP_X_INERTIA="true")
    request.session = SessionBase()
    view.request = request

    response = view.get(request)

    assert response.status_code == 200

    data = json.loads(response.content)

    assert context_received["request"] == request
    assert context_received["view"] == view
    assert data["props"]["has_request"] is True
    assert data["props"]["has_view"] is True
