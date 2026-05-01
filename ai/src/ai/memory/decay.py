"""Temporal validity and decay logic for financial facts."""

from dataclasses import replace
from datetime import date
from math import exp, log, log2

from ai.memory.schemas import FactStatus, MemoryFact, Validity

SUMMARY_DROP_THRESHOLD = 0.2
REHEAT_SCORE = 0.7


def decay_score(fact: MemoryFact, *, today: date) -> float:
    if fact.status != FactStatus.ACTIVE:
        return 0.0
    if fact.validity in {Validity.EVERGREEN, Validity.EXPIRES}:
        return 1.0
    age_days = max(0, (today - fact.recorded_at).days)
    base_half_life = fact.half_life_days or 14
    effective_half_life = base_half_life * (1 + log2(1 + max(0, fact.access_count)))
    lam = log(2) / effective_half_life
    confidence_multiplier = {"low": 0.8, "medium": 1.0, "high": 1.15}[fact.confidence.value]
    return max(0.0, min(1.0, exp(-lam * age_days) * confidence_multiplier))


def reheat_fact(fact: MemoryFact, *, accessed_at: date) -> MemoryFact:
    return fact.model_copy(
        update={
            "last_accessed": accessed_at,
            "access_count": fact.access_count + 1,
            "score": max(fact.score or 0.0, REHEAT_SCORE),
        }
    )


def transition_expired_fact(fact: MemoryFact, *, today: date) -> MemoryFact:
    if fact.validity != Validity.EXPIRES or fact.expires is None or fact.expires >= today or fact.status != FactStatus.ACTIVE:
        return fact
    historical_text = f"{fact.fact} (historical as of {fact.expires.isoformat()})"
    return fact.model_copy(
        update={
            "status": FactStatus.HISTORICAL,
            "transitioned_at": today,
            "superseded_by_text": fact.fact,
            "fact": historical_text,
        }
    )


def update_decay_state(fact: MemoryFact, *, today: date) -> MemoryFact:
    transitioned = transition_expired_fact(fact, today=today)
    if transitioned.validity != Validity.POINT_IN_TIME or transitioned.status != FactStatus.ACTIVE:
        return transitioned
    return transitioned.model_copy(update={"score": decay_score(transitioned, today=today)})


def include_in_summary(fact: MemoryFact, *, today: date) -> bool:
    updated = update_decay_state(fact, today=today)
    if updated.status == FactStatus.SUPERSEDED:
        return False
    if updated.status == FactStatus.HISTORICAL:
        return True
    if updated.validity == Validity.POINT_IN_TIME:
        return (updated.score if updated.score is not None else decay_score(updated, today=today)) >= SUMMARY_DROP_THRESHOLD
    return True
