# The protocol

This page describes the Inertia v3 protocol as dj-inertiajs implements it: what the client sends, and what Django sends back. It follows Inertia's [protocol specification](https://inertiajs.com/docs/v3/core-concepts/the-protocol), which is the reference.

## First visit: HTML

The first request is an ordinary browser request, with no Inertia headers. The view returns the layout template. `{% inertia_body %}` puts the [page object] in a JSON `<script>` element, followed by the element the client mounts on:

```http
REQUEST
GET: http://example.com/events/80
Accept: text/html, application/xhtml+xml


RESPONSE
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

<html>
<head>
    <title>My app</title>
    <script src="/static/assets/main.js" type="module"></script>
</head>
<body>

<script data-page="app" type="application/json">{"component": "Event/Show", "props": {"event": {"id": 80, "title": "Birthday party"}}, "url": "/events/80", "version": "1.0", "encryptHistory": false, "clearHistory": false}</script>
  <div id="app"></div>

</body>
</html>
```

The page component itself is rendered in the browser, unless you turn on server-side rendering with `INERTIA["SSR"]`.

## Later visits: JSON

After it starts, the client makes every visit with XHR and an `X-Inertia: true` header. For those requests the same view returns the page object as JSON. The response varies on `Cookie` too, because it sets the CSRF cookie the client reads:

```http
REQUEST
GET: http://example.com/events/80
Accept: text/html, application/xhtml+xml
X-Requested-With: XMLHttpRequest
X-Inertia: true
X-Inertia-Version: 1.0

RESPONSE
HTTP/1.1 200 OK
Content-Type: application/json
Vary: X-Inertia, Cookie
X-Inertia: true

{
  "component": "Event/Show",
  "props": {
    "event": {"id": 80, "title": "Birthday party"}
  },
  "url": "/events/80",
  "version": "1.0",
  "encryptHistory": false,
  "clearHistory": false
}
```

## The page object

Every page object has:

- `component`: the name of the page component.
- `props`: the props, after shared props are added and callables are resolved.
- `url`: the URL of the page.
- `version`: the asset version, from `INERTIA["VERSION"]`.
- `encryptHistory`: whether the client encrypts this page in the browser history.
- `clearHistory`: whether the client discards the encrypted history.

It has these keys only when they apply:

- `flash`: Django messages, as `{"messages": [{"level": ..., "message": ...}]}`.
- `sharedProps`: the keys of the props that came from `INERTIA["SHARED_PROPS"]`, and `errors` when `set_errors()` was called.
- `preserveFragment`: keep the URL fragment after a redirect.
- `deferredProps`, `mergeProps`, `prependProps`, `deepMergeProps`, `matchPropsOn`, `scrollProps`, `onceProps` and `rescuedProps`: how the client loads, merges and caches props, from the options of `Prop`.

## Asset versioning

The client sends the asset version it was loaded with in `X-Inertia-Version`. When a `GET` visit arrives with a version other than `INERTIA["VERSION"]`, the middleware replaces the view's response with `409 Conflict`, the URL in `X-Inertia-Location` and the current version in `X-Inertia-Version`, and the client reloads the whole page to get the new assets. Django messages the view's response would have shown are kept for that reload.

```http
REQUEST
GET: http://example.com/events/80
X-Inertia: true
X-Inertia-Version: 0.9

RESPONSE
HTTP/1.1 409 Conflict
X-Inertia-Location: http://example.com/events/80
X-Inertia-Version: 1.0
```

The client skips the reload for an async request, such as a poll, a prefetch or a `router.reload()`, so it does not discard a page the user is working on.

Other methods are not checked, so a form submission is not lost; the `GET` that follows its redirect is.

## Partial reloads

A partial reload asks for some props of the current page. The client names the component in `X-Inertia-Partial-Component` and the props in `X-Inertia-Partial-Data`, or the props to leave out in `X-Inertia-Partial-Except`. If the view renders that component, only the requested props are resolved and sent, plus `always` props and `errors`; otherwise the response is a normal visit. See [Partial reloads](/guide/partial-reloads).

```http
REQUEST
GET: http://example.com/events
X-Inertia: true
X-Inertia-Version: 1.0
X-Inertia-Partial-Component: Event/Index
X-Inertia-Partial-Data: events

RESPONSE
HTTP/1.1 200 OK
Content-Type: application/json

{
  "component": "Event/Index",
  "props": {
    "events": [...]
  },
  "url": "/events",
  "version": "1.0",
  "encryptHistory": false,
  "clearHistory": false
}
```

## Other request headers

The client sends more headers for partial reloads, merging, once props and prefetching. `InertiaMiddleware` exposes each one on `request.inertia`:

| Header | `request.inertia` |
|---|---|
| `X-Inertia` | truthy when present |
| `X-Inertia-Version` | `version` |
| `X-Inertia-Partial-Component` | `partial_component` |
| `X-Inertia-Partial-Data` | `partial_data` |
| `X-Inertia-Partial-Except` | `partial_except` |
| `X-Inertia-Reset` | `reset` |
| `X-Inertia-Except-Once-Props` | `except_once_props` |
| `X-Inertia-Infinite-Scroll-Merge-Intent` | `merge_intent` |
| `Purpose: prefetch` | `prefetch` |

## Redirects

For Inertia requests, `InertiaMiddleware` adjusts redirects the way the client needs:

- A `301` or `302` redirect after a `PUT`, `PATCH` or `DELETE` request becomes `303 See Other`, so the browser follows it with a `GET`.
- A redirect to a URL with a fragment, such as `/articles/1#comments`, becomes `409 Conflict` with the URL in an `X-Inertia-Redirect` header, except for prefetch requests. The client could not see the fragment of a redirect that XHR follows for it, so it makes a new visit to that URL instead.

To leave the Inertia app, a view returns `InertiaLocation(url)`: `409 Conflict` with an `X-Inertia-Location` header, which makes the client do a full page visit to `url`. On a full page load, which a browser makes without the client, the middleware sends an ordinary `302` redirect instead.

[page object]: #the-page-object
