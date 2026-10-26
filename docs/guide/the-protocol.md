# The protocol

This page contains a detailed specification of the Inertia protocol. Be sure to read the [how it works](/guide/how-it-works.md) page first for a high-level overview.

## HTML responses

The very first request to an Inertia app is just a regular, full-page browser request, with no special Inertia headers or data. For these requests, the server returns a full HTML document.

This HTML response includes the site assets (CSS, JavaScript), a JSON script containing the initial [page object], and a root `<div>` in the page's body. The root `<div>` serves as a mounting point for the client-side app; Inertia uses the JSON script to boot the framework and display the initial page component.

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
    <link href="/css/app.css" rel="stylesheet">
    <script src="/js/app.js" defer></script>
</head>
<body>

<script data-page="app" type="application/json">{"component":"Event","props":{"event":{"id":80,"title":"Birthday party","start_date":"2019-06-02","description":"Come out and celebrate Jonathan's 36th birthday party!"}},"url":"/events/80","version":"c32b8e4965f418ad16eaebba1d4e960f"}</script>
<div id="app"></div>

</body>
</html>
```

> [!NOTE]
> The page components are not rendered on the server unless you turn on server-side rendering; see `INERTIA["SSR"]`.

## Inertia responses

Once the Inertia app has been booted, all subsequent requests to the site are made via XHR with a `X-Inertia` header set to `true`. This header indicates that the request is being made by Inertia and isn't a standard full-page visit.

When the server detects the `X-Inertia` header, instead of responding with a full HTML document, it returns a JSON response with an encoded [page object].

```http
REQUEST
GET: http://example.com/events/80
Accept: text/html, application/xhtml+xml
X-Requested-With: XMLHttpRequest
X-Inertia: true
X-Inertia-Version: 6b16b94d7c51cbe5b1fa42aac98241d5

RESPONSE
HTTP/1.1 200 OK
Content-Type: application/json
Vary: X-Inertia
X-Inertia: true

{
  "component": "Event",
  "props": {
    "event": {
      "id": 80,
      "title": "Birthday party",
      "start_date": "2019-06-02",
      "description": "Come out and celebrate Jonathan's 36th birthday party!"
    }
  },
  "url": "/events/80",
  "version": "c32b8e4965f418ad16eaebba1d4e960f",
  "encryptHistory": true,
  "clearHistory": false
}
```

## The page object

Inertia shares data between the server and client via a page object. This object includes the necessary information required to render the page component, update the browser's history state, and track the site's asset version. Every page object has these properties:

1. `component`: The name of the JavaScript page component.
2. `props`: The page props (data).
3. `url`: The page URL.
4. `version`: The current asset version.
5. `encryptHistory`: Whether or not to encrypt the current page's history state.
6. `clearHistory`: Whether or not to clear any encrypted history state.

It has these when they apply:

- `flash`: Django messages, as `{"messages": [{"level": ..., "message": ...}]}`.
- `sharedProps`: the keys of the props that came from `INERTIA["SHARED_PROPS"]`.
- `preserveFragment`: keep the URL fragment after a redirect.
- `deferredProps`, `mergeProps`, `prependProps`, `deepMergeProps`, `matchPropsOn`, `scrollProps`, `onceProps` and `rescuedProps`: how the client loads, merges and caches the props, from the options of `Prop`.

On standard full page visits, the page object is JSON encoded into a `<script data-page="app" type="application/json">` element. On Inertia visits, the page object is returned as the JSON payload.

## Asset versioning

One common challenge with single-page apps is refreshing site assets when they've been changed. Inertia makes this easy by optionally tracking the current version of the site's assets. In the event that an asset changes, Inertia will automatically make a full-page visit instead of an XHR visit.

The Inertia [page object] includes a `version` identifier. This version identifier is set server-side and can be a number, string, file hash, or any other value that represents the current "version" of your site's assets, as long as the value changes when the site's assets have been updated.

Whenever an Inertia request is made, Inertia will include the current asset version in the `X-Inertia-Version` header. When the server receives the request, it compares the asset version provided in the `X-Inertia-Version` header with the current asset version. This is typically handled in the middleware layer of your server-side framework.

If the asset versions are the same, the request simply continues as expected. However, if the asset versions are different, the server immediately returns a `409 Conflict` response, and includes the URL in a `X-Inertia-Location` header. This header is necessary, since server-side redirects may have occurred. This tells Inertia what the final intended destination URL is.

Note, `409 Conflict` responses are only sent for `GET` requests, and not for `POST/PUT/PATCH/DELETE` requests. That said, they will be sent in the event that a `GET` redirect occurs after one of these requests.

If "flash" session data exists when a `409 Conflict` response occurs, Inertia's server-side framework adapters will automatically reflash this data.

```http
REQUEST
GET: http://example.com/events/80
Accept: text/html, application/xhtml+xml
X-Requested-With: XMLHttpRequest
X-Inertia: true
X-Inertia-Version: 6b16b94d7c51cbe5b1fa42aac98241d5

RESPONSE
409: Conflict
X-Inertia-Location: http://example.com/events/80
```

## Partial reloads

When making Inertia requests, the partial reload option allows you to request a subset of the props (data) from the server on subsequent visits to the same page component. This can be a helpful performance optimization if it's acceptable that some page data becomes stale.

When a partial reload request is made, Inertia includes two additional headers with the request: `X-Inertia-Partial-Data` and `X-Inertia-Partial-Component`.

The `X-Inertia-Partial-Data` header is a comma separated list of the desired props (data) keys that should be returned.

The `X-Inertia-Partial-Component` header includes the name of the component that is being partially reloaded. This is necessary, since partial reloads only work for requests made to the same page component. If the final destination is different for some reason (eg. the user was logged out and is now on the login page), then no partial reloading will occur.

```http
REQUEST
GET: http://example.com/events
Accept: text/html, application/xhtml+xml
X-Requested-With: XMLHttpRequest
X-Inertia: true
X-Inertia-Version: 6b16b94d7c51cbe5b1fa42aac98241d5
X-Inertia-Partial-Data: events
X-Inertia-Partial-Component: Events

RESPONSE
HTTP/1.1 200 OK
Content-Type: application/json

{
  "component": "Events",
  "props": {
    "auth": {...},       // NOT included
    "categories": [...], // NOT included
    "events": [...]      // included
  },
  "url": "/events",
  "version": "c32b8e4965f418ad16eaebba1d4e960f"
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
- A redirect to a URL with a fragment, such as `/articles/1#comments`, becomes `409 Conflict` with the URL in an `X-Inertia-Redirect` header, because a browser drops the fragment when it follows a redirect itself.
- `InertiaLocation(url)` returns `409 Conflict` with an `X-Inertia-Location` header, which makes the client do a full page visit to `url`.

[page object]: #the-page-object
