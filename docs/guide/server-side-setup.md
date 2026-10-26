# Server-side setup

To get started with Inertia in Django, the first step is to configure Django to use the `dj_inertiajs` server-side adapter.

::: tip
For new projects, we recommend following the [template based setup](#template-based-setup) guide.
:::

## Template-based setup

If you're starting a new project, we recommend configuring Django and Inertia using a `django-vite-inertia` template.

This will require [uv](https://docs.astral.sh/uv/) or [pipx](https://pipx.pypa.io/stable/) to be installed.

First, let's create a new directory for our project.

```shell
mkdir myproject
```
Next, we'll use the template based installer.

::: code-group

```shell [uv]
uvx copier copy gh:sarthakjariwala/django-vite-inertia myproject
```

```shell [pipx]
pipx run copier copy gh:sarthakjariwala/django-vite-inertia myproject

```

:::

This command will:

- Create a new Django project in your `myproject` directory
- Ask you to choose your preferred frontend framework:
    - React
    - Vue
    - Svelte
- Ask you if you want to use Tailwind CSS
- Ask you the database you want to use
    - SQLite
    - PostgreSQL
- Ask you if you want to use Docker in development
- Ask you if you want to use Docker in production
- Set up Vite integration via `django-vite`
- Set up Django to work with Inertia
- Initialize the Inertia app
- Configure CSRF to work properly with Django

Example output:
```
? Your project name: todo
? Which database do you want to use? postgresql
? Which frontend do you want to use? vue
? Do you want to use Tailwind CSS? Yes
? Do you want to use Docker in development? Yes
? Do you want to use Docker in production? Yes
```

::: warning
The template generates a project for inertia-django, the adapter this package was forked from. After generating it, switch it to this package by following [Upgrading from inertia-django](/guide/upgrading-from-inertia-django): run the codemod, then `python manage.py check`.
:::

You're all set! You can now start your development server.

## Manual setup

::: tip
Skip this section if you used the [template based setup](#template-based-setup) method.
:::

### Install dependencies

Install the server-side adapter and `django-vite`. The adapter is not on PyPI yet, so install it from Git for now.

::: code-group

```shell [uv]
uv add "dj-inertiajs @ git+https://github.com/joshuadavidthomas/inertia-django" django-vite
```

```shell [pip]
python -m pip install "dj-inertiajs @ git+https://github.com/joshuadavidthomas/inertia-django" django-vite
```
:::

For server-side rendering, install the `ssr` extra, which adds `requests`: `"dj-inertiajs[ssr] @ git+https://github.com/joshuadavidthomas/inertia-django"`.

### Update installed apps

Add `django_vite` and `dj_inertiajs` to your `INSTALLED_APPS` in `settings.py`.

```python
INSTALLED_APPS = [
    # ...
    "django_vite",
    "dj_inertiajs",
]
```

### Update middleware

Next, add `dj_inertiajs.middleware.InertiaMiddleware` to your `MIDDLEWARE` in `settings.py`. Inertia stores some state in the session, so `SessionMiddleware` must be there too; new Django projects include it.

```python
MIDDLEWARE = [
    # ...
    "django.contrib.sessions.middleware.SessionMiddleware",
    # ...
    "dj_inertiajs.middleware.InertiaMiddleware",
]
```

### Configure settings

Configure `django-vite` and Inertia in `settings.py`.

```python
# In development, load assets from the Vite dev server, with hot reloading.
DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
    }
}

# Where Vite builds the assets, as configured in the client-side setup.
# collectstatic copies them, with Vite's manifest, into STATIC_ROOT.
STATICFILES_DIRS = [BASE_DIR / "frontend" / "dist"]
```

> For a complete list of available `vite` related settings, see `django-vite` [docs](https://github.com/MrBin99/django-vite?tab=readme-ov-file#django-vite).

All Inertia settings live in one `INERTIA` dict. Only `LAYOUT` is required:

```python
INERTIA = {
    "LAYOUT": "base.html",  # update with your base template name
}
```

> For the other settings, such as `VERSION`, `SHARED_PROPS` and `SSR`, see the [README](https://github.com/joshuadavidthomas/inertia-django#settings).

### Update base template

In your base template, load the `inertia` tags. `{% inertia_head %}` goes in `<head>` and outputs the head tags from server-side rendering, if you use it. `{% inertia_body %}` goes where the app mounts and outputs the root element with the page data.

```django
{% load django_vite inertia %}

...
<head>
    ...
    {% vite_hmr_client %}
    {% vite_asset 'js/main.js' %}
    {% inertia_head %}
</head>

<body>
    {% inertia_body %}
</body>
```

A view can render a different layout by passing `template_name` to `render()`, or by setting `template_name` on a class-based view.

### Check the setup

Run Django's system checks. They report a missing setting, middleware or dependency before the first request:

```shell
python manage.py check
```
