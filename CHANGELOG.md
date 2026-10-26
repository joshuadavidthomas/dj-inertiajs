# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

This is a separate, Django-native package forked from inertia-django 2.0.0. It breaks the API on purpose; a migration guide will cover every change.

### Breaking changes

* Rename the import package from `inertia` to `django_inertia` (placeholder until the final name is chosen).
* Replace the `INERTIA_*` settings with one `INERTIA` dict: `LAYOUT`, `VERSION`, `JSON_ENCODER`, `ENCRYPT_HISTORY`, and `SSR` with `ENABLED` and `URL`. `JSON_ENCODER` is now a dotted import path.
* `InertiaResponse` now subclasses `SimpleTemplateResponse` and renders lazily, when Django's handler calls `render()`. Reading `response.content` before that raises `ContentNotRenderedError`. Its extra arguments are now keyword-only `status` and `headers`.
* Replace the block-based layout with template tags. The package no longer ships `inertia.html` or `inertia_ssr.html`, and layouts no longer define `{% block inertia %}` or `{% block inertia_head %}`. Instead a layout does `{% load inertia %}` and calls `{% inertia_head %}` in `<head>` and `{% inertia_body %}` where the app mounts. `{% inertia_body id="root" %}` sets the root element's id, which was hard-coded to `app`.
* Replace the prop helper functions `optional`, `defer`, `always`, `merge`, `deep_merge`, `scroll`, `once` and `lazy` with one `Prop` class whose keyword options carry the same behavior, for example `Prop(load_stats, defer=True, group="charts")`. Options that cannot be combined now raise `ValueError` instead of being ignored. `scroll()`'s `wrapper` becomes `merge="<path>"`, and `merge(append=...)` becomes `merge=...`.
* Rewrite the test helpers. Assertions take the response first, for example `assertComponentUsed(response, "Event/Index")`, and live in `InertiaTestMixin` so they work with `SimpleTestCase`. `self.inertia` is an `InertiaClient`. Removed: the stateful accessors (`page()`, `props()`, `component()`, `template_data()`, `merge_props()`, `deferred_props()`, `once_props()`), `last_response`, `ClientWithLastResponse`, `BaseInertiaTestCase`, `assertJSONResponse`, `inertia_page()` and `inertia_div()`.

### Added

* Export `encrypt_history` and `clear_history` from the top-level package. They were only importable from `inertia.http`, although the README imported them from `inertia`.
* Add system checks for unknown `INERTIA` keys, unimportable `SHARED_PROPS` entries, a missing layout, SSR without `requests`, and missing Inertia or session middleware.
* Make `InertiaMiddleware` async-capable, so it no longer runs in a thread under ASGI.
* Support `async def` views under `@inertia`.
* Let `process_template_response` middleware and view decorators change `component`, `props` and `template_data` before the page is rendered.
* Add `status` and `headers` arguments to `render()`.
* Add a per-view layout: `render(..., template_name=...)`, `InertiaResponse(..., template_name=...)` and a `template_name` attribute on class-based views. `INERTIA["LAYOUT"]` is the default.
* Add `INERTIA["SHARED_PROPS"]`: dotted paths to `(request) -> dict` functions whose props are added to every page, like template context processors. View props override them, and `share()` still adds per-request values.
* Add `set_errors(request, form_or_dict)`, which sends validation errors as the `errors` prop on the next page, once, the way `contrib.messages` works. Each field keeps its first message, and the prop is included in partial reloads.
* Add class-based views in `django_inertia.views`: `InertiaResponseMixin`, which works with Django's generic views such as `ListView` and `FormView`, and `InertiaView`. Props come from `get_props()`. `Prop` attributes declared on the class are collected automatically, and a declared `Prop` whose value is a string names a view method. A bound, invalid `form` in the context is sent as the `errors` prop, so `FormView` needs no extra code.
* Expose the page a rendered response sent as `response.inertia` (`component`, `props`, `url`, `version`, and the whole page object as `data`), so pytest tests can read it without helpers.

## [2.0.0] - 2026-08-16

### Breaking changes

* Require Python 3.10 or newer ([#74](https://github.com/inertiajs/inertia-django/pull/74), [#86](https://github.com/inertiajs/inertia-django/pull/86)).
* Require Django 5.2 LTS or newer ([#103](https://github.com/inertiajs/inertia-django/pull/103)).
* Move `requests` behind the optional `ssr` extra. Applications using server-side rendering must install `inertia-django[ssr]` ([#73](https://github.com/inertiajs/inertia-django/pull/73)).
* Update the first-load page format and CSRF configuration for Inertia v3. Applications with custom templates or client setup should follow the [Inertia v3 upgrade guide](docs/guide/upgrading-to-v3.md) ([#100](https://github.com/inertiajs/inertia-django/pull/100), [#101](https://github.com/inertiajs/inertia-django/pull/101)).

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
