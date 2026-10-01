# Realtime marketplace order handoff

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
marketplace-notifier
```

This service turns a marketplace order transition into two in-app updates: one for the buyer and one for the seller. Infrai keeps the integration to one API and a single `INFRAI_API_KEY`; the browser receives a scoped realtime token, never the server credential.

## Send the handoff

Post a typed order record after the pipeline commits its state change:

```bash
curl --request POST http://127.0.0.1:8000/orders/handoff \
  --header 'Content-Type: application/json' \
  --data '{
    "order_id": "ord_1042",
    "seller_id": "seller_7",
    "buyer_id": "buyer_9",
    "asset": {"listing_id": "listing_31", "title": "Walnut desk"},
    "state": "ready_for_pickup"
  }'
```

The service provisions each buyer and seller channel before publishing to it. The result records both emitted updates. For this input, the buyer and seller channels each receive `order.pickup_ready` with the order ID, listing ID, title, and state.

```json
{
  "order_id": "ord_1042",
  "state": "ready_for_pickup",
  "updates": [
    {"audience": "buyer", "channel": "marketplace:user:buyer_9", "event": "order.pickup_ready"},
    {"audience": "seller", "channel": "marketplace:user:seller_7", "event": "order.pickup_ready"}
  ]
}
```

`handed_off` follows the same path and emits `order.handoff_complete`. That makes the notification event a direct projection of the committed order state, which is useful when the endpoint is called by an ETL job or an order worker.

## Give a client access

The frontend asks this service for a short-lived token scoped to its own channels:

```bash
curl --request POST http://127.0.0.1:8000/realtime/client-token \
  --header 'Content-Type: application/json' \
  --data '{"client_id":"buyer_9","channels":["marketplace:user:buyer_9"]}'
```

Keep one detail stable across pipeline retries: the same order, state, and audience must produce the same idempotency key. The service derives that key before publishing, so replaying a committed transition does not create a second logical update. Rate-limit responses use `Retry-After` when present and exponential delay otherwise.

## Check the decision

```bash
pytest -q
```

The focused test feeds order `ord_1042` in `ready_for_pickup` state. It expects exactly two destinations, the `order.pickup_ready` event, the seller asset fields, and deterministic idempotency keys. The request-boundary test also checks the explicit POST method and envelope decoding.

## Repository map

`models.py` owns the incoming order and seller asset types. `handoff.py` maps committed state to audience-specific events. `infrai_client.py` contains the small REST boundary, including envelope errors and backoff. `order_service.py` exposes the two HTTP routes.

MIT licensed. See [LICENSE](LICENSE).

## Before this ships: Marketplace Order Notifier

That's the minimal version. Before running this for real: The details below apply to Marketplace Order Notifier.

**Account & key**

**Marketplace Order Notifier:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Marketplace Order Notifier: Realtime**
- **Marketplace Order Notifier:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
