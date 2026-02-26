from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import settings


@dataclass
class CheckoutResult:
    provider: str
    url: str


def _stripe_price_for_plan(plan_id: str) -> str:
    if plan_id == "pro":
        return settings.stripe_price_id_pro or settings.stripe_price_id_monthly or ""
    if plan_id == "premium":
        return settings.stripe_price_id_premium or ""
    return ""


def create_checkout(user_id: str, email: str, plan_id: str) -> CheckoutResult:
    if plan_id not in {"pro", "premium"}:
        raise RuntimeError("Unsupported paid plan")

    if settings.payments_mode == "stripe":
        stripe_price = _stripe_price_for_plan(plan_id)
        if not settings.stripe_secret_key or not stripe_price:
            raise RuntimeError("Stripe is enabled but plan price ID is missing")
        import stripe

        stripe.api_key = settings.stripe_secret_key

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email,
            line_items=[{"price": stripe_price, "quantity": 1}],
            success_url=f"{settings.base_url}/dashboard?paid=1",
            cancel_url=f"{settings.base_url}/pricing?canceled=1",
            metadata={"user_id": user_id, "plan_id": plan_id},
        )
        return CheckoutResult(provider="stripe", url=session.url)

    # mock
    return CheckoutResult(provider="mock", url=f"{settings.base_url}/payments/mock/success?plan={plan_id}")
