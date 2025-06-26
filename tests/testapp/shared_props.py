from __future__ import annotations

from typing import Any

from django.http import HttpRequest


def user_props(request: HttpRequest) -> dict[str, Any]:
    if request.user.is_authenticated:
        return {
            "auth": {
                "user": {
                    "id": request.user.id,
                    "username": request.user.username,
                    "email": request.user.email,
                },
                "is_authenticated": True,
            }
        }
    return {
        "auth": {
            "user": None,
            "is_authenticated": False,
        }
    }


def app_props(request: HttpRequest) -> dict[str, Any]:
    return {
        "app": {
            "name": "Test App",
            "version": "1.0.0",
            "debug": request.META.get("DEBUG", False),
        }
    }


def share_test_props(request: HttpRequest) -> dict[str, Any]:
    return {
        "position": "goalie",
        "number": 29,
    }


static_props = {
    "static": {
        "version": "1.0.0",
        "features": ["inertia", "django"],
    }
}
