import asyncio

from django import forms
from django.contrib import messages
from django.http.response import HttpResponse, JsonResponse
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect
from django.shortcuts import render as django_render
from django.utils.decorators import decorator_from_middleware
from django.views.generic import FormView, ListView

from dj_inertiajs import (
    InertiaLocation,
    Prop,
    clear_history,
    inertia,
    prop,
    render,
    set_errors,
)
from dj_inertiajs import redirect as inertia_redirect
from dj_inertiajs.request import (
    INERTIA_SESSION_CLEAR_HISTORY,
    INERTIA_SESSION_PRESERVE_FRAGMENT,
)
from dj_inertiajs.views import InertiaResponseMixin, InertiaView

from .models import Sport


class PlayerMiddleware:
    """Works something out for the request, like AuthenticationMiddleware;
    a SHARED_PROPS function sends it."""

    def __init__(self, get_response):
        self.get_response = get_response

    def process_request(self, request):
        request.player = dict(
            position=lambda: "goalie",
            number=29,
        )


def test(request):
    return HttpResponse("Hey good stuff")


@inertia("TestComponent")
def empty_test(request):
    return {}


def redirect_test(request):
    return redirect(empty_test)


@inertia("TestComponent")
def inertia_redirect_test(request):
    return redirect(empty_test)


def external_redirect_test(request):
    return InertiaLocation("http://foobar.com/")


@inertia("TestComponent")
def props_test(request):
    return {
        "name": "Brandon",
        "sport": "Hockey",
    }


def template_data_test(request):
    return render(
        request,
        "TestComponent",
        template_data={
            "name": "Brian",
            "sport": "Basketball",
        },
    )


@inertia("TestComponent")
def optional_test(request):
    return {
        "name": "Brian",
        "sport": Prop(lambda: "Basketball", optional=True),
        "grit": Prop(lambda: "intense", optional=True),
    }


@inertia("TestComponent")
def defer_test(request):
    return {"name": "Brian", "sport": Prop(lambda: "Basketball", defer=True)}


@inertia("TestComponent")
def defer_group_test(request):
    return {
        "name": "Brian",
        "sport": Prop(lambda: "Basketball", defer=True, group="group"),
        "team": Prop(lambda: "Bulls", defer=True, group="group"),
        "grit": Prop(lambda: "intense", defer=True),
    }


@inertia("TestComponent")
def merge_test(request):
    return {
        "name": "Brandon",
        "sport": Prop(lambda: "Hockey", merge=True),
        "team": Prop(lambda: "Penguins", defer=True, merge=True),
    }


@inertia("TestComponent")
def complex_props_test(request):
    return {
        "person": {
            "name": lambda: "Brandon",
        }
    }


@decorator_from_middleware(PlayerMiddleware)
@inertia("TestComponent")
def share_test(request):
    return {
        "name": "Brandon",
    }


@inertia("TestComponent", encrypt_history=True)
def encrypt_history_test(request):
    return {}


@inertia("TestComponent", encrypt_history=False)
def encrypt_history_false_test(request):
    return {}


def encrypt_history_type_error_test(request):
    return render(request, "TestComponent", encrypt_history="foo")


class EncryptedHistoryView(InertiaView):
    component = "TestComponent"
    encrypt_history = True


@inertia("TestComponent")
def clear_history_test(request):
    clear_history(request)
    return {}


@inertia("TestComponent")
def clear_history_redirect_test(request):
    clear_history(request)
    return redirect(empty_test)


@inertia("TestComponent")
def clear_history_type_error_test(request):
    request.session[INERTIA_SESSION_CLEAR_HISTORY] = "foo"
    return {}


# ---------------------------------------------------------------------------
# Once props (Inertia v3)
# ---------------------------------------------------------------------------


@inertia("TestComponent")
def once_test(request):
    return {
        "name": "Brandon",
        "plans": Prop(lambda: ["basic", "pro"], once=True),
    }


@inertia("TestComponent")
def once_shared_test(request):
    """Rendered with once_plans in SHARED_PROPS, to verify shared once props
    appear in onceProps and are skipped when the client already holds them."""
    return {"name": "Brandon"}


@inertia("TestComponent")
def once_fresh_test(request):
    return {
        "name": "Brandon",
        "plans": Prop(lambda: ["basic", "pro"], once=True, fresh=True),
    }


# ---------------------------------------------------------------------------
# preserveFragment (Inertia v3)
# ---------------------------------------------------------------------------


def preserve_fragment_redirect_test(request):
    """Redirects with preserve_fragment; the flag travels via the session to
    the next Inertia response."""
    return inertia_redirect(empty_test, preserve_fragment=True)


@inertia("TestComponent")
def preserve_fragment_type_error_test(request):
    request.session[INERTIA_SESSION_PRESERVE_FRAGMENT] = "not-a-bool"
    return {}


# ---------------------------------------------------------------------------
# preserveErrors / shared errors partial-reload filtering (Inertia v3)
# ---------------------------------------------------------------------------


@inertia("TestComponent")
def preserve_errors_test(request):
    return {"name": "Brandon"}


# ---------------------------------------------------------------------------
# Infinite scroll / X-Inertia-Infinite-Scroll-Merge-Intent (Inertia v3)
# ---------------------------------------------------------------------------


