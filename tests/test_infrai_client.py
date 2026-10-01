import httpx

from marketplace_notify.infrai_client import InfraiRealtimeClient


def test_publish_decodes_envelope_and_sends_idempotency_key() -> None:
    captured: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True, "data": {"published": True}})

    client = InfraiRealtimeClient(
        "test-key", transport=httpx.MockTransport(respond)
    )
    try:
        result = client.publish(
            channel="marketplace:user:buyer_9",
            event="order.pickup_ready",
            data={"order_id": "ord_1042"},
            account_id="buyer_9",
            idempotency_key="order:ord_1042:ready_for_pickup:buyer",
        )
    finally:
        client.close()

    assert result == {"published": True}
    assert captured[0].method == "POST"
    assert captured[0].headers["Idempotency-Key"] == "order:ord_1042:ready_for_pickup:buyer"

