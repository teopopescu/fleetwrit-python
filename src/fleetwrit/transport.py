"""Transport interface plus the httpx implementation over the ``/v1`` API.

Tests inject a fake; production uses :class:`HttpTransport`. Network errors
become ``FleetwritUnavailable`` (never fail open).
"""

from __future__ import annotations

import time
from typing import Any, Protocol, runtime_checkable

from .exceptions import FleetwritAlreadyConsumed, FleetwritUnavailable


@runtime_checkable
class Transport(Protocol):
    """The operations the Client needs from a server or a fake."""

    def register(self, payload: dict[str, Any]) -> None: ...

    def create_request(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_decision(self, request_id: str, wait: int = 30) -> dict[str, Any]: ...

    def ack(self, request_id: str) -> None: ...

    def cancel(self, request_id: str) -> None: ...


class HttpTransport:
    """httpx transport for the agent-facing ``/v1`` API (key-authenticated).

    Implemented but not required to connect in v0. Retries with backoff, then
    raises ``FleetwritUnavailable`` rather than failing open.
    """

    def __init__(
        self,
        url: str | None,
        api_key: str | None,
        *,
        timeout: float = 30.0,
        max_retry_seconds: float = 60.0,
    ) -> None:
        self.url = (url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retry_seconds = max_retry_seconds

    def _client(self) -> Any:
        if not self.url:
            raise FleetwritUnavailable(
                "FLEETWRIT_URL is not set and no transport was injected"
            )
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - httpx is a hard dep
            raise FleetwritUnavailable("httpx is not installed") from exc
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return httpx.Client(base_url=self.url, headers=headers, timeout=self.timeout)

    def _request(self, method: str, path: str, **kw: Any) -> Any:
        import httpx

        deadline = time.monotonic() + self.max_retry_seconds
        attempt = 0
        while True:
            attempt += 1
            try:
                with self._client() as client:
                    resp = client.request(method, path, **kw)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPStatusError:
                raise
            except httpx.HTTPError as exc:
                if time.monotonic() >= deadline:
                    raise FleetwritUnavailable(
                        f"server unreachable after {attempt} attempts: {exc}"
                    ) from exc
                time.sleep(min(2**attempt * 0.1, 5.0))

    def register(self, payload: dict[str, Any]) -> None:
        self._request("POST", "/v1/agents/register", json=payload)

    def create_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._request("POST", "/v1/requests", json=payload)
        return resp.json()

    def get_decision(self, request_id: str, wait: int = 30) -> dict[str, Any]:
        resp = self._request(
            "GET", f"/v1/requests/{request_id}/decision", params={"wait": wait}
        )
        return resp.json()

    def ack(self, request_id: str) -> None:
        import httpx

        try:
            self._request("POST", f"/v1/requests/{request_id}/ack")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                raise FleetwritAlreadyConsumed(
                    f"decision for {request_id} was already consumed"
                ) from exc
            raise

    def cancel(self, request_id: str) -> None:
        self._request("POST", f"/v1/requests/{request_id}/cancel")
