from typing import Any

from django import template
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

register = template.Library()

CONTEXT_KEY = "_inertia"


@register.simple_tag(takes_context=True)
def inertia_head(context: template.Context) -> SafeString:
    """Output the head tags from server-side rendering, or nothing."""
    page = context.get(CONTEXT_KEY)
    return mark_safe(str(page["head"]) if page else "")


@register.simple_tag(takes_context=True)
def inertia_body(context: template.Context, id: str = "app") -> SafeString:
    """Output the Inertia root element and its page data.

    With server-side rendering this is the rendered body. Otherwise it is the
    page JSON in a script tag followed by an empty root ``<div>``, which the
    client mounts on. ``id`` must match the client's ``id`` option.
    """
    page: dict[str, Any] | None = context.get(CONTEXT_KEY)
    if not page:
        return mark_safe("")
    if page["body"] is not None:
        return mark_safe(str(page["body"]))
    # page["json"] is already escaped for embedding in a script tag.
    return format_html(
        '<script data-page="{}" type="application/json">{}</script>\n  <div id="{}"></div>',
        id,
        mark_safe(page["json"]),
        id,
    )
