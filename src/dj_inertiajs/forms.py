from __future__ import annotations

from typing import Any

from django.forms import BaseForm, BaseFormSet

__all__ = ["error_messages"]


def error_messages(
    errors: BaseForm | BaseFormSet[Any] | dict[str, Any],
) -> dict[str, str]:
    """Map each field to its first error message, the shape Inertia forms expect.

    The default ``INERTIA["FORM_ERRORS"]``. Errors not tied to a field stay
    under Django's ``"__all__"`` key. A formset's errors are keyed
    ``"<prefix>.<index>.<field>"``, and its own errors ``"<prefix>"``.
    """
    if isinstance(errors, BaseFormSet):
        prefix = str(errors.prefix)
        result = {}
        if errors.non_form_errors():
            result[prefix] = str(errors.non_form_errors()[0])
        for index, form in enumerate(errors.forms):
            for field, message in error_messages(form).items():
                result[f"{prefix}.{index}.{field}"] = message
        return result
    if isinstance(errors, BaseForm):
        errors = errors.errors
    return {
        field: str(messages[0]) if isinstance(messages, list) else str(messages)
        for field, messages in errors.items()
    }
