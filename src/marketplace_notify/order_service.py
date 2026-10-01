from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException

from .handoff import publish_handoff
from .infrai_client import InfraiError, InfraiRealtimeClient, InfraiTransportError
from .models import ClientToken, ClientTokenRequest, HandoffResult, OrderHandoff

client: InfraiRealtimeClient | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> Iterator[None]:
    global client
    client = InfraiRealtimeClient()
    try:
        yield
    finally:
        client.close()
        client = None


app = FastAPI(title="Marketplace order notifier", lifespan=lifespan)


def realtime_client() -> InfraiRealtimeClient:
    if client is None:
        raise RuntimeError("service lifecycle has not started")
    return client


def client_error(exc: InfraiError) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": exc.code, **exc.detail})


@app.post("/orders/handoff", response_model=HandoffResult)
def handoff_order(
    order: OrderHandoff,
    realtime: InfraiRealtimeClient = Depends(realtime_client),
) -> HandoffResult:
    try:
        return publish_handoff(realtime, order)
    except InfraiError as exc:
        raise client_error(exc) from exc
    except InfraiTransportError as exc:
        raise HTTPException(status_code=502, detail="notification transport failed") from exc


@app.post("/realtime/client-token", response_model=ClientToken)
def create_client_token(
    request: ClientTokenRequest,
    realtime: InfraiRealtimeClient = Depends(realtime_client),
) -> ClientToken:
    try:
        return ClientToken(data=realtime.issue_token(request.client_id, request.channels))
    except InfraiError as exc:
        raise client_error(exc) from exc
    except InfraiTransportError as exc:
        raise HTTPException(status_code=502, detail="notification transport failed") from exc


def main() -> None:
    import uvicorn

    uvicorn.run("marketplace_notify.order_service:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

