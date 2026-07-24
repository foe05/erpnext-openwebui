"""Schlanker asynchroner Client für die ERPNext-/Frappe-REST-API.

Deckt die Bausteine ab, die der Connector braucht:
- Ressourcen-CRUD über /api/resource/<DocType>
- Whitelisted-Methoden über /api/method/<dotted.path> (u. a. die make_*-Übergänge)

Der Client kennt keine Geschäftslogik — er ist nur der HTTP-Zugang. Auflösung
und Verben sitzen in eigenen Modulen."""

from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings


class ErpNextError(RuntimeError):
    """Fehler aus einem ERPNext-REST-Aufruf (inkl. Statuscode und Server-Text)."""

    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class ErpNextClient:
    def __init__(self, settings: Settings, *, http_client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(
            base_url=settings.base_url,
            headers={
                "Authorization": settings.auth_header,
                "Accept": "application/json",
            },
            timeout=settings.timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "ErpNextClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # -- interne Fehlerbehandlung ------------------------------------------------

    def _unwrap(self, response: httpx.Response) -> Any:
        if response.is_success:
            return response.json().get("data")
        # Frappe verpackt Fehler oft als _server_messages / exception im Body.
        detail: Any
        try:
            detail = response.json()
        except json.JSONDecodeError:
            detail = response.text
        raise ErpNextError(
            f"ERPNext antwortete mit HTTP {response.status_code}",
            status_code=response.status_code,
            detail=detail,
        )

    # -- Ressourcen (DocType-CRUD) ----------------------------------------------

    async def get_doc(self, doctype: str, name: str) -> dict[str, Any]:
        """Ein einzelnes Dokument holen: GET /api/resource/<DocType>/<name>."""
        resp = await self._client.get(f"/api/resource/{doctype}/{name}")
        return self._unwrap(resp)

    async def get_list(
        self,
        doctype: str,
        *,
        filters: list | None = None,
        fields: list[str] | None = None,
        limit: int | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """Eine gefilterte Liste holen: GET /api/resource/<DocType>?..."""
        params: dict[str, str] = {
            "limit_page_length": str(limit or self._settings.default_limit),
        }
        if filters is not None:
            params["filters"] = json.dumps(filters)
        if fields is not None:
            params["fields"] = json.dumps(fields)
        if order_by is not None:
            params["order_by"] = order_by
        resp = await self._client.get(f"/api/resource/{doctype}", params=params)
        return self._unwrap(resp) or []

    async def create_doc(self, doctype: str, doc: dict[str, Any]) -> dict[str, Any]:
        """Ein Dokument anlegen: POST /api/resource/<DocType>."""
        resp = await self._client.post(f"/api/resource/{doctype}", json=doc)
        return self._unwrap(resp)

    async def update_doc(
        self, doctype: str, name: str, patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Ein Dokument ändern: PUT /api/resource/<DocType>/<name>."""
        resp = await self._client.put(f"/api/resource/{doctype}/{name}", json=patch)
        return self._unwrap(resp)

    # -- Methoden (whitelisted, u. a. make_*-Übergänge) -------------------------

    async def call_method(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        http_method: str = "GET",
    ) -> Any:
        """Eine whitelisted Server-Methode aufrufen: /api/method/<dotted.path>.

        Für Übergänge wie erpnext.selling.doctype.quotation.quotation.make_sales_order.
        Komplexe Argumente werden als JSON-String übergeben (Frappe-Konvention)."""
        path = f"/api/method/{method}"
        encoded = {
            k: (v if isinstance(v, str) else json.dumps(v))
            for k, v in (params or {}).items()
        }
        if http_method.upper() == "GET":
            resp = await self._client.get(path, params=encoded)
        else:
            resp = await self._client.post(path, data=encoded)
        return self._unwrap(resp)
