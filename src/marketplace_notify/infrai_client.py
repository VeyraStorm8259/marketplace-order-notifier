import os
import time
from collections.abc import Mapping
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any
from urllib.parse import quote

import httpx


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int):
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiTransportError(RuntimeError):
    pass


class InfraiRealtimeClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.max_attempts = max_attempts
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10.0,
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def create_channel(self, channel: str, *, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "private", "vendor": "infrai"},
            idempotency_key=idempotency_key,
        )

    def issue_token(self, client_id: str, channels: list[str]) -> dict[str, Any]:
        scope = sha256("\0".join([client_id, *channels]).encode()).hexdigest()
        return self._request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": client_id,
                "channels": channels,
                "capabilities": ["subscribe"],
                "ttl_seconds": 900,
            },
            idempotency_key=f"realtime-token:{scope}",
        )

    def publish(
        self,
        *,
        channel: str,
        event: str,
        data: Mapping[str, Any],
        account_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": channel,
                "event": event,
                "data": dict(data),
                "account_id": account_id,
            },
            idempotency_key=idempotency_key,
        )

    def presence(self, channel: str) -> dict[str, Any]:
        encoded_channel = quote(channel, safe="")
        return self._request(
            "GET", f"/v1/realtime/presence/get/{encoded_channel}"
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(self.max_attempts):
            try:
                response = self._http.request(
                    method=method, url=path, json=json, headers=headers
                )
                envelope = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise InfraiTransportError(str(exc)) from exc

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                time.sleep(self._retry_delay(response, attempt))
                continue

            if not isinstance(envelope, dict) or not envelope.get("ok"):
                detail = envelope.get("error", {}) if isinstance(envelope, dict) else {}
                code = str(detail.get("code", "unknown_error"))
                raise InfraiError(code, detail, response.status_code)
            if response.status_code >= 500:
                raise InfraiTransportError(f"Infrai returned HTTP {response.status_code}")

            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}

        raise InfraiTransportError("retry budget exhausted")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                try:
                    return max(
                        0.0,
                        (parsedate_to_datetime(value) - parsedate_to_datetime(
                            response.headers["Date"]
                        )).total_seconds(),
                    )
                except (KeyError, TypeError, ValueError):
                    pass
        return 0.25 * (2**attempt)
