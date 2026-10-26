# Upgrading from inertia-django

This package is a separate, Django-native adapter forked from inertia-django 2.0.0. Its API differs on purpose: settings live in one dict, props are declared with a `Prop` class, layouts use template tags, and the test helpers take the response. Nothing from the old API is kept for compatibility, so an upgraded project uses only the new API.

The protocol the client sees is the same as inertia-django 2.0's, which targets Inertia v3. Coming from 2.0, you do not need to change your frontend. Coming from 1.x, which targets Inertia v2, also follow [From inertia-django 1.x](#from-inertia-django-1-x).

## How to upgrade

Work through three steps. Each one shortens the list for the next.

1. **Run the codemod.** It rewrites imports, prop helpers, request helpers such as `share()`, settings, the `MIDDLEWARE` and `INSTALLED_APPS` entries, and test assertions:

   ```shell
   pip install "<package>[upgrade]"
   python -m django_inertia.upgrade --diff path/to/project   # review the changes
   python -m django_inertia.upgrade path/to/project          # write them
   ```

   It prints every change it could not make on its own.

2. **Run the system checks.** `python manage.py check` reports each old pattern that is still in use, with a link to the section below that explains the fix. The codemod is optional; without it, the checks still list everything.

3. **Fix the rest by hand** using the sections below, then uninstall `inertia-django`.

## From inertia-django 1.x

inertia-django 1.x targets the Inertia v2 client. This package needs the v3 client, so a project on 1.x also upgrades its frontend. The server-side changes below cover everything else.

1. **Install the v3 client adapter** for your framework:

   ::: code-group

   ```shell [Vue]
   npm install @inertiajs/vue3@^3
   ```

   ```shell [React]
   npm install @inertiajs/react@^3
   ```

   ```shell [Svelte]
   npm install @inertiajs/svelte@^3
   ```

   :::

2. **Configure Django's CSRF names.** The v3 HTTP client defaults to Laravel's `XSRF-TOKEN` cookie and `X-XSRF-TOKEN` header:

   ```js
   createInertiaApp({
     // resolve and setup...
     http: {
       xsrfCookieName: "csrftoken",
       xsrfHeaderName: "X-CSRFToken",
     },
   })
   ```

   If you set `CSRF_COOKIE_NAME` or `CSRF_HEADER_NAME`, use those names instead.

3. **Use Django messages for one-time notices.** Messages from `django.contrib.messages` are sent as the page's top-level `flash.messages`. Replace props you used for notices with `messages.success()` and the like.

4. **Review caching and partial reloads.**
   - Every Inertia response varies on `X-Inertia`. Make sure your reverse proxy or CDN honors the `Vary` header.
   - Partial reloads accept nested paths, such as `only: ["account.plans"]`, and `except`. Metadata such as `mergeProps` and `onceProps` only lists props included in that response.

Then check that a full page visit mounts the v3 client, a form submission sends the CSRF header, and flash messages appear once after a redirect.

## Install and app name

The import package is `django_inertia`. Both packages can be installed at the same time while you migrate, but only one may be in `INSTALLED_APPS` and `MIDDLEWARE`.

```python
INSTALLED_APPS = [
    # ...
    "django_inertia",   # was "inertia"
]
```

The codemod rewrites this entry. The `inertia.E009` check reports it if it is left.

## Settings

The `INERTIA_*` settings are replaced by one `INERTIA` dict. `JSON_ENCODER` is now a dotted import path instead of a class, so `settings.py` does not import application code.

| inertia-django | django_inertia |
|---|---|
| `INERTIA_LAYOUT` | `INERTIA["LAYOUT"]` |
| `INERTIA_VERSION` | `INERTIA["VERSION"]` |
| `INERTIA_JSON_ENCODER = MyEncoder` | `INERTIA["JSON_ENCODER"] = "myapp.encoders.MyEncoder"` |
| `INERTIA_ENCRYPT_HISTORY` | `INERTIA["ENCRYPT_HISTORY"]` |
| `INERTIA_SSR_ENABLED` | `INERTIA["SSR"]["ENABLED"]` |
| `INERTIA_SSR_URL` | `INERTIA["SSR"]["URL"]` |

```python
# Before
INERTIA_LAYOUT = "base.html"
INERTIA_SSR_ENABLED = True

# After
INERTIA = {
    "LAYOUT": "base.html",
    "SSR": {"ENABLED": True},
}
```

