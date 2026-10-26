---
prev: false
next:
  text: 'How it works'
  link: '/guide/how-it-works'
---

# Introduction

dj-inertiajs connects Django to [Inertia.js](https://inertiajs.com/docs/v3/getting-started). Your views stay Django views, but instead of rendering a template they render a page component written in React, Vue or Svelte. Inertia turns those pages into a single-page app, without an API between the two.

dj-inertiajs is an independent project. It is not affiliated with or endorsed by the Inertia.js project or [inertia-django](https://github.com/inertiajs/inertia-django). It was forked from inertia-django 2.0.0 and speaks the same Inertia v3 protocol, so the client side is the standard Inertia client. Its Python API is new, and follows Django's conventions: one settings dict, system checks, class-based views, lazy responses like `TemplateResponse`, and test assertions that take the response. Coming from inertia-django? See [Upgrading from inertia-django](/guide/upgrading-from-inertia-django).

## Where things are documented

- **The Django side** is documented here and in the [README](https://github.com/joshuadavidthomas/inertia-django#readme): installing the adapter, views, props, forms, settings and testing.
- **The client side**, such as page components, links, forms and layouts, is documented by Inertia itself at [inertiajs.com](https://inertiajs.com/docs/v3/getting-started). Its [who is it for](https://inertiajs.com/docs/v3/core-concepts/who-is-it-for) page explains when Inertia is a good fit.

## Next steps

Read [how it works](/guide/how-it-works), or go straight to the [server-side setup](/guide/server-side-setup).
