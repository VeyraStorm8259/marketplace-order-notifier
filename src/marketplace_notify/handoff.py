from dataclasses import dataclass
from typing import Protocol

from .models import HandoffResult, OrderHandoff, PublishedUpdate


class Publisher(Protocol):
    def create_channel(self, channel: str, *, idempotency_key: str) -> dict[str, object]:
        pass

    def publish(
        self,
        *,
        channel: str,
        event: str,
        data: dict[str, str],
        account_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        pass


@dataclass(frozen=True)
class NotificationPlan:
    audience: str
    account_id: str
    channel: str
    event: str


def plan_handoff(order: OrderHandoff) -> list[NotificationPlan]:
    suffix = "pickup_ready" if order.state == "ready_for_pickup" else "handoff_complete"
    return [
        NotificationPlan(
            audience="buyer",
            account_id=order.buyer_id,
            channel=f"marketplace:user:{order.buyer_id}",
            event=f"order.{suffix}",
        ),
        NotificationPlan(
            audience="seller",
            account_id=order.seller_id,
            channel=f"marketplace:user:{order.seller_id}",
            event=f"order.{suffix}",
        ),
    ]


def publish_handoff(publisher: Publisher, order: OrderHandoff) -> HandoffResult:
    updates: list[PublishedUpdate] = []
    data = {
        "order_id": order.order_id,
        "listing_id": order.asset.listing_id,
        "title": order.asset.title,
        "state": order.state,
    }
    for item in plan_handoff(order):
        publisher.create_channel(
            item.channel,
            idempotency_key=f"channel:{item.channel}",
        )
        publisher.publish(
            channel=item.channel,
            event=item.event,
            data=data,
            account_id=item.account_id,
            idempotency_key=f"order:{order.order_id}:{order.state}:{item.audience}",
        )
        updates.append(
            PublishedUpdate(
                audience=item.audience,
                channel=item.channel,
                event=item.event,
            )
        )
    return HandoffResult(order_id=order.order_id, state=order.state, updates=updates)