@inertia("TestComponent")
def infinite_scroll_test(request):
    return {
        "name": "Brandon",
        "items": Prop(lambda: ["item1", "item2"], merge=True),
    }


@inertia("TestComponent")
def v3_nested_props_test(request):
    return {
        "config": {
            "locale": Prop(lambda: "en-US", once=True, key="locale"),
            "timezone": "UTC",
        },
        "user": {"name": "Brandon", "token": "secret-token"},
    }


def csrf_rotate_test(request):
    rotate_token(request)
    return JsonResponse({"rotated": True})


def v3_post_test(request):
    # A visit redirects back to a page; a useHttp request gets JSON.
    if request.inertia:
        return redirect("/v3/nested/")
    return JsonResponse({"saved": True})


@inertia("TestComponent")
def v3_merge_props_test(request):
    return {
        "feed": Prop(
            lambda: {"items": [{"id": 2, "name": "Brandon"}]},
            merge="items",
            match_on="items.id",
        ),
        "chat": Prop(
            lambda: {"messages": [{"id": 2, "body": "Hockey"}]},
            deep_merge=True,
            match_on="messages.id",
        ),
    }


@inertia("TestComponent")
def v3_scroll_test(request):
    return {
        "players": Prop(
            lambda: ["Brian", "Brandon"],
            scroll={
                "pageName": "page",
                "previousPage": None,
                "nextPage": 2,
                "currentPage": 1,
            },
        )
    }


@inertia("TestComponent")
def v3_deferred_scroll_test(request):
    return {
        "score": Prop(lambda: "Brandon", always=True),
        "players": Prop(
            lambda: ["Brian", "Brandon"],
            scroll={
                "pageName": "page",
                "previousPage": None,
                "nextPage": 2,
                "currentPage": 1,
            },
            defer=True,
        ),
    }


@inertia("TestComponent")
def v3_deferred_once_test(request):
    return {
        "report": Prop(
            lambda: {"winner": "Brandon"},
            defer=True,
            once=True,
            key="cached-report",
        )
    }


@inertia("TestComponent")
def messages_test(request):
    messages.success(request, "Profile saved!")
    return {}


@inertia("TestComponent")
def no_messages_test(request):
    return {}


class AddPropMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def process_template_response(self, request, response):
        response.props["added"] = "by middleware"
        return response


@decorator_from_middleware(AddPropMiddleware)
@inertia("TestComponent")
def template_response_middleware_test(request):
    return {"name": "Brandon"}


@inertia("TestComponent")
async def async_test(request):
    return {"name": "Brandon"}


def shared_props(request):
    return {"app_name": "Scoreboard", "user": Prop(lambda: "Brandon", always=True)}


def set_errors_test(request):
    form = SportForm(request.POST)
    if not form.is_valid():
        set_errors(request, form)
    return redirect(empty_test)


@inertia("TestComponent")
def overrides_shared_test(request):
    return {"app_name": "From the view"}


def other_layout_test(request):
    return render(request, "TestComponent", template_name="other_layout.html")


class OtherLayoutView(InertiaView):
    component = "TestComponent"
    template_name = "other_layout.html"


def plain_layout_test(request):
    return django_render(request, "layout.html", {"name": "Brian"})


def status_test(request):
    return render(request, "TestComponent", {"name": "Brandon"}, status=201)


class DashboardView(InertiaView):
    component = "Dashboard"
    plans = Prop(["basic", "pro"], once=True)
    motto = Prop("get_stats")  # a string is just a string

    @prop(defer=True)
    async def stats(self):
        return {"wins": 3}

    def get_props(self, **kwargs):
        return {**super().get_props(**kwargs), "team": kwargs["team"]}


class SportListView(InertiaResponseMixin, ListView):
    component = "Sports/Index"
    model = Sport

    def get_props(self, **kwargs):
        names = [sport.name for sport in kwargs["object_list"]]
        return {**super().get_props(**kwargs), "sports": names}


class SportForm(forms.Form):
    name = forms.CharField()


class SportFormView(InertiaResponseMixin, FormView):
    component = "Sports/Create"
    form_class = SportForm
    success_url = "/empty/"


class MissingComponentView(InertiaView):
    pass


@inertia("TestComponent")
def request_details_test(request):
    return {
        "inertia": bool(request.inertia),
        "partial_data": request.inertia.partial_data,
        "is_partial": request.inertia.is_partial("TestComponent"),
    }


@inertia(
    "TestComponent",
    template_name="other_layout.html",
    status=202,
    headers={"X-Team": "Penguins"},
)
def decorated_options_test(request):
    return {}


async def load_score():
    await asyncio.sleep(0)
    return 3


@inertia("TestComponent")
def async_props_test(request):
    return {"score": load_score, "deferred": Prop(load_score, defer=True)}


@inertia("TestComponent")
async def async_view_async_props_test(request):
    return {"score": load_score}


def all_error_messages(errors):
    return {
        field: [str(m) for m in messages] for field, messages in errors.errors.items()
    }


def player_props(request):
    return getattr(request, "player", {})


def once_plans(request):
    return {"plans": Prop(lambda: ["basic", "pro"], once=True)}


def shared_errors(request):
    """Shared validation errors, to verify that partial reloads exclude them
    unless X-Inertia-Partial-Data asks for them."""
    return {"errors": {"email": "required"}}
