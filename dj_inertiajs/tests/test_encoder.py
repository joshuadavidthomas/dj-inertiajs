from datetime import date, datetime
from json import dumps

from django.test import TestCase

from dj_inertiajs.encoders import InertiaJsonEncoder
from dj_inertiajs.tests.testapp.models import Sport, User


def make_brandon() -> User:
    return User(
        name="Brandon",
        password="something-top-secret",
        birthdate=date(1987, 2, 15),
        registered_at=datetime(2022, 10, 31, 10, 13, 1),
    )


class InertiaJsonEncoderTestCase(TestCase):
    def setUp(self):
        self.encode = lambda obj: dumps(obj, cls=InertiaJsonEncoder)

    def test_models_without_inertia_meta_are_not_encoded(self):
        with self.assertRaisesMessage(
            TypeError, "list the fields in an InertiaMeta inner class on User"
        ):
            self.encode({"user": make_brandon()})

    def test_it_handles_inertia_meta_fields(self):
        sport = Sport(
            id=3,
            name="Hockey",
            season="Winter",
            created_at=datetime(2022, 10, 31, 10, 13, 1),
        )

        self.assertEqual(
            dumps(
                {
                    "id": 3,
                    "name": "Hockey",
                    "created_at": "2022-10-31T10:13:01",
                }
            ),
            self.encode(sport),
        )

    def test_it_handles_querysets(self):
        sport = Sport.objects.create(id=3, name="Hockey", season="Winter")
        created_at = sport.created_at.isoformat()

        self.assertEqual(
            self.encode(Sport.objects.all()),
            dumps([{"id": 3, "name": "Hockey", "created_at": created_at}]),
        )
        self.assertEqual(
            self.encode(Sport.objects.values("name", "season")),
            dumps([{"name": "Hockey", "season": "Winter"}]),
        )

    def test_it_handles_non_model_querysets(self):
        user = make_brandon()
        user.save()
        self.assertEqual(
            self.encode(User.objects.values_list("name", flat=True)),
            self.encode([user.name]),
        )
