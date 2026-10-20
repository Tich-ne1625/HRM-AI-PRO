from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.feedback.schemas import AssignmentCreate, AssignmentUpdate, FeedbackCreate


def submission(**changes):
    return dict(
        assignment_id=str(uuid4()),
        expected_assignment_version=1,
        expected_evidence_version=2,
        rating=4,
        comment="Useful feedback",
        **changes,
    )


@pytest.mark.parametrize("rating", [True, False, 0, 6, 1.0, "4", None])
def test_rating_must_be_strict_integer(rating):
    data = submission()
    data["rating"] = rating
    with pytest.raises(ValidationError):
        FeedbackCreate.model_validate(data)


def test_comment_normalizes_lines_and_keeps_plain_text():
    data = submission()
    data["comment"] = "  <b>Good</b>\r\nNext\tstep  "
    assert FeedbackCreate.model_validate(data).comment == "<b>Good</b>\nNext\tstep"


@pytest.mark.parametrize("comment", ["x" * 2001, "a\x00b", "a\x7fb", "a\x0bb", "a\x1fb"])
def test_rejects_oversized_or_control_character_comments(comment):
    data = submission()
    data["comment"] = comment
    with pytest.raises(ValidationError):
        FeedbackCreate.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewer_id", str(uuid4())),
        ("participant_id", str(uuid4())),
        ("relationship", "SELF"),
        ("expected_assignment_version", True),
        ("expected_evidence_version", 0),
    ],
)
def test_submission_rejects_forged_identity_and_invalid_versions(field, value):
    data = submission()
    data[field] = value
    with pytest.raises(ValidationError):
        FeedbackCreate.model_validate(data)


def assignment(**changes):
    return {
        "participant_id": str(uuid4()),
        "reviewer_id": str(uuid4()),
        "relationship": "PEER",
        "required": False,
        "expected_evidence_version": 2,
    } | changes


@pytest.mark.parametrize("due", ["2026-11-01T12:00:00", 1793534400, True, "2026-11-01"])
def test_deadline_requires_explicit_timezone(due):
    with pytest.raises(ValidationError):
        AssignmentCreate.model_validate(assignment(due_at=due))


def test_deadline_normalizes_to_utc_and_accepts_null():
    row = AssignmentCreate.model_validate(assignment(due_at="2026-11-01T12:00:00+07:00"))
    assert row.due_at == datetime(2026, 11, 1, 5, tzinfo=UTC)
    assert AssignmentCreate.model_validate(assignment(due_at=None)).due_at is None


@pytest.mark.parametrize("relationship", ["SELF", "MANAGER"])
def test_mandatory_relationship_cannot_be_optional(relationship):
    with pytest.raises(ValidationError):
        AssignmentCreate.model_validate(assignment(relationship=relationship))


@pytest.mark.parametrize(
    "changes", [{}, {"required": None}, {"status": "CANCELLED"}, {"reviewer_id": str(uuid4())}]
)
def test_assignment_patch_requires_supported_change(changes):
    with pytest.raises(ValidationError):
        AssignmentUpdate.model_validate(
            {"expected_assignment_version": 1, "expected_evidence_version": 2} | changes
        )


def test_patch_can_explicitly_clear_deadline():
    row = AssignmentUpdate.model_validate(
        {"expected_assignment_version": 1, "expected_evidence_version": 2, "due_at": None}
    )
    assert "due_at" in row.model_fields_set
