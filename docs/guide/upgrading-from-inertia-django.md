# Upgrading from inertia-django

This package is a separate, Django-native adapter forked from inertia-django 2.0.0. Its API differs on purpose: settings live in one dict, props are declared with a `Prop` class, layouts use template tags, and the test helpers take the response. Nothing from the old API is kept for compatibility, so an upgraded project uses only the new API.

The protocol the client sees is the same as inertia-django 2.0's, which targets Inertia v3. Coming from 2.0, you do not need to change your frontend. Coming from 1.x, which targets Inertia v2, also follow [From inertia-django 1.x](#from-inertia-django-1-x).

## How to upgrade

Every change is described in the sections below, with what to do by hand. The codemod makes the mechanical ones for you, and the system checks find what is left, so you can use either or both.

1. **Install this package** next to inertia-django. Both can be installed while you migrate:

   ```shell
   pip install "dj-inertiajs[upgrade] @ git+https://github.com/joshuadavidthomas/inertia-django"
   ```

   The `upgrade` extra installs [LibCST](https://libcst.readthedocs.io/), which only the codemod needs.

2. **Rewrite the code**, with the codemod or by hand. The codemod rewrites every Python file under the paths you give it:

   ```shell
   dj-inertiajs-upgrade --diff path/to/project   # review the changes
   dj-inertiajs-upgrade path/to/project          # write them
   ```

   It prints, with file and line, every change it could not make on its own. [What the codemod changes](#what-the-codemod-changes) lists each rewrite and the section that explains how to make it by hand.

3. **Run the system checks.** `python manage.py check` reports old settings, the old middleware and app entries, and layouts that still use the old blocks, and names the section of this guide that explains each fix.

4. **Fix the rest by hand**, then uninstall `inertia-django`. Some changes can only be made by hand, because they depend on what your code means: templates, models without `InertiaMeta`, and uses of `share()`.

### Why the codemod is not a management command

Django only finds management commands in apps listed in `INSTALLED_APPS`, and only after it has loaded your settings. Before the upgrade neither holds:

- `dj_inertiajs` is not in `INSTALLED_APPS` yet; adding it is one of the codemod's rewrites. A `manage.py` command would not exist until the codemod had run.
- Once inertia-django is uninstalled, settings that still list `"inertia"` stop Django from starting, so `manage.py` does not run at all.

The codemod reads your code as text and never imports it, so it works on a project that does not start. Standalone codemods for Django, such as [django-upgrade](https://github.com/adamchainz/django-upgrade), work the same way. What does run inside Django is the system checks, which need a project that starts.

`python -m dj_inertiajs.upgrade` runs the same codemod.

## What the codemod changes

| The codemod rewrites | To do it by hand, see |
|---|---|
| Imports from `inertia` and its modules | [Imports](#imports) |
| `"inertia"` in `INSTALLED_APPS` | [Install and app name](#install-and-app-name) |
| The middleware path in `MIDDLEWARE` | [Middleware](#middleware) |
| `INERTIA_*` settings into the `INERTIA` dict, and the encoder path | [Settings](#settings) |
| Prop helper calls, such as `defer(f)`, into `Prop(...)` | [Props](#props) |
| `location(url)` into `InertiaLocation(url)` | [Redirects](#redirects) |
| `encrypt_history(request)` in an `@inertia` view into the decorator's option | [History encryption](#history-encryption) |
| Test clients, assertion names, and assertions and accessors that read the last response | [Tests](#tests) |

It reports these with file and line, and leaves them for you. Where such code still uses a name imported from inertia-django, the codemod keeps that import, so the file fails at import once inertia-django is uninstalled, instead of with a `NameError` only when the line runs:

| The codemod reports | See |
|---|---|
| Calls to `share()` | [Shared data](#shared-data) |
| Calls to `preserve_fragment()` | [Redirects](#redirects) |
| Prop helper calls it cannot map, such as `defer(f, *args)` | [Props](#props) |
| `encrypt_history()` calls outside an `@inertia` view, or with a value other than `True` or `False` | [History encryption](#history-encryption) |
| `import inertia`, `from inertia import *`, and names that were removed or were never public | [Imports](#imports) |
| Reads of `settings.INERTIA_*`, old settings in `override_settings()` and `self.settings()`, and an `INERTIA_JSON_ENCODER` that is not a class or a dotted path | [Settings](#settings) |
| Assertions with no request before them in the same test method, and `assertJSONResponse` | [Tests](#tests) |

It does not find these. The system checks find the first; the CSRF option keeps working; the others show up when the page renders or the tests run:

| Not handled by the codemod | See |
|---|---|
| Layout templates | [Layout templates](#layout-templates) |
| Models without `InertiaMeta` | [Serialization](#serialization) |
| Code that reads `request.inertia` | [The request](#the-request) |
| Code that reads `response.content` before returning a response | [Responses render lazily](#responses-render-lazily) |
| The `http` CSRF option in your JavaScript, which still works but can go | [CSRF](#csrf) |

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

2. **Remove the CSRF configuration** from your client setup, such as `axios.defaults.xsrfHeaderName`. The v3 client reads the `XSRF-TOKEN` cookie, which the middleware sets; see [CSRF](#csrf).

3. **Use Django messages for one-time notices.** Messages from `django.contrib.messages` are sent as the page's top-level `flash.messages`. Replace props you used for notices with `messages.success()` and the like.

4. **Review caching and partial reloads.**
   - Every Inertia response varies on `X-Inertia`. Make sure your reverse proxy or CDN honors the `Vary` header.
   - Partial reloads accept nested paths, such as `only: ["account.plans"]`, and `except`. Metadata such as `mergeProps` and `onceProps` only lists props included in that response.

Then check that a full page visit mounts the v3 client, a form submission sends the CSRF header, and flash messages appear once after a redirect.

## Install and app name

The import package is `dj_inertiajs`. Both packages can be installed at the same time while you migrate, but only one may be in `INSTALLED_APPS` and `MIDDLEWARE`.

```python
INSTALLED_APPS = [
    # ...
    "dj_inertiajs",   # was "inertia"
]
```

The codemod rewrites this entry. The `inertia.E009` check reports it if it is left.

## Imports

Change every import from `inertia` to the name below. Names marked "removed" have no direct replacement; the linked section explains what to do instead.

| inertia-django | dj_inertiajs |
|---|---|
| `from inertia import render, inertia, InertiaResponse` | `from dj_inertiajs import render, inertia, InertiaResponse` |
| `from inertia.http import render, inertia, InertiaResponse, clear_history` | `from dj_inertiajs import render, inertia, InertiaResponse, clear_history` |
| `from inertia import defer, merge, optional, ...` (or `inertia.utils`) | `from dj_inertiajs import Prop`; see [Props](#props) |
| `from inertia import location` (or `inertia.http`) | `from dj_inertiajs import InertiaLocation`; see [Redirects](#redirects) |
| `from inertia import preserve_fragment` (or `inertia.http`) | Removed; `from dj_inertiajs import redirect`, see [Redirects](#redirects) |
| `from inertia.http import encrypt_history` | Removed; see [History encryption](#history-encryption) |
| `from inertia import share` (or `inertia.share`) | Removed; see [Shared data](#shared-data) |
| `from inertia.utils import InertiaJsonEncoder` | `from dj_inertiajs.encoders import InertiaJsonEncoder` |
| `from inertia.middleware import InertiaMiddleware` | `from dj_inertiajs.middleware import InertiaMiddleware` |
| `from inertia.test import InertiaTestCase` | `from dj_inertiajs.test import InertiaTestCase` |
| `from inertia.test import inertia_page, inertia_div, BaseInertiaTestCase, ClientWithLastResponse` | Removed; see [Tests](#tests) |
| `from inertia.settings import settings` | Removed; see [Settings](#settings) |

Other names, such as the classes in `inertia.prop_classes`, `InertiaRequest` and `model_to_dict`, were never public API and have no replacement. `import inertia` followed by `inertia.render(...)` becomes `import dj_inertiajs` and `dj_inertiajs.render(...)`.

Dotted paths in strings change the same way: `"inertia.middleware.InertiaMiddleware"` becomes `"dj_inertiajs.middleware.InertiaMiddleware"`, and `"inertia.utils.InertiaJsonEncoder"` becomes `"dj_inertiajs.encoders.InertiaJsonEncoder"`.

## Settings

The `INERTIA_*` settings are replaced by one `INERTIA` dict. `JSON_ENCODER` is now a dotted import path instead of a class, so `settings.py` does not import application code.

| inertia-django | dj_inertiajs |
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

Code that read the old settings, through `django.conf.settings.INERTIA_LAYOUT` or inertia-django's `inertia.settings.settings`, reads `settings.INERTIA` instead.

The codemod rewrites module-level `INERTIA_*` assignments and reports reads of the old names. The `inertia.E007` check reports any that are left, and `inertia.E001` reports unknown keys in `INERTIA`, such as typos.

## Middleware

```python
MIDDLEWARE = [
    # ...
    "dj_inertiajs.middleware.InertiaMiddleware",   # was "inertia.middleware.InertiaMiddleware"
]
```

`SessionMiddleware` is now required and checked (`inertia.E005`). inertia-django needed it too, but failed only when it handled a request, not at startup.

The codemod rewrites this entry. The `inertia.E008` check reports the old path if it is left.

## CSRF

The middleware now sets an `XSRF-TOKEN` cookie on Inertia responses and accepts an `X-XSRF-TOKEN` header, the names the v3 client uses by default. The `http` option you added to `createInertiaApp` for Django's names still works, because Django still accepts its own header, but you can delete it:

```js
createInertiaApp({
  // Before: delete these lines
  http: {
    xsrfCookieName: "csrftoken",
    xsrfHeaderName: "X-CSRFToken",
  },
  // resolve and setup...
})
```

This also makes the client work with `CSRF_USE_SESSIONS` and `CSRF_COOKIE_HTTPONLY`, where Django's own cookie cannot be read.

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

| inertia-django | dj_inertiajs |
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

`Prop` raises `ValueError` for options that cannot be combined, including some the helpers ignored silently. For example, `group` needs `defer=True`, `match_on` needs merging, and `fresh` needs `once=True`. If an upgraded view raises one of these errors, the option never had an effect; remove it.

```python
# Before
from inertia import defer, merge

return render(request, "Event/Index", {
    "events": merge(lambda: Event.objects.page(page)),
    "stats": defer(lambda: Stats.objects.summary(), "sidebar"),
})

# After
from dj_inertiajs import Prop

return render(request, "Event/Index", {
    "events": Prop(lambda: Event.objects.page(page), merge=True),
    "stats": Prop(lambda: Stats.objects.summary(), defer=True, group="sidebar"),
})
```

The codemod rewrites calls to helpers imported by name from `inertia` or `inertia.utils`, including under another name. It reports module imports such as `import inertia.utils`, and leaves calls through them, such as `inertia.utils.defer(f)`, for you.

## Views

`render()` and the `@inertia` decorator keep their shape. Three things change:

- `@inertia` now works on `async def` views.
- The extra arguments of `render()` and `InertiaResponse` are keyword-only: `template_name`, `status`, `headers` and `encrypt_history`. `InertiaResponse` no longer takes `HttpResponse`'s other arguments, such as `content` or `content_type`.
- `@inertia` takes the same keyword arguments, such as `@inertia("Event/Index", template_name="events/base.html")`.

Class-based views are new, in `dj_inertiajs.views`:

```python
from django.views.generic import ListView

from dj_inertiajs import prop
from dj_inertiajs.views import InertiaResponseMixin, InertiaView


class Dashboard(InertiaView):
    component = "Dashboard"

    @prop(defer=True)   # sent as "stats", computed only when sent
    def stats(self):
        return Stats.objects.summary()


class EventList(InertiaResponseMixin, ListView):
    component = "Event/Index"
    model = Event

    def get_props(self, **kwargs):
        return {**super().get_props(**kwargs), "events": list(kwargs["object_list"].values("id", "title"))}
```

## Responses render lazily

`InertiaResponse` is now a `SimpleTemplateResponse`. Props are resolved and the page is built when Django's handler renders the response, not in the constructor. Middleware with `process_template_response` and view decorators can change `response.component`, `response.props` and `response.template_data` before then.

Code that reads `response.content` on a response it built itself, before returning it, must call `response.render()` first, or it raises `ContentNotRenderedError`.

## Shared data

`share(request, **props)` was removed. Shared props come from functions listed in `INERTIA["SHARED_PROPS"]`, the way template context comes from context processors. Each takes the request and returns a dict, and runs when the page renders:

```python
# Before: a custom middleware
def inertia_share(get_response):
    def middleware(request):
        share(request, app_name=settings.APP_NAME, user=lambda: request.user.get_username())
        return get_response(request)
    return middleware

# After: myapp/inertia.py
def shared(request):
    return {"app_name": settings.APP_NAME, "user": lambda: request.user.get_username()}

# settings.py
INERTIA = {"LAYOUT": "base.html", "SHARED_PROPS": ["myapp.inertia.shared"]}
```

Every other use of `share()` has a replacement:

| `share()` was called from | Replace it with |
|---|---|
| Middleware, with values every page needs | A `SHARED_PROPS` function, as above |
| Middleware, with a value it worked out, such as the current tenant | The middleware sets `request.tenant`; a `SHARED_PROPS` function reads it, the way context processors read `request.user` |
| A decorator or mixin, for some views | Change `response.props` on the returned response, which renders lazily, or override `get_props()` on a class-based view |
| A view, for its own page | Pass the values as props |

Later functions in `SHARED_PROPS` override earlier ones, as later `share()` calls overrode earlier ones, and a view's own props still override shared props. The codemod reports each use of `share`, since the replacement depends on where the call is.

## Validation errors

Inertia forms read an `errors` prop. inertia-django left it to you to share one. Now:

- In a redirect-after-POST view, call `set_errors(request, form)` before redirecting. The errors are sent once on the next page, like `messages.error()`.
- A class-based view whose context holds a bound, invalid `form`, such as `FormView` after `form_invalid`, sends its errors automatically.

Each field keeps its first message, the shape Inertia's `useForm` expects. If you shared `form.errors` yourself, you sent lists of messages; delete that code.

## Redirects

`preserve_fragment(request)` is gone. Keeping the fragment is a property of the redirect, so it is now an option of it:

```python
# Before
from django.shortcuts import redirect
from inertia.http import preserve_fragment

preserve_fragment(request)
return redirect("articles:show", slug=article.slug)

# After
from dj_inertiajs import redirect

return redirect("articles:show", slug=article.slug, preserve_fragment=True)
```

`dj_inertiajs.redirect` is `django.shortcuts.redirect` with Inertia's options. The codemod reports each `preserve_fragment` call.

`location(url)` is now a response class, `InertiaLocation(url)`, like `HttpResponseRedirect`:

```python
# Before
from inertia import location

return location("https://billing.example.com/portal")

# After
from dj_inertiajs import InertiaLocation

return InertiaLocation("https://billing.example.com/portal")
```

The codemod rewrites these calls.

## The request

`request.inertia` changed meaning. In inertia-django it held the shared props; code that read it, such as `request.inertia.all()`, must change. It now describes the request, like django-htmx's `request.htmx`: it is truthy for Inertia visits, and has `version`, `partial_component`, `partial_data`, `partial_except` and `is_partial()`. `share()` was removed; see [Shared data](#shared-data).

## History encryption

Encrypting history is a property of the page a view renders, so it moved from a call inside the view to the place the view declares its page:

```python
# Before
@inertia("Account/Show")
def account(request):
    encrypt_history(request)
    return {"email": request.user.email}

# After
@inertia("Account/Show", encrypt_history=True)
def account(request):
    return {"email": request.user.email}
```

`render(request, "Account/Show", props, encrypt_history=True)` and `encrypt_history = True` on a class-based view do the same. `False` opts a page out of `INERTIA["ENCRYPT_HISTORY"]`. To decide at runtime, pass a variable to `render()`, or set `response.encrypt_history` before the response renders.

The codemod moves `encrypt_history(request)`, `encrypt_history(request, True)` and `encrypt_history(request, False)` from the body of an `@inertia` view to its decorator. It reports every other call, including one whose value is computed in the view; pass that value to `render()` instead.

`clear_history(request)` is unchanged; only its import moves, which the codemod does. Like `messages.error(request, ...)`, it takes the request first, because it applies to the next page.

## Serialization

`InertiaMeta` is unchanged, and `QuerySet`s are still encoded as lists. What changed is models without `InertiaMeta`. inertia-django encoded them with `model_to_dict`, dropping a field named `password` and every field with `editable=False`. That sent every other field to the browser, including ones the page never used, and silently left out fields such as `auto_now_add` timestamps. Now such a model raises `TypeError` when the page renders, naming the model, like `JsonResponse` does.

For each model the error names, choose the fields the page should receive:

```python
# Before: every field except password and non-editable ones
return render(request, "Users/Show", {"user": user})

# After: the fields named in the view
return render(request, "Users/Show", {"user": {"id": user.id, "name": user.name}})

# Or on the model, for every page that sends it
class User(models.Model):
    class InertiaMeta:
        fields = ("id", "name", "created_at")
```

For a list, `User.objects.values("id", "name")` sends dicts. Neither the codemod nor the checks can find these props, because which models reach a page is only known when it renders; render each page once, or run your view tests, to find them.

The setting that selects the encoder changed too; see [Settings](#settings).

## Tests

The test helpers no longer remember the last response. Assertions take the response first, like `assertTemplateUsed`, and have Django-style names. `self.client` is now the Inertia client, so the old `self.client`, which made full page loads, becomes `self.client.get(..., inertia=False)`:

```python
# Before
self.client.get("/events/")
self.inertia.get("/events/")
self.assertComponentUsed("Event/Index")
self.assertIncludesProps({"sport": "hockey"})
self.assertEqual(self.props()["name"], "Brandon")

# After
response = self.client.get("/events/", inertia=False)
response = self.client.get("/events/")
self.assertComponentUsed(response, "Event/Index")
self.assertPropsContain(response, {"sport": "hockey"})
self.assertEqual(response.inertia.props["name"], "Brandon")
```

| Before | After |
|---|---|
| `self.inertia.get(...)` | `self.client.get(...)` |
| `self.client.get(...)` | `self.client.get(..., inertia=False)` |
| `assertHasExactProps` | `assertPropsEqual` |
| `assertIncludesProps` | `assertPropsContain` |
| `assertHasExactTemplateData` | `assertTemplateDataEqual` |
| `assertIncludesTemplateData` | `assertTemplateDataContain` |

To make these changes by hand, in each test method:

1. Assign the result of each request to `response`, if the test discarded it.
2. Rename `self.inertia` to `self.client`, and add `inertia=False` to requests that used the old `self.client`.
3. Pass `response` as the first argument of each assertion, and rename the assertions as in the table.
4. Replace the accessors with reads from `response`:

| Before | After |
|---|---|
| `self.component()` | `response.inertia.component` |
| `self.props()` | `response.inertia.props` |
| `self.page()` | `response.inertia.data` |
| `self.merge_props()` | `response.inertia.data["mergeProps"]` |
| `self.deferred_props()` | `response.inertia.data["deferredProps"]` |
| `self.once_props()` | `response.inertia.data["onceProps"]` |
| `self.template_data()` | `response.template_data` |
| `self.client.last_response` | `response` |

- `response.inertia` holds the page the response sent: `component`, `props`, `url`, `version`, and the whole page object as `data`. It replaces the accessors above.
- `InertiaTestCase` sets Django's `client_class` to `InertiaClient` and `async_client_class` to `AsyncInertiaClient`. `self.inertia` and `last_response` are gone.
- The assertions live in `InertiaTestMixin`, which also works with `SimpleTestCase`. In pytest, read `response.inertia` directly.
- `inertia_page()`, `inertia_div()`, `assertJSONResponse` and `BaseInertiaTestCase` were removed. Compare `response.inertia.data` or `response.json()` instead. The codemod reports their imports and each `assertJSONResponse` call.

The codemod makes all of these rewrites in every class that descends from an `inertia.test` test case, including through your own base classes in other files. In each test method it keeps the response of the latest request in a variable, assigning `response = ...` where the request's result was discarded, and passes it to the assertions and accessors that read it. It reports an assertion with no request before it in the same method, such as one in a helper method; pass the response to those by hand.

To find base classes in other files, the codemod must see them: run it on the whole project, or include the files that define your base test cases. A test case whose base it cannot find is left as it is. Its tests fail with an `AttributeError` for `self.inertia` or an old assertion name, or a `TypeError` from `assertComponentUsed`, which kept its name.
