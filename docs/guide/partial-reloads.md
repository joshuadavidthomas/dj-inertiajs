# Partial reloads

A partial reload asks the server for only some of a page's props, on a visit to the same page component. The client side is described in the Inertia docs on [partial reloads](https://inertiajs.com/docs/v3/data-props/partial-reloads):

```js
router.reload({ only: ["users"] })
router.reload({ except: ["companies"] })
```

On the server, write the view as usual. Only the props the client asks for are resolved:

```python
from dj_inertiajs import Prop, inertia


@inertia("Users/Index")
def users(request):
    return {
        "users": lambda: list(User.objects.values("id", "name")),
        "companies": lambda: list(Company.objects.values("id", "name")),
        "stats": Prop(load_stats, optional=True),
        "auth": Prop(request.user.get_username, always=True),
    }
```

`router.reload({ only: ["users"] })` sends `users` and `auth`. The `companies` and `stats` callables are not called.

- Wrap a prop in a callable, or a `Prop`, to skip its work when it is not sent. A plain value is computed when the view runs, whether or not it is sent.
- `Prop(..., optional=True)` is never sent on the first load, only when a partial reload asks for it.
- `Prop(..., always=True)` is sent on every partial reload, as is the `errors` prop from `set_errors()`.
- Props may be nested in dicts and lists; `only` and `except` address them by dotted path, such as `"user.name"`.
- A partial reload applies only when the view renders the component the client asked about. If it renders another one, for example after a redirect to the login page, the response is built as for a first load: every prop except `optional` and deferred ones.

To check in a view whether a request is a partial reload, use `request.inertia.is_partial("Users/Index")`, and `request.inertia.partial_data` for the props it asks for.