The codemod rewrites module-level `INERTIA_*` assignments. The `inertia.E007` check reports any that are left, and `inertia.E001` reports unknown keys in `INERTIA`, such as typos.

## Middleware

```python
MIDDLEWARE = [
    # ...
    "django_inertia.middleware.InertiaMiddleware",   # was "inertia.middleware.InertiaMiddleware"
]
```

`SessionMiddleware` is now required and checked (`inertia.E005`). inertia-django needed it too, but only failed on the first request.

The codemod rewrites this entry. The `inertia.E008` check reports the old path if it is left.

## Layout templates

Layouts no longer define `{% block inertia %}` and `{% block inertia_head %}` for the package to fill. Instead they place the page with template tags:

```django
{# Before #}
<head>{% block inertia_head %}{% endblock %}</head>
<body>{% block inertia %}{% endblock %}</body>

{# After #}
{% load inertia %}
<head>{% inertia_head %}</head>
<body>{% inertia_body %}</body>
```

- `{% inertia_head %}` outputs the head tags from server-side rendering, and nothing without it.
- `{% inertia_body %}` outputs the root element. Pass `id="..."` if your client uses an `id` other than `app`.
- Outside an Inertia response both tags output nothing, so the same layout can serve ordinary Django views.

`INERTIA["LAYOUT"]` is now only the default. A view can choose its own layout with `render(..., template_name="...")` or a `template_name` attribute on a class-based view.

The codemod does not edit templates. The `inertia.E010` check names the layout template that still uses the old blocks. A layout that is not updated renders without the page, so the app does not mount.

## Props

The prop helper functions are replaced by one `Prop` class. Each helper becomes a keyword option:

| inertia-django | django_inertia |
|---|---|
| `optional(f)` | `Prop(f, optional=True)` |
| `lazy(f)` | `Prop(f, optional=True)` |
| `always(f)` | `Prop(f, always=True)` |
| `defer(f)` | `Prop(f, defer=True)` |
| `defer(f, "group")` | `Prop(f, defer=True, group="group")` |
| `defer(f, merge=True)` | `Prop(f, defer=True, merge=True)` |
| `merge(f)` | `Prop(f, merge=True)` |
| `merge(f, append="items")` | `Prop(f, merge="items")` |
| `merge(f, prepend=True)` | `Prop(f, prepend=True)` |
| `deep_merge(f, match_on="id")` | `Prop(f, deep_merge=True, match_on="id")` |
| `once(f)` | `Prop(f, once=True)` |
| `once(f, fresh=True)` | `Prop(f, once=True, fresh=True)` |
| `scroll(f, meta)` | `Prop(f, scroll=meta)` |
| `scroll(f, meta, wrapper="data")` | `Prop(f, scroll=meta, merge="data")` |

The other keywords, such as `key`, `expires_at` and `rescue`, keep their names.

`Prop` raises `ValueError` for options that cannot be combined, where the helpers ignored them silently. For example, `group` needs `defer=True`, `match_on` needs merging, and `fresh` needs `once=True`. If an upgraded view raises one of these errors, the option never had an effect; remove it.

The codemod rewrites calls to the helpers it can trace to an `inertia` import.

## Views

`render()` and the `@inertia` decorator keep their shape. Two things change:

- `@inertia` now works on `async def` views.
- The extra arguments of `render()` and `InertiaResponse` are keyword-only: `template_name`, `status` and `headers`. `InertiaResponse` no longer takes `HttpResponse`'s positional arguments.

Class-based views are new, in `django_inertia.views`:

```python
from django.views.generic import ListView

from django_inertia import Prop
from django_inertia.views import InertiaResponseMixin, InertiaView


class Dashboard(InertiaView):
    component = "Dashboard"
    stats = Prop("get_stats", defer=True)   # a string names a method on the view

    def get_stats(self):
        return Stats.objects.summary()


class EventList(InertiaResponseMixin, ListView):
    component = "Event/Index"
    model = Event

    def get_props(self, **kwargs):
        return {**super().get_props(**kwargs), "events": list(kwargs["object_list"])}
```

## Responses render lazily

`InertiaResponse` is now a `SimpleTemplateResponse`. Props are resolved and the page is built when Django's handler renders the response, not in the constructor. Middleware with `process_template_response` and view decorators can change `response.component`, `response.props` and `response.template_data` before then.

