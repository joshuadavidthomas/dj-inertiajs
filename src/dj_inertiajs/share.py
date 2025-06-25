from __future__ import annotations

__all__ = ["share"]


def share(request, **kwargs):
    request.inertia.share(**kwargs)
