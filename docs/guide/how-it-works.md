# How it works

A Django view usually renders a template. With Inertia, it renders a page component, and passes it props instead of template context:

```python
from dj_inertiajs import inertia


@inertia("Event/Index")
def index(request):
    return {"events": list(Event.objects.values("id", "title"))}
```

`Event/Index` is a component in your frontend, such as `frontend/pages/Event/Index.vue`, which receives `events` as a prop.

1. **The first visit is an ordinary request.** The view runs and returns your layout template, with the component's name and props embedded as JSON. The Inertia client starts, reads the JSON and renders the component.
2. **Later visits are Inertia requests.** Inertia's `<Link>` component and its `router` intercept navigation and make the request with XHR, adding an `X-Inertia` header. The same view runs, but this time the response is JSON: the component name and its props. The client swaps in the new component and updates the browser history, without a full page load.
3. **Forms post to Django views too.** A view validates the data and redirects, as usual. `set_errors()` sends validation errors back to the form, and Django messages arrive as flash messages.

Routing, authentication, permissions, the ORM and forms all stay in Django. There is no API to build and no client-side router.

[The protocol](/guide/the-protocol) describes the requests and responses in detail. Inertia's own explanation is on [inertiajs.com](https://inertiajs.com/docs/v3/core-concepts/how-it-works).
