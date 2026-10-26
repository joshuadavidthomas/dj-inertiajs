from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.query import QuerySet
from django.forms.models import model_to_dict as base_model_to_dict


def model_to_dict(model: models.Model) -> dict[str, Any]:
    return base_model_to_dict(model, exclude=("password",))


class InertiaJsonEncoder(DjangoJSONEncoder):
    def default(self, o: Any) -> Any:
        if hasattr(o.__class__, "InertiaMeta"):
            return {
                field: getattr(o, field) for field in o.__class__.InertiaMeta.fields
            }
        if isinstance(o, models.Model):
            return model_to_dict(o)
        if isinstance(o, QuerySet):
            return [
                (model_to_dict(obj) if isinstance(o.model, models.Model) else obj)
                for obj in o
            ]
        return super().default(o)
