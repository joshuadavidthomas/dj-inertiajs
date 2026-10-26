![image](https://user-images.githubusercontent.com/6599653/114456558-032e2200-9bab-11eb-88bc-a19897f417ba.png)

# dj-inertiajs

A Django-native server-side adapter for [Inertia.js](https://inertiajs.com/), forked from [inertia-django](https://github.com/inertiajs/inertia-django) 2.0.0. It speaks the same Inertia v3 protocol, so the client side is unchanged, but its API follows Django's conventions: one settings dict, system checks, class-based views, lazy responses like `TemplateResponse`, template tags, and test assertions that take the response.

Coming from inertia-django? See [Upgrading from inertia-django](docs/guide/upgrading-from-inertia-django.md). A codemod and system checks do most of the work.

The import package is `dj_inertiajs`. The distribution name is not final yet, so install it from Git for now.

## Installation

### Backend

```bash
pip install "dj-inertiajs @ git+https://github.com/joshuadavidthomas/inertia-django"
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

`python manage.py check` reports anything missing from this setup.

### Frontend

See the [client-side setup guide](docs/guide/client-side-setup.md). We recommend [django-vite](https://github.com/MrBin99/django-vite) to serve your frontend assets.

### CSRF

The middleware sets Django's CSRF cookie on every response, including requests made with Inertia v3's `useHttp`. The v3 HTTP client defaults to Laravel's cookie and header names, so configure Django's (or your project's custom names):

```javascript
createInertiaApp({
  // ...
  http: {
    xsrfCookieName: 'csrftoken',
    xsrfHeaderName: 'X-CSRFToken',
  },
})
```

## Responses

`render()` works like `django.shortcuts.render`, with a component instead of a template:

```python
from dj_inertiajs import render

from .models import Event


def index(request):
    return render(request, "Event/Index", {"events": Event.objects.all()})
```

It also takes `template_data` (extra context for the layout), and the keyword-only `template_name` (a layout other than `INERTIA["LAYOUT"]`), `status` and `headers`.

For views that only return props, use the decorator. It works on sync and `async` views, and passes any `HttpResponse` the view returns, such as a redirect, through unchanged:

```python
from dj_inertiajs import inertia


@inertia("Event/Index")
async def index(request):
    return {"events": [event async for event in Event.objects.all()]}
```

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
        return {**super().get_props(**kwargs), "events": list(kwargs["object_list"])}
```

Only what `get_props()` returns is sent, so context such as `view` or `paginator` never reaches the page by accident.

`InertiaView` renders `component` on GET, like `TemplateView`. Props can be declared on the class with `Prop`. A `Prop` whose value is a string names a method on the view, which runs only when the prop is sent:

```python
from dj_inertiajs import Prop
from dj_inertiajs.views import InertiaView


class Dashboard(InertiaView):
    component = "Dashboard"
    stats = Prop("get_stats", defer=True)

    def get_stats(self):
        return Stats.objects.summary()
```

Both take a `template_name` attribute to choose a layout.

## Props

A prop is any JSON-serializable value. A callable is called at render time, and only if the prop is sent. Props can be nested in dicts and lists; partial reloads address them by dotted path, such as `user.name`.

`Prop` wraps a value with the Inertia options that control when and how it loads:

```python
from datetime import timedelta

from dj_inertiajs import Prop

props = {
    "name": "Brandon",
    "reports": Prop(load_reports, optional=True),
    "user": Prop(lambda: request.user.username, always=True),
    "stats": Prop(load_stats, defer=True, group="charts"),
    "plans": Prop(Plan.objects.all, once=True, expires_at=timedelta(hours=1)),
    "feed": Prop(load_feed, merge="items", match_on="items.id"),
}
```

| Option | Effect |
|---|---|
| `optional=True` | Skipped on the first load. Sent only when a partial reload asks for it. |
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

To add shared props for one request, for example from a middleware, call `share()`:

```python
from dj_inertiajs import share

share(request, team=lambda: request.user.team.name)
```

The view's own props override shared props with the same name. The page reports shared keys in `sharedProps`.

## Forms and validation errors

Inertia forms read validation errors from the `errors` prop.

In a view that redirects after a POST, call `set_errors()` before redirecting. Like `messages.error()`, the errors are stored in the session and sent once, on the next page:

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

A class-based view whose context holds a bound, invalid `form`, such as a `FormView` after `form_invalid()`, sends its errors automatically.

Each field keeps its first message, the shape Inertia's `useForm` expects. Errors are included in partial reloads too.

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

A request built with `RequestFactory` gets `request.inertia` when the response renders, so views can be unit tested without the middleware.

## Flash messages

Django messages are sent as the page's top-level `flash.messages`, a list of `{"level": ..., "message": ...}`:

```python
from django.contrib import messages

messages.success(request, "Event saved.")
return redirect("events:index")
```

## Redirects

Return Django's redirects as usual. The middleware turns redirects after `PUT`, `PATCH` and `DELETE` into `303 See Other`, as Inertia requires.

To leave the Inertia app, for an external site or a non-Inertia page, return `location()`. It makes the client do a full `window.location` visit:

```python
from dj_inertiajs import location


def billing_portal(request):
    return location("https://billing.example.com/")
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
    return {"account": request.user.account}
```

`render(..., encrypt_history=True)` and an `encrypt_history = True` attribute on a class-based view do the same. To decide at runtime, set `response.encrypt_history` before the response renders.

Call `clear_history(request)` to discard the encrypted history on the next page, for example on logout:

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

To use your own encoder, set `INERTIA["JSON_ENCODER"]` to its dotted path, or set `json_encoder` on an `InertiaResponse` subclass.

## Server-side rendering

Server-side rendering runs in a separate Node server. Django posts the page to it and puts the returned HTML into the layout through `{% inertia_head %}` and `{% inertia_body %}`. If the request fails, the error is logged and the page renders client-side.

1. Install the `ssr` extra, which adds `requests`.
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
| `VERSION` | `"1.0"` | The asset version. When the client's version differs, it reloads the page. |
| `JSON_ENCODER` | `"dj_inertiajs.encoders.InertiaJsonEncoder"` | Dotted path to the JSON encoder for props. |
| `ENCRYPT_HISTORY` | `False` | Encrypt the browser history state on every page. |
| `SHARED_PROPS` | `[]` | Dotted paths to functions whose props are added to every page. |
| `SSR` | `{"ENABLED": False, "URL": "http://localhost:13714"}` | Server-side rendering. Keys you leave out keep their defaults. |

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
| `inertia.E007`–`E010` | Configuration left over from inertia-django. See [Upgrading from inertia-django](docs/guide/upgrading-from-inertia-django.md). |

## Testing

Every rendered `InertiaResponse` has the page it sent as `response.inertia`, with `component`, `props`, `url`, `version`, and the whole page object as `data`. In pytest, read it directly:

```python
def test_events(client):
    response = client.get("/events/", headers={"X-Inertia": "true"})

    assert response.inertia.component == "Event/Index"
    assert response.inertia.props["events"] == []
```

`response.inertia` works for full page loads too.

With Django's test cases, `InertiaTestCase` adds assertions that take the response first, like `assertTemplateUsed`. `self.inertia` is a client whose requests are Inertia visits:

```python
from dj_inertiajs.test import InertiaTestCase


class EventTests(InertiaTestCase):
    def test_index(self):
        response = self.inertia.get("/events/")

        self.assertComponentUsed(response, "Event/Index")
        self.assertIncludesProps(response, {"sport": "hockey"})
        self.assertHasExactProps(response, {"sport": "hockey", "events": []})
        self.assertIncludesTemplateData(response, {"title": "Events"})
        self.assertHasExactTemplateData(response, {"title": "Events"})
```

`InertiaTestCase` is `InertiaTestMixin` plus `django.test.TestCase`. Combine the mixin with `SimpleTestCase` or another test case when you need to.

## Upgrading from inertia-django

Run the codemod, then the system checks, then follow the [upgrade guide](docs/guide/upgrading-from-inertia-django.md) for the rest:

```bash
pip install "dj-inertiajs[upgrade] @ git+https://github.com/joshuadavidthomas/inertia-django"
python -m dj_inertiajs.upgrade --diff path/to/project   # review
python -m dj_inertiajs.upgrade path/to/project          # write
python manage.py check
```

## Examples

These projects use inertia-django. They show the overall setup; their Python code needs the upgrade above.

- [Django Svelte Template](https://github.com/pmdevita/Django-Svelte-Template): Inertia with Svelte and SSR.
- [Django React](https://github.com/willianantunes/inertia-django-playground): a Django and React project with CRUD, forms, authentication, Docker deployment and SSR.

## Thank you

This package builds on [inertia-django](https://github.com/inertiajs/inertia-django) by Brandon Shar and its contributors. Parts of that project were inspired by [Andres Vargas](https://github.com/zodman) and [Samuel Girardin](https://github.com/girardinsamuel).
