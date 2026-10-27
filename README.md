# dj-inertiajs

A Django-native server-side adapter for [Inertia.js](https://inertiajs.com/), forked from [inertia-django](https://github.com/inertiajs/inertia-django) 2.0.0. It speaks the same Inertia v3 protocol, so the client side is unchanged, but its API follows Django's conventions: one settings dict, system checks, class-based views, lazy responses like `TemplateResponse`, template tags, and test assertions that take the response.

dj-inertiajs is an independent project. It is not affiliated with or endorsed by the Inertia.js project or [inertia-django](https://github.com/inertiajs/inertia-django).

Coming from inertia-django? [Upgrading from inertia-django](#upgrading-from-inertia-django) lists what changed, and system checks report leftover configuration.

The distribution is `dj-inertiajs` and the import package `dj_inertiajs`. It is not on PyPI yet, so install it from Git for now.

## Installation

### Backend

```bash
pip install "dj-inertiajs @ git+https://github.com/joshuadavidthomas/dj-inertiajs"
```

Add the app and the middleware. Inertia stores some state in the session, so `SessionMiddleware` is required too:

```python
INSTALLED_APPS = [
    # ...
    "dj_inertiajs",
]

MIDDLEWARE = [
    # ...
    "django.contrib.sessions.middleware.SessionMiddleware",
    # ...
    "dj_inertiajs.middleware.InertiaMiddleware",
]

INERTIA = {
    "LAYOUT": "base.html",
}
```

Create the layout. `{% inertia_head %}` outputs server-side rendered head tags, and `{% inertia_body %}` outputs the element the client mounts on:

```django
{% load inertia %}
<!doctype html>
<html>
  <head>
    {% inertia_head %}
  </head>
  <body>
    {% inertia_body %}
  </body>
</html>
```

`python manage.py check` reports a missing middleware or `INERTIA["LAYOUT"]`. It cannot report the app missing from `INSTALLED_APPS`, because the app registers the checks; then the layout fails with "'inertia' is not a registered tag library".

### Frontend

See the [client-side setup guide](docs/guide/client-side-setup.md). We recommend [django-vite](https://github.com/MrBin99/django-vite) to serve your frontend assets.

### CSRF

There is nothing to configure. The Inertia v3 client reads the CSRF token from an `XSRF-TOKEN` cookie and sends it back in an `X-XSRF-TOKEN` header, the names Laravel uses. `InertiaMiddleware` sets that cookie on Inertia responses, next to Django's own, and passes the header to Django's CSRF check. This works for visits and `useHttp` requests alike, and with `CSRF_USE_SESSIONS` or `CSRF_COOKIE_HTTPONLY`.

## Responses

`render()` works like `django.shortcuts.render`, with a component instead of a template:

```python
from dj_inertiajs import render

from .models import Event


def index(request):
    return render(request, "Event/Index", {"events": Event.objects.values("id", "title")})
```

It also takes `template_data` (extra context for the layout), and the keyword-only `template_name` (a layout other than `INERTIA["LAYOUT"]`), `status`, `headers` and `encrypt_history` (see [History encryption](#history-encryption)).

For views that only return props, use the decorator. It works on sync and `async` views, and passes any `HttpResponse` the view returns, such as a redirect, through unchanged:

```python
from dj_inertiajs import inertia


@inertia("Event/Index")
async def index(request):
    return {"events": [event async for event in Event.objects.values("id", "title")]}
```

The decorator takes `render()`'s other options too, `template_data`, `template_name`, `status`, `headers` and `encrypt_history`, for example `@inertia("Event/Index", template_name="events/base.html", status=200)`.

Responses render lazily, like `TemplateResponse`. Until Django's handler renders the response, middleware with `process_template_response` and view decorators can change `response.component`, `response.props` and `response.template_data`.

### Class-based views

`InertiaResponseMixin` is the Inertia counterpart of `TemplateResponseMixin`: put it before a generic view and the view renders a component. Props come from `get_props()`, which receives the context the generic view built:

```python
from django.views.generic import ListView

from dj_inertiajs.views import InertiaResponseMixin


class EventList(InertiaResponseMixin, ListView):
    component = "Event/Index"
    model = Event

    def get_props(self, **kwargs):
        return {**super().get_props(**kwargs), "events": list(kwargs["object_list"].values("id", "title"))}
```

Only what `get_props()` returns is sent, so context such as `view` or `paginator` never reaches the page by accident.

`InertiaView` renders `component` on GET, like `TemplateView`. Props can be declared on the class: a `Prop` attribute, or a method decorated with `@prop`, like `@property`. A decorated method is named after its prop, takes `Prop`'s options, and runs only when the prop is sent:

```python
from dj_inertiajs import Prop, prop
from dj_inertiajs.views import InertiaView


class Dashboard(InertiaView):
    component = "Dashboard"
    plans = Prop(["basic", "pro"], once=True)

    @prop(defer=True)
    def stats(self):
        return Stats.objects.summary()
```

Both take a `template_name` attribute to choose a layout.

## Props

A prop is any JSON-serializable value. A callable is called at render time, and only if the prop is sent. An `async def` callable is awaited, so it can use the async ORM, in sync and async views alike. Props can be nested in dicts and lists; partial reloads address them by dotted path, such as `user.name`.

`Prop` wraps a value with the Inertia options that control when and how it loads:

```python
from datetime import timedelta

from dj_inertiajs import Prop

props = {
    "name": "Brandon",
    "reports": Prop(load_reports, optional=True),
    "user": Prop(lambda: request.user.username, always=True),
    "stats": Prop(load_stats, defer=True, group="charts"),
    "plans": Prop(lambda: list(Plan.objects.values("id", "name")), once=True, expires_at=timedelta(hours=1)),
    "feed": Prop(load_feed, merge="items", match_on="items.id"),
}
```

| Option | Effect |
|---|---|
| `optional=True` | Skipped on full visits. Sent on a partial reload that selects it: one whose `only` names it, or whose `except` does not. |
| `always=True` | Sent even when a partial reload asks for other props. |
| `defer=True` | Skipped on the first load. The client fetches it right after, together with other deferred props in the same `group`. |
| `group="name"` | The batch a deferred prop loads in. Requires `defer`. |
| `rescue=True` | If resolving a deferred prop raises, omit it and report it to the client instead of failing the request. Requires `defer`. |
| `merge=True` | Append to the client's existing value instead of replacing it. A path or list of paths, such as `merge="items"`, appends inside the prop. |
| `prepend=True` | Like `merge`, but prepends. |
| `deep_merge=True` | Merge nested objects and arrays recursively. |
| `match_on="id"` | Paths of keys that identify records when merging. |
| `scroll={...}` | Pagination metadata for Inertia's infinite scroll: `pageName`, `previousPage`, `nextPage` and `currentPage`. Implies `merge`. |
| `once=True` | Resolved once and kept by the client across visits. |
| `key="name"` | The client-side cache key of a `once` prop, by default its path. |
| `expires_at=...` | When a `once` prop expires: a `datetime`, a `timedelta`, or seconds from now. |
| `fresh=True` | Resolve a `once` prop on every request even if the client has it. |

Loading options exclude each other: use at most one of `optional`, `defer` and `always`. `Prop` raises `ValueError` for combinations that have no effect, such as `group` without `defer`.

For example, an infinite-scroll list whose first page loads after the initial render:

```python
"players": Prop(
    load_players,
    scroll={"pageName": "page", "previousPage": None, "nextPage": 2, "currentPage": 1},
    defer=True,
)
```

See [Partial reloads](docs/guide/partial-reloads.md) and the Inertia docs on [deferred props](https://inertiajs.com/deferred-props) for how the client uses these.

## Shared data

Props that every page needs, such as the signed-in user, come from functions listed in `INERTIA["SHARED_PROPS"]`, like template context processors. Each takes the request and returns a dict:

```python
# myapp/inertia.py
from dj_inertiajs import Prop


def shared(request):
    return {
        "app_name": "Scoreboard",
        "user": Prop(lambda: request.user.get_username(), always=True),
    }
```

```python
INERTIA = {
    "LAYOUT": "base.html",
    "SHARED_PROPS": ["myapp.inertia.shared"],
}
```

When a middleware works out a value, such as the current team, it puts it on the request, the way `AuthenticationMiddleware` sets `request.user`, and a shared-props function sends it:

```python
# middleware
request.team = Team.objects.get(slug=...)

# myapp/inertia.py, also listed in SHARED_PROPS
def team(request):
    return {"team": request.team.name} if hasattr(request, "team") else {}
```

Later functions in the list override earlier ones, and the view's own props override them all. The page reports shared keys in `sharedProps`. To add props to particular views from a decorator or middleware, change `response.props` before the response renders, as described in [Responses](#responses).

## Forms and validation errors

Inertia forms read validation errors from the `errors` prop.

Call `set_errors()` in the view that validates the form. Like Django messages, the errors are stored in the session and sent once, with the next Inertia page that renders. In the usual redirect-after-POST view, that is the page the redirect leads to:

```python
from django.shortcuts import redirect

from dj_inertiajs import set_errors


def create_event(request):
    form = EventForm(request.POST)
    if not form.is_valid():
        set_errors(request, form)
        return redirect("events:create")
    form.save()
    return redirect("events:index")
```

A view that renders a page instead of redirecting sends the errors with that page, since it is the next one rendered. If the client reloads because the asset version changed, the errors wait for the reloaded page.

A class-based view whose context holds a bound, invalid `form`, such as a `FormView` after `form_invalid()`, sends its errors automatically.

Each field keeps its first message, the shape Inertia's `useForm` expects. Errors that belong to no field, from `Form.clean()`, are under Django's `"__all__"` key. `set_errors()` also takes a formset: its forms' errors are keyed `"<prefix>.<index>.<field>"`, such as `"sports.1.name"`, and its own errors `"<prefix>"`. Errors are included in partial reloads too.

To send errors in another shape, such as every message per field, point `INERTIA["FORM_ERRORS"]` at a function that takes a form, formset or dict and returns the `errors` prop.

## The request

`InertiaMiddleware` attaches `request.inertia`, the way `SessionMiddleware` attaches `request.session`. Like django-htmx's `request.htmx`, it only describes the request. It is truthy when the Inertia client made the request:

```python
if request.inertia:                 # an Inertia visit, not a full page load
    request.inertia.version         # the client's asset version
    request.inertia.partial_component, request.inertia.partial_data, request.inertia.partial_except
    request.inertia.is_partial("Event/Index")
```

For type checkers, annotate views with `InertiaHttpRequest`:

```python
from dj_inertiajs.request import InertiaHttpRequest


def show(request: InertiaHttpRequest, pk: int):
    if request.inertia.is_partial("Event/Show"):
        ...
```

A request built with `RequestFactory` has no `request.inertia` until the view builds an Inertia response, and no `request.session`, which rendering needs. Test views with the test client, which runs the middleware.

## Flash messages

Django messages are sent as the page's top-level `flash.messages`, a list of `{"level": ..., "message": ...}`:

```python
from django.contrib import messages

messages.success(request, "Event saved.")
return redirect("events:index")
```

## Redirects

Return Django's redirects as usual. The middleware turns redirects after `PUT`, `PATCH` and `DELETE` into `303 See Other`, as Inertia requires.

To leave the Inertia app, for an external site or a non-Inertia page, return an `InertiaLocation`. It is the Inertia counterpart of `HttpResponseRedirect`: on an Inertia visit the client does a full `window.location` visit, and on a full page load the middleware sends an ordinary redirect:

```python
from dj_inertiajs import InertiaLocation


def billing_portal(request):
    return InertiaLocation("https://billing.example.com/")
```

When a request URL has a fragment, such as `/article/old-slug#section`, redirect with `preserve_fragment=True` so the client keeps the fragment on the new URL. `dj_inertiajs.redirect` is `django.shortcuts.redirect` with Inertia's options:

```python
from dj_inertiajs import redirect


def rename_article(request, slug):
    article = Article.objects.get(slug=slug)
    article.slug = request.POST["new_slug"]
    article.save()
    return redirect("articles:show", slug=article.slug, preserve_fragment=True)
```

## History encryption

Inertia can [encrypt the history state](https://inertiajs.com/history-encryption) it keeps in the browser, for pages with sensitive data. It needs HTTPS, because it uses `window.crypto.subtle`.

Turn it on for every page with `INERTIA["ENCRYPT_HISTORY"] = True`, or per view:

```python
from dj_inertiajs import inertia


@inertia("Account/Show", encrypt_history=True)  # False opts out
def account(request):
    return {"email": request.user.email}
```

`render(..., encrypt_history=True)` and an `encrypt_history = True` attribute on a class-based view do the same. To decide at runtime, set `response.encrypt_history` before the response renders.

Call `clear_history(request)` to discard the encrypted history when the next Inertia page renders, for example on logout. Like `set_errors()`, that is the page after a redirect, or the page the view renders itself:

```python
from django.contrib.auth import views as auth_views

from dj_inertiajs import clear_history


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        clear_history(request)
        return response
```

## Serialization

Props are encoded with `INERTIA["JSON_ENCODER"]`, by default `dj_inertiajs.encoders.InertiaJsonEncoder`. It extends `DjangoJSONEncoder`, which handles dates, times, decimals and UUIDs, and adds two things:

- Any class with an `InertiaMeta` inner class is encoded as the attributes listed in `InertiaMeta.fields`.
- A `QuerySet` is encoded as a list of its items, so `Event.objects.values("id", "title")` sends dicts.

Like `JsonResponse`, it does not encode models on its own: a model without `InertiaMeta` raises `TypeError`. Everything a page receives is visible in the browser, so name the fields to send, in the view or on the model:

```python
class User(models.Model):
    name = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    created_at = models.DateField(auto_now_add=True)

    class InertiaMeta:
        fields = ("id", "name", "created_at")
```

To use your own encoder, set `INERTIA["JSON_ENCODER"]` to its dotted path, or set `json_encoder` on an `InertiaResponse` subclass and return it from the view, or set it as a class-based view's `response_class`.

## Server-side rendering

Server-side rendering runs in a separate Node server. Django posts the page to it and puts the returned HTML into the layout through `{% inertia_head %}` and `{% inertia_body %}`. If the request fails, the error is logged and the page renders client-side.

1. Install the `ssr` extra, which adds `requests`: `pip install "dj-inertiajs[ssr] @ git+https://github.com/joshuadavidthomas/dj-inertiajs"`.
2. Turn it on:

   ```python
   INERTIA = {
       "LAYOUT": "base.html",
       "SSR": {"ENABLED": True, "URL": "http://localhost:13714"},
   }
   ```

3. Set up the frontend as described in the Inertia docs on [server-side rendering](https://inertiajs.com/server-side-rendering).

## Settings

All settings live in one `INERTIA` dict:

| Key | Default | Purpose |
|---|---|---|
| `LAYOUT` | none, required | The layout template for full page loads. Views can choose another with `template_name`. |
| `VERSION` | `"1.0"` | The asset version, or a callable that returns it. When the client's version differs, it reloads the page. |
| `JSON_ENCODER` | `"dj_inertiajs.encoders.InertiaJsonEncoder"` | Dotted path to the JSON encoder for props. |
| `ENCRYPT_HISTORY` | `False` | Encrypt the browser history state on every page. |
| `SHARED_PROPS` | `[]` | Dotted paths to functions whose props are added to every page. |
| `FORM_ERRORS` | `"dj_inertiajs.forms.error_messages"` | Dotted path to a function that turns a form, formset or dict of errors into the `errors` prop. |
| `SSR` | `{"ENABLED": False, "URL": "http://localhost:13714"}` | Server-side rendering. Keys you leave out keep their defaults. |

To change the version whenever your assets change, set `VERSION` to a callable, for example one that hashes your build manifest:

```python
import hashlib
from functools import cache


@cache
def asset_version():
    return hashlib.md5((BASE_DIR / "frontend/dist/manifest.json").read_bytes()).hexdigest()


INERTIA = {"LAYOUT": "base.html", "VERSION": asset_version}
```

## System checks

`python manage.py check` reports configuration problems before the first request:

| ID | Problem |
|---|---|
| `inertia.E001` | Unknown key in `INERTIA`, such as a typo. |
| `inertia.E002` | `INERTIA["LAYOUT"]` is not set. |
| `inertia.E003` | Server-side rendering is on, but `requests` is not installed. |
| `inertia.E004` | `InertiaMiddleware` is not in `MIDDLEWARE`. |
| `inertia.E005` | `SessionMiddleware` is not in `MIDDLEWARE`. |
| `inertia.E006` | An entry in `INERTIA["SHARED_PROPS"]` cannot be imported. |
| `inertia.E011` | `INERTIA["JSON_ENCODER"]` or `INERTIA["FORM_ERRORS"]` cannot be imported. |
| `inertia.E012` | `INERTIA["VERSION"]` is neither a string nor a callable. |
| `inertia.E007`–`E010` | Configuration left over from inertia-django. See [Upgrading from inertia-django](docs/guide/upgrading-from-inertia-django.md). |

## Testing

Every rendered `InertiaResponse` has the page it sent as `response.inertia`, with `component`, `props`, `url`, `version`, and the whole page object as `data`. In pytest, read it directly:

```python
def test_events(client):
    response = client.get("/events/", headers={"X-Inertia": "true"})

    assert response.inertia.component == "Event/Index"
    assert response.inertia.props["events"] == []
```

`response.inertia` works for full page loads too. `dj_inertiajs.test.InertiaClient` is a Django test client whose requests are Inertia visits; pass `inertia=False` to a request for a full page load.

With Django's test cases, `InertiaTestCase` sets `client_class` to `InertiaClient` (and `async_client_class` to `AsyncInertiaClient`), and adds assertions that take the response first, like `assertTemplateUsed`:

```python
from dj_inertiajs.test import InertiaTestCase


class EventTests(InertiaTestCase):
    def test_index(self):
        response = self.client.get("/events/")

        self.assertComponentUsed(response, "Event/Index")
        self.assertPropsContain(response, {"sport": "hockey"})
        self.assertPropsEqual(response, {"sport": "hockey", "events": []})

    def test_first_load(self):
        response = self.client.get("/events/", inertia=False)

        self.assertTemplateDataContain(response, {"title": "Events"})
        self.assertTemplateDataEqual(response, {"title": "Events"})
```

`InertiaTestCase` is `InertiaTestMixin` plus `django.test.TestCase`. Combine the mixin with `SimpleTestCase` or another test case when you need to.

## Upgrading from inertia-django

This package breaks inertia-django's API on purpose, so that it follows Django's conventions instead of the Laravel adapter's. Nothing old is kept for compatibility. Most rows link to the section of the [upgrade guide](docs/guide/upgrading-from-inertia-django.md) that explains the change.

### What stays the same

- The Inertia v3 protocol and page object. The client side does not change.
- `render(request, component, props)` and the `@inertia("Component")` decorator.
- `clear_history(request)`, flash messages from `django.contrib.messages`, and `InertiaMeta`.

### What changed

| Area | inertia-django | dj-inertiajs |
|---|---|---|
| [Settings](docs/guide/upgrading-from-inertia-django.md#settings) | Flat `INERTIA_*` settings; the encoder is a class | One `INERTIA` dict; the encoder is a dotted path; `VERSION` may be a callable |
| [Layout](docs/guide/upgrading-from-inertia-django.md#layout-templates) | One global layout that defines `{% block inertia %}` | Any template, using `{% inertia_head %}` and `{% inertia_body %}`, chosen per view with `template_name` |
| [Props](docs/guide/upgrading-from-inertia-django.md#props) | `defer()`, `merge()`, `optional()` and five more helpers | One `Prop` class with keyword options |
| [Views](docs/guide/upgrading-from-inertia-django.md#views) | Function views only; `@inertia` takes only a component; no async | Class-based views with `@prop` methods; `@inertia` and `render()` take `template_name`, `status`, `headers` and `encrypt_history`; `async def` views and props work |
| [Responses](docs/guide/upgrading-from-inertia-django.md#responses-render-lazily) | Rendered in the constructor | Rendered lazily, like `TemplateResponse`, so middleware and decorators can change `response.props` |
| [Shared data](docs/guide/upgrading-from-inertia-django.md#shared-data) | `share(request, ...)` from a custom middleware | Functions listed in `INERTIA["SHARED_PROPS"]`, like context processors |
| [Validation errors](docs/guide/upgrading-from-inertia-django.md#validation-errors) | Not handled | `set_errors(request, form)`, and invalid forms in class-based views; formsets supported |
| [Redirects](docs/guide/upgrading-from-inertia-django.md#redirects) | `preserve_fragment(request)`; `location(url)` | `redirect(..., preserve_fragment=True)`; `InertiaLocation(url)` |
| [The request](docs/guide/upgrading-from-inertia-django.md#the-request) | `request.inertia` holds shared props | `request.inertia` describes the request, like django-htmx's `request.htmx` |
| [History encryption](docs/guide/upgrading-from-inertia-django.md#history-encryption) | `encrypt_history(request)` inside the view | `encrypt_history=True` on the decorator, `render()` or the class-based view |
| [Serialization](docs/guide/upgrading-from-inertia-django.md#serialization) | Models encoded with every editable field except `password` | Models need `InertiaMeta` or explicit fields, like `JsonResponse` |
| [Tests](docs/guide/upgrading-from-inertia-django.md#tests) | Stateful assertions read the last response; `self.inertia` client | Assertions take the response; `self.client` makes Inertia visits; `response.inertia` in pytest |
| [CSRF](docs/guide/upgrading-from-inertia-django.md#csrf) | The client is configured with Django's cookie and header names; cookie set on every response | Works with the client's default `XSRF-TOKEN` names; cookie set only on Inertia responses |
| Configuration errors | Found at request time | Reported by `manage.py check` |

### How to upgrade

The [upgrade guide](docs/guide/upgrading-from-inertia-django.md) shows each change before and after, and lists them in one table with how a missed change shows itself. `python manage.py check` reports leftover settings, middleware, app and layout, and names the guide section that explains each fix.

## Examples

These projects use inertia-django. They show the overall setup; their Python code needs the upgrade above.

- [Django Svelte Template](https://github.com/pmdevita/Django-Svelte-Template): Inertia with Svelte and SSR.
- [Django React](https://github.com/willianantunes/inertia-django-playground): a Django and React project with CRUD, forms, authentication, Docker deployment and SSR.

## Thank you

This package builds on [inertia-django](https://github.com/inertiajs/inertia-django) by Brandon Shar and its contributors. Parts of that project were inspired by [Andres Vargas](https://github.com/zodman) and [Samuel Girardin](https://github.com/girardinsamuel).

## License

dj-inertiajs is licensed under the MIT license. See the [`LICENSE`](LICENSE) file for more information.
