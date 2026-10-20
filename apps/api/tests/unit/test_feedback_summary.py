from app.modules.feedback.models import Relationship
from app.modules.feedback.summary import rating_group, rating_mean


def test_mean_is_decimal_half_up_and_empty_is_null():
    assert rating_mean([]) is None
    assert rating_mean([1, 2, 2]) == "1.67"
    assert rating_mean([1] * 7 + [2]) == "1.13"


def test_small_groups_have_identical_shape_for_zero_one_two():
    for relationship in (Relationship.PEER, Relationship.SUBORDINATE):
        for ratings in ([], [1], [1, 5]):
            assert rating_group(relationship, ratings).model_dump() == {
                "relationship": relationship,
                "suppressed": True,
                "count": None,
                "mean": None,
            }
        group = rating_group(relationship, [1, 5, 4])
        assert group.count == 3 and group.mean == "3.33" and not group.suppressed


def test_mandatory_group_is_visible_without_comments():
    group = rating_group(Relationship.SELF, [4])
    assert group.count == 1 and group.mean == "4.00" and not group.suppressed


def test_deadline_exact_boundary_is_expired(monkeypatch):
    from datetime import UTC, datetime, timedelta

    import pytest

    from app.core.errors import ApiError
    from app.modules.feedback import service

    now = datetime(2026, 10, 20, tzinfo=UTC)

    class Clock:
        @staticmethod
        def now(tz):
            return now

    monkeypatch.setattr(service, "datetime", Clock)
    service.future_deadline(None)
    service.future_deadline(now + timedelta(microseconds=1))
    with pytest.raises(ApiError) as exc:
        service.future_deadline(now)
    assert exc.value.code == "deadline_passed"
