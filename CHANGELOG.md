# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

This is a separate, Django-native package forked from inertia-django 2.0.0. It breaks the API on purpose; a migration guide will cover every change.

### Breaking changes

* Rename the distribution from `inertia-django` to `dj-inertiajs`, and the import package from `inertia` to `dj_inertiajs`. The `{% load inertia %}` tag library, the `INERTIA` setting and the `inertia.E0xx` check IDs keep their names.
* Replace the `INERTIA_*` settings with one `INERTIA` dict: `LAYOUT`, `VERSION`, `JSON_ENCODER`, `ENCRYPT_HISTORY`, and `SSR` with `ENABLED` and `URL`. `JSON_ENCODER` is now a dotted import path.
* `InertiaResponse` now subclasses `SimpleTemplateResponse` and renders lazily, when Django's handler calls `render()`. Reading `response.content` before that raises `ContentNotRenderedError`. Its extra arguments are now keyword-only `status` and `headers`.
* Replace the block-based layout with template tags. The package no longer ships `inertia.html` or `inertia_ssr.html`, and layouts no longer define `{% block inertia %}` or `{% block inertia_head %}`. Instead a layout does `{% load inertia %}` and calls `{% inertia_head %}` in `<head>` and `{% inertia_body %}` where the app mounts. `{% inertia_body id="root" %}` sets the root element's id, which was hard-coded to `app`.
* Replace the prop helper functions `optional`, `defer`, `always`, `merge`, `deep_merge`, `scroll`, `once` and `lazy` with one `Prop` class whose keyword options carry the same behavior, for example `Prop(load_stats, defer=True, group="charts")`. Options that cannot be combined now raise `ValueError` instead of being ignored. `scroll()`'s `wrapper` becomes `merge="<path>"`, and `merge(append=...)` becomes `merge=...`.
* `request.inertia` no longer holds the shared props; it describes the request (see Added).
* Replace `location(url)` with a response class, `InertiaLocation(url)`, the Inertia counterpart of `HttpResponseRedirect`.
* Replace `preserve_fragment(request)` with an option of the redirect: `redirect(..., preserve_fragment=True)`, using `dj_inertiajs.redirect`, which is `django.shortcuts.redirect` with Inertia's options.
* Replace `encrypt_history(request)` with an `encrypt_history` option on the page: `@inertia("...", encrypt_history=True)`, `render(..., encrypt_history=True)`, `InertiaResponse(..., encrypt_history=True)` and an `encrypt_history` attribute on class-based views. A non-bool value raises `TypeError` when the response is built.
* Organize modules the way Django does: `shortcuts.render`, `decorators.inertia`, `response.InertiaResponse`, `request.InertiaDetails`, `encoders.InertiaJsonEncoder` and `conf.settings`. `http.py`, `utils.py`, `settings.py` and the unused `helpers.py` are gone. Import public names from `dj_inertiajs` itself.
* Stop encoding models implicitly. `InertiaJsonEncoder` no longer runs `model_to_dict` on models, which sent every field except one named `password` and skipped `editable=False` fields. A model without `InertiaMeta` now raises `TypeError` naming the model, like `JsonResponse`; send a dict, `QuerySet.values()`, or declare `InertiaMeta.fields`. `InertiaMeta` and `QuerySet` encoding are unchanged.
* Rewrite the test helpers. Assertions take the response first, for example `assertComponentUsed(response, "Event/Index")`, and live in `InertiaTestMixin` so they work with `SimpleTestCase`. `self.inertia` is an `InertiaClient`. Removed: the stateful accessors (`page()`, `props()`, `component()`, `template_data()`, `merge_props()`, `deferred_props()`, `once_props()`), `last_response`, `ClientWithLastResponse`, `BaseInertiaTestCase`, `assertJSONResponse`, `inertia_page()` and `inertia_div()`.

### Added

* Make `request.inertia` describe the request, like django-htmx's `request.htmx`: `InertiaMiddleware` attaches it to every request, like `request.session`. It is truthy for Inertia visits, and has `version`, `partial_component`, `partial_data`, `partial_except`, `reset`, `except_once_props`, `merge_intent`, `prefetch` and `is_partial()`. Annotate views with `dj_inertiajs.request.InertiaHttpRequest` for type checkers. A request built with `RequestFactory` gets it when the response renders.
* Add an upgrade codemod, `python -m dj_inertiajs.upgrade [--diff] PATH ...`, with the `upgrade` extra. It rewrites imports, prop helper calls, `location()` calls into `InertiaLocation`, `encrypt_history(request)` in `@inertia` views into the decorator's option, `INERTIA_*` settings, the `MIDDLEWARE` and `INSTALLED_APPS` entries, and `InertiaTestCase` assertions and accessors to take the response, including in test cases that inherit from it through base classes in other files, preserving formatting, and lists what it could not rewrite.
* Add upgrade checks that report inertia-django configuration still in use: `INERTIA_*` settings, the old middleware path, the `inertia` app, and layouts that use `{% block inertia %}`. Each hint names the section of the upgrade guide that explains the fix.
* Add system checks for unknown `INERTIA` keys, unimportable `SHARED_PROPS` entries, a missing layout, SSR without `requests`, and missing Inertia or session middleware.
* Set the CSRF cookie only on Inertia responses. The middleware set it on every response, which added `Vary: Cookie` to pages that are not Inertia pages.
* Make `InertiaMiddleware` async-capable, so it no longer runs in a thread under ASGI.
* Support `async def` views under `@inertia`, and `async def` prop callables, which are awaited in sync and async views alike.
* Let `process_template_response` middleware and view decorators change `component`, `props` and `template_data` before the page is rendered.
* Add `status` and `headers` arguments to `render()`. `@inertia` takes the same options as `render()`: `template_name`, `status`, `headers` and `encrypt_history`.
* Add a per-view layout: `render(..., template_name=...)`, `InertiaResponse(..., template_name=...)` and a `template_name` attribute on class-based views. `INERTIA["LAYOUT"]` is the default.
* Add `INERTIA["SHARED_PROPS"]`: dotted paths to `(request) -> dict` functions whose props are added to every page, like template context processors. View props override them, and `share()` still adds per-request values.
* Add `set_errors(request, form_or_dict)`, which sends validation errors as the `errors` prop on the next page, once, the way `contrib.messages` works. Each field keeps its first message, and the prop is included in partial reloads. Formsets are supported, with `"<prefix>.<index>.<field>"` keys. `INERTIA["FORM_ERRORS"]` names the function that converts errors, and check `inertia.E011` reports it, or `JSON_ENCODER`, when it cannot be imported.
* Add class-based views in `dj_inertiajs.views`: `InertiaResponseMixin`, which works with Django's generic views such as `ListView` and `FormView`, and `InertiaView`. Props come from `get_props()`. `Prop` attributes declared on the class are collected automatically, and so are methods decorated with `@prop(...)`, which take `Prop`'s options and run only when their prop is sent. A bound, invalid `form` in the context is sent as the `errors` prop, so `FormView` needs no extra code.
* Expose the page a rendered response sent as `response.inertia` (`component`, `props`, `url`, `version`, and the whole page object as `data`), so pytest tests can read it without helpers.

