from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models


@dataclass(frozen=True)
class PlanFeatures:
    plan_id: str
    name: str
    monthly_reports: int | None
    tutorials: tuple[str, ...]


PLAN_FEATURES: dict[str, PlanFeatures] = {
    "free": PlanFeatures(plan_id="free", name="Free", monthly_reports=1, tutorials=("starter",)),
    "pro": PlanFeatures(plan_id="pro", name="Pro", monthly_reports=4, tutorials=("starter", "advanced")),
    "premium": PlanFeatures(plan_id="premium", name="Premium", monthly_reports=None, tutorials=("starter", "advanced", "elite")),
}
PLAN_RANK: dict[str, int] = {"free": 0, "pro": 1, "premium": 2}


def get_plan_features(plan_id: str | None) -> PlanFeatures:
    return PLAN_FEATURES.get(plan_id or "free", PLAN_FEATURES["free"])


def is_subscription_active(sub: models.UserSubscription | None) -> bool:
    if not sub:
        return False
    if sub.status not in {"active", "trialing"}:
        return False
    if sub.current_period_end is None:
        return True
    now = datetime.now(tz=timezone.utc)
    end = sub.current_period_end
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return end > now


async def get_latest_subscription(session: AsyncSession, user_id: str) -> models.UserSubscription | None:
    q = (
        select(models.UserSubscription)
        .where(models.UserSubscription.user_id == user_id)
        .order_by(models.UserSubscription.updated_at.desc(), models.UserSubscription.created_at.desc())
    )
    res = await session.execute(q)
    return res.scalars().first()


async def get_current_plan_id(session: AsyncSession, user_id: str) -> str:
    sub = await get_latest_subscription(session, user_id)
    if is_subscription_active(sub):
        return sub.plan_id
    return "free"


async def can_generate_report(session: AsyncSession, user_id: str) -> tuple[bool, str]:
    plan_id = await get_current_plan_id(session, user_id)
    features = get_plan_features(plan_id)
    if features.monthly_reports is None:
        return True, plan_id

    # Count sent reports in current UTC month
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q = select(func.count(models.Report.id)).where(
        models.Report.user_id == user_id,
        models.Report.status.in_(["queued", "generating", "sent"]),
        models.Report.created_at >= month_start,
    )
    res = await session.execute(q)
    used = int(res.scalar() or 0)
    return used < features.monthly_reports, plan_id


def tutorials_for_plan(plan_id: str) -> tuple[str, ...]:
    return get_plan_features(plan_id).tutorials


def has_tutorial_access(plan_id: str, slug: str) -> bool:
    return slug in set(tutorials_for_plan(plan_id))


def has_plan_access(user_plan_id: str, required_plan_id: str) -> bool:
    return PLAN_RANK.get(user_plan_id, 0) >= PLAN_RANK.get(required_plan_id, 0)


async def upsert_subscription(
    session: AsyncSession,
    *,
    user_id: str,
    provider: str,
    plan_id: str,
    status: str,
    provider_customer_id: str | None,
    provider_subscription_id: str | None,
    current_period_end: datetime | None,
    cancel_at_period_end: bool,
    provider_payload: dict,
) -> models.UserSubscription:
    sub: models.UserSubscription | None = None
    if provider_subscription_id:
        q = select(models.UserSubscription).where(models.UserSubscription.provider_subscription_id == provider_subscription_id)
        res = await session.execute(q)
        sub = res.scalars().first()

    if not sub:
        q = (
            select(models.UserSubscription)
            .where(models.UserSubscription.user_id == user_id)
            .order_by(models.UserSubscription.updated_at.desc(), models.UserSubscription.created_at.desc())
        )
        res = await session.execute(q)
        sub = res.scalars().first()

    if not sub:
        sub = models.UserSubscription(user_id=user_id)
        session.add(sub)

    sub.provider = provider
    sub.plan_id = plan_id
    sub.status = status
    sub.provider_customer_id = provider_customer_id
    sub.provider_subscription_id = provider_subscription_id
    sub.current_period_end = current_period_end
    sub.cancel_at_period_end = cancel_at_period_end
    sub.provider_payload = provider_payload or {}
    await session.flush()
    return sub
