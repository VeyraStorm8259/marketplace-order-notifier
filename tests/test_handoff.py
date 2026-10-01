from marketplace_notify.handoff import publish_handoff
from marketplace_notify.models import OrderHandoff, SellerAsset


class RecordingPublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.channels: list[dict[str, object]] = []
        self.operations: list[str] = []

    def create_channel(self, channel: str, *, idempotency_key: str) -> dict[str, object]:
        self.operations.append("create")
        self.channels.append({"channel": channel, "idempotency_key": idempotency_key})
        return {"created": True}

    def publish(self, **request: object) -> dict[str, object]:
        self.operations.append("publish")
        self.calls.append(request)
        return {"published": True}


def test_pickup_ready_routes_asset_update_to_buyer_and_seller() -> None:
    publisher = RecordingPublisher()
    order = OrderHandoff(
        order_id="ord_1042",
        seller_id="seller_7",
        buyer_id="buyer_9",
        asset=SellerAsset(listing_id="listing_31", title="Walnut desk"),
        state="ready_for_pickup",
    )

    result = publish_handoff(publisher, order)

    assert publisher.operations == ["create", "publish", "create", "publish"]
    assert publisher.channels == [
        {"channel": "marketplace:user:buyer_9", "idempotency_key": "channel:marketplace:user:buyer_9"},
        {"channel": "marketplace:user:seller_7", "idempotency_key": "channel:marketplace:user:seller_7"},
    ]
    assert [call["channel"] for call in publisher.calls] == [
        "marketplace:user:buyer_9",
        "marketplace:user:seller_7",
    ]
    assert {call["event"] for call in publisher.calls} == {"order.pickup_ready"}
    assert publisher.calls[0]["data"] == {
        "order_id": "ord_1042",
        "listing_id": "listing_31",
        "title": "Walnut desk",
        "state": "ready_for_pickup",
    }
    assert [call["idempotency_key"] for call in publisher.calls] == [
        "order:ord_1042:ready_for_pickup:buyer",
        "order:ord_1042:ready_for_pickup:seller",
    ]
    assert [update.audience for update in result.updates] == ["buyer", "seller"]