## [2.0.0] - 2026-08-16

### Breaking changes

* Require Python 3.10 or newer ([#74](https://github.com/inertiajs/inertia-django/pull/74), [#86](https://github.com/inertiajs/inertia-django/pull/86)).
* Require Django 5.2 LTS or newer ([#103](https://github.com/inertiajs/inertia-django/pull/103)).
* Move `requests` behind the optional `ssr` extra. Applications using server-side rendering must install `inertia-django[ssr]` ([#73](https://github.com/inertiajs/inertia-django/pull/73)).
* Update the first-load page format and CSRF configuration for Inertia v3. Applications with custom templates or client setup should follow the [Inertia v3 upgrade guide](https://github.com/joshuadavidthomas/inertia-django/blob/4a9405726525e27c40f216076142277337d7221c/docs/guide/upgrading-to-v3.md) ([#100](https://github.com/inertiajs/inertia-django/pull/100), [#101](https://github.com/inertiajs/inertia-django/pull/101)).

### Added

* Add full Inertia v3 protocol support, including nested partial reloads, once props, deep merge and scroll props, prepend intent, fragment-preserving redirects, preserved errors, and improved merge metadata ([#100](https://github.com/inertiajs/inertia-django/pull/100), [#101](https://github.com/inertiajs/inertia-django/pull/101)).
* Expose Django messages as top-level Inertia flash data ([#96](https://github.com/inertiajs/inertia-django/pull/96), [#101](https://github.com/inertiajs/inertia-django/pull/101)).
* Add type annotations and ship a PEP 561 `py.typed` marker for downstream type checkers ([#85](https://github.com/inertiajs/inertia-django/pull/85), [#95](https://github.com/inertiajs/inertia-django/pull/95)).
* Log server-side rendering failures while preserving the client-side rendering fallback ([#89](https://github.com/inertiajs/inertia-django/pull/89)).

### Changed

* Make `InertiaRequest` inherit from Django's `HttpRequest` for better compatibility with Django and third-party libraries ([#84](https://github.com/inertiajs/inertia-django/pull/84)).
* Improve the `@inertia` decorator's response handling and stack-trace naming ([#77](https://github.com/inertiajs/inertia-django/pull/77)).

Thanks to @akx, @SarthakJariwala, @mrgalopes, @kennyputman, @willianantunes,
@leeuwr, @benaduo, @Zesuperaker, and @basan17 for their contributions to this release.

## [1.2.0] - 2025-03-25
* Add InertiaMeta class config for easier serialization
* Bugfix for InertiaJsonEncoder customizatin. Thanks @akx!
* Better Errors for missing settings. Thanks @akx!
* Allow serialization of non-model query set results. Thanks @akx
* Special thanks to @svengt for adding ruff formatting!

## [1.1.0] - 2025-01-08
* Refactored rendering logic to create InertiaResponse class
* Bugfix for SSR template data
* Bugfix for relative url. Thanks @Rey092!

## [1.0.0] - 2025-01-05
* Inertia V2 Support
* * Encrypt History. Thanks @svengt!
* * Deferred Props. Thanks @mrfolksy!
* * Optional props and deprecate lazy
* * Merge Props
* Location function. Thanks @keinstn!

## [0.6.0] - 2024-01-26
* Allow Django >=4 Thanks @pmdevita!

## [0.5.3] - 2023-09-20

* Encode SSR page data via the included InertiaJsonEncoder. Thanks @svengt!
* Bugfix for Inertia test helpers. Thanks @nootr!
* Bugfix for 303 redirect HTTP verbs. Thanks @Xzya! 

## [0.5.2] - 2022-12-22

* Make sure CSRF cookies are also set on initial load, not just inertia responses. Thanks @pauldiepold!

## [0.5.1] - 2022-12-21

* Revert switch to using Vary: X-Inertia headers due to bug report.

## [0.5.0] - 2022-12-20

* Automatically Include CSRF Token.
* Switch to using Vary: X-Inertia headers. Thanks @swarakaka!
* Bugfix for Inertia head tag rendering. Thanks @svengt!

## [0.4.1] - 2022-10-10

* Bugfix to allow redirects to be returned from @inertia decorated views.

## [0.4.0] - ???

* Initial release.
