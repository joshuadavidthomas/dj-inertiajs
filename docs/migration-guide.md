# dj-inertiajs Migration Guide

This guide documents all breaking changes and migration steps for dj-inertiajs.

## Overview

This fork reimplements inertia-django following Django best practices and conventions. Major changes include:

- Request handling via proper class inheritance
- Django templatetag system integration  
- Context processor support
- Reorganized package structure
- Improved naming conventions

## Developer Changes

### Development Tooling

The project has switched from Poetry to uv for dependency management:

```bash
# Old (Poetry)
poetry install
poetry run pytest

# New (uv)
uv sync --group dev
uv run pytest
```

### Import Conveniences

Several commonly-used items are now available directly from the `inertia` package:

```python
# These items can now be imported from the base package
from inertia import (
    encrypt_history,      # Previously: from inertia.http import encrypt_history
    clear_history,        # Previously: from inertia.http import clear_history
    InertiaJsonEncoder,   # Previously: from inertia.utils import InertiaJsonEncoder
)

# Note: The old import paths still work for backwards compatibility
```