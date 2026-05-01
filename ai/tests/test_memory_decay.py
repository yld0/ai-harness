from datetime import date

from ai.memory.decay import (
    decay_score,
    reheat_fact,
    transition_expired_fact,
    update_decay_state,
)
from ai.memory.schemas import FactStatus, MemoryFact, Validity


def point_in_time_fact(access_count: int = 0) -> MemoryFact:
    return MemoryFact(
        id="MSFT-valuation",
        fact="MSFT appears overvalued at 35x P/E",
        category="valuation",
        validity=Validity.POINT_IN_TIME,
        confidence="medium",
        recorded_at=date(2026, 4, 1),
        access_count=access_count,
    )


def test_point_in_time_fact_decays_with_half_life_and_access_reheats() -> None:
    stale = point_in_time_fact(access_count=0)
    reheated = point_in_time_fact(access_count=7)

    stale_score = decay_score(stale, today=date(2026, 4, 15))
    reheated_score = decay_score(reheated, today=date(2026, 4, 15))
    bumped = reheat_fact(stale, accessed_at=date(2026, 4, 15))

    assert 0 < stale_score < 0.5
    assert reheated_score > stale_score
    assert bumped.access_count == 1
    assert bumped.score == 0.7


def test_expired_fact_transitions_to_historical_with_audit_text() -> None:
    expiring = MemoryFact(
        id="MSFT-guidance",
        fact="MSFT guided Q3 revenue to $64B",
        category="guidance",
        validity=Validity.EXPIRES,
        expires=date(2026, 4, 10),
        recorded_at=date(2026, 3, 1),
    )

    transitioned = transition_expired_fact(expiring, today=date(2026, 4, 26))

    assert transitioned.status == FactStatus.HISTORICAL
    assert transitioned.transitioned_at == date(2026, 4, 26)
    assert transitioned.superseded_by_text == "MSFT guided Q3 revenue to $64B"
    assert "historical as of 2026-04-10" in transitioned.fact


def test_update_decay_state_records_score_for_point_in_time() -> None:
    updated = update_decay_state(point_in_time_fact(), today=date(2026, 4, 8))

    assert updated.score is not None
    assert 0 < updated.score < 1