Code that reads `response.content` on a response it built itself, before returning it, must call `response.render()` first, or it raises `ContentNotRenderedError`.

## Shared data

`share(request, **props)` is now `request.inertia.share(**props)`; see [Request helpers](#request-helpers). For props on every page, list functions in a setting instead of writing a middleware, like template context processors:

```python
# Before: a custom middleware
def inertia_share(get_response):
    def middleware(request):
        request.inertia.share(app_name=settings.APP_NAME, user=lambda: request.user)
        return get_response(request)
    return middleware

# After: myapp/inertia.py
def shared(request):
    return {"app_name": settings.APP_NAME, "user": lambda: request.user}

# settings.py
INERTIA = {"LAYOUT": "base.html", "SHARED_PROPS": ["myapp.inertia.shared"]}
```

A middleware calling `request.inertia.share()` keeps working, so this change is optional.

## Validation errors

Inertia forms read an `errors` prop. inertia-django left it to you to share one. Now:

- In a redirect-after-POST view, call `request.inertia.set_errors(form)` before redirecting. The errors are sent once on the next page, like `messages.error()`.
- A class-based view whose context holds a bound, invalid `form`, such as `FormView` after `form_invalid`, sends its errors automatically.

Each field keeps its first message, the shape Inertia's `useForm` expects. If you shared `form.errors` yourself, you sent lists of messages; delete that code.

## Request helpers

The functions that took the request first are now methods of `request.inertia`, which `InertiaMiddleware` attaches like `request.session`:

```python
# Before
from inertia import share
from inertia.http import clear_history, encrypt_history, preserve_fragment

share(request, team=team)
encrypt_history(request)
clear_history(request)
preserve_fragment(request)

# After
request.inertia.share(team=team)
request.inertia.encrypt_history()
request.inertia.clear_history()
request.inertia.preserve_fragment()
```

The codemod makes these rewrites. It reports a helper that is passed around instead of called, or that gets the request as a keyword argument.

`request.inertia` also describes the request: it is truthy for Inertia visits, and has `version`, `partial_component`, `partial_data`, `partial_except` and `is_partial()`. In inertia-django, `request.inertia` held only the shared props; code that read it, such as `request.inertia.all()`, must read `request.inertia.shared` instead.

`location(url)` is unchanged: it builds a response and does not take the request.

## Serialization

`InertiaJsonEncoder` and `InertiaMeta` are unchanged. Only the setting that selects the encoder changed; see [Settings](#settings).

## Tests

The test helpers no longer remember the last response. Assertions take the response first, like `assertTemplateUsed`:

```python
# Before
self.client.get("/events/")
self.assertComponentUsed("Event/Index")
self.assertIncludesProps({"sport": "hockey"})
self.assertEqual(self.props()["name"], "Brandon")

# After
response = self.client.get("/events/")
self.assertComponentUsed(response, "Event/Index")
self.assertIncludesProps(response, {"sport": "hockey"})
self.assertEqual(response.inertia.props["name"], "Brandon")
```

- `response.inertia` holds the page the response sent: `component`, `props`, `url`, `version`, and the whole page object as `data`. It replaces `page()`, `props()`, `component()`, `merge_props()`, `deferred_props()` and `once_props()`; for example, `self.deferred_props()` becomes `response.inertia.data["deferredProps"]`.
- `self.inertia` is still a client that sends `X-Inertia`, now an `InertiaClient`. `last_response` is gone.
- The assertions live in `InertiaTestMixin`, which also works with `SimpleTestCase`. In pytest, read `response.inertia` directly.
- `inertia_page()`, `inertia_div()`, `assertJSONResponse` and `BaseInertiaTestCase` were removed. Compare `response.inertia.data` or `response.json()` instead.

The codemod rewrites these in every class that descends from an `inertia.test` test case, including through your own base classes in other files. In each test method it keeps the response of the latest request in a variable, assigning `response = ...` where the request's result was discarded, and passes it to the assertions and accessors that read it. It reports an assertion with no request before it in the same method, such as one in a helper method; pass the response to those by hand.

To find base classes in other files, the codemod must see them: run it on the whole project, or include the files that define your base test cases. A test case whose base it cannot find is left as it is, and its assertions fail with a `TypeError` that names the assertion.
