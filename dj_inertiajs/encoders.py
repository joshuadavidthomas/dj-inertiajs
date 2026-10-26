from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.query import QuerySet


class InertiaJsonEncoder(DjangoJSONEncoder):
    """Encode props like ``DjangoJSONEncoder``, plus two additions.

    An object whose class has an ``InertiaMeta`` inner class is encoded as
    the attributes listed in ``InertiaMeta.fields``, and a ``QuerySet`` as a
    list of its items. Models are not encoded implicitly, so a prop sends
    only the fields a view or ``InertiaMeta`` names.
    """

    def default(self, o: Any) -> Any:
        meta = getattr(type(o), "InertiaMeta", None)
        if meta is not None:
            return {field: getattr(o, field) for field in meta.fields}
        if isinstance(o, QuerySet):
            return list(o)
        if isinstance(o, models.Model):
            raise TypeError(
                f"Object of type {type(o).__name__} is not JSON serializable. "
                "Models are not encoded implicitly: send a dict of the fields "
                "the page needs, use QuerySet.values(), or list the fields in "
                f"an InertiaMeta inner class on {type(o).__name__}."
            )
        return super().default(o)
