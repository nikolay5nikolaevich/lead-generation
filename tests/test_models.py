import pytest
from pydantic import ValidationError

from leadgen.models import EmailHit, Fact, FactKind, Lead, ScoreCriterion, Status


def test_fact_accepts_valid_data():
    fact = Fact(
        kind="size",
        value="180 сотрудников",
        source_url="https://example.ru/about",
        quote="в штате 180 сотрудников",
    )
    assert fact.kind == FactKind.SIZE


def test_fact_rejects_bad_url():
    with pytest.raises(ValidationError):
        Fact(kind="size", value="180", source_url="не ссылка", quote="180 сотрудников")


def test_fact_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        Fact(kind="mood", value="весёлые", source_url="https://example.ru/", quote="весёлые")


def test_fact_rejects_empty_quote():
    with pytest.raises(ValidationError):
        Fact(kind="size", value="180", source_url="https://example.ru/", quote="")


def test_score_criterion_rating_is_limited_to_0_3():
    with pytest.raises(ValidationError):
        ScoreCriterion(criterion="size", rating=4, reasoning="очень большие")


def test_email_hit_rejects_address_without_at():
    with pytest.raises(ValidationError):
        EmailHit(address="info.example.ru", kind="role", source="https://example.ru/", confidence="high")


def test_new_lead_is_pending():
    lead = Lead(domain="example.ru")
    assert lead.status == Status.PENDING
    assert lead.facts == []
