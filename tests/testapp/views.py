from __future__ import annotations

from django.http.response import HttpResponse
from django.shortcuts import redirect

from dj_inertiajs import defer
from dj_inertiajs import inertia
from dj_inertiajs import lazy
from dj_inertiajs import location
from dj_inertiajs import merge
from dj_inertiajs import optional
from dj_inertiajs import render
from dj_inertiajs.http import INERTIA_SESSION_CLEAR_HISTORY
from dj_inertiajs.http import clear_history
from dj_inertiajs.http import encrypt_history


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
    return location("http://foobar.com/")


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
def lazy_test(request):
    return {
        "name": "Brian",
        "sport": lazy(lambda: "Basketball"),
        "grit": lazy(lambda: "intense"),
    }


@inertia("TestComponent")
def optional_test(request):
    return {
        "name": "Brian",
        "sport": optional(lambda: "Basketball"),
        "grit": optional(lambda: "intense"),
    }


@inertia("TestComponent")
def defer_test(request):
    return {"name": "Brian", "sport": defer(lambda: "Basketball")}


@inertia("TestComponent")
def defer_group_test(request):
    return {
        "name": "Brian",
        "sport": defer(lambda: "Basketball", "group"),
        "team": defer(lambda: "Bulls", "group"),
        "grit": defer(lambda: "intense"),
    }


@inertia("TestComponent")
def merge_test(request):
    return {
        "name": "Brandon",
        "sport": merge(lambda: "Hockey"),
        "team": defer(lambda: "Penguins", merge=True),
    }


@inertia("TestComponent")
def complex_props_test(request):
    return {
        "person": {
            "name": lambda: "Brandon",
        }
    }


@inertia("TestComponent")
def share_test(request):
    return {
        "name": "Brandon",
    }


@inertia("TestComponent")
def encrypt_history_test(request):
    encrypt_history(request)
    return {}


@inertia("TestComponent")
def encrypt_history_false_test(request):
    encrypt_history(request, False)
    return {}


@inertia("TestComponent")
def encrypt_history_type_error_test(request):
    encrypt_history(request, "foo")
    return {}


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
