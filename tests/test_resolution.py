"""Funktionstests der Auflösungsschicht und des REST-Clients gegen ein
gemocktes ERPNext (kein Live-Zugang nötig).

Ausführen:
    pip install -e . pytest
    pytest
"""

from __future__ import annotations

import httpx
import pytest

from erpnext_connector.client import ErpNextClient, ErpNextError
from erpnext_connector.config import Settings
from erpnext_connector.resolve import Resolver

SETTINGS = Settings(base_url="https://x.frappe.cloud", api_key="k", api_secret="s")


def _make_resolver(handler) -> tuple[ErpNextClient, Resolver]:
    ac = httpx.AsyncClient(
        base_url=SETTINGS.base_url,
        headers={"Authorization": SETTINGS.auth_header},
        transport=httpx.MockTransport(handler),
    )
    client = ErpNextClient(SETTINGS, http_client=ac)
    return client, Resolver(client)


def _customer_handler(request: httpx.Request) -> httpx.Response:
    # Auth-Header muss dem Frappe-Token-Format entsprechen
    assert request.headers["Authorization"] == "token k:s"
    path = request.url.path
    if path == "/api/resource/Customer":
        filters = request.url.params.get("filters", "")
        if "Acme" in filters:
            data = [{"name": "CUST-0007", "customer_name": "Acme GmbH"}]
        elif "Meier" in filters:
            data = [
                {"name": "CUST-1", "customer_name": "Meier AG"},
                {"name": "CUST-2", "customer_name": "Meier & Co"},
            ]
        else:
            data = []
        return httpx.Response(200, json={"data": data})
    if path in ("/api/resource/Lead", "/api/resource/Item"):
        return httpx.Response(200, json={"data": []})
    if path.startswith("/api/resource/Customer/"):
        return httpx.Response(200, json={"data": {"name": "CUST-0007", "customer_name": "Acme GmbH"}})
    return httpx.Response(404, json={"exc": "not found"})


@pytest.mark.asyncio
async def test_finde_kunde_unique():
    client, r = _make_resolver(_customer_handler)
    res = await r.finde_kunde("Acme")
    assert res.status == "unique"
    assert res.match["name"] == "CUST-0007"
    await client.aclose()


@pytest.mark.asyncio
async def test_finde_kunde_ambiguous():
    client, r = _make_resolver(_customer_handler)
    res = await r.finde_kunde("Meier")
    assert res.status == "ambiguous"
    assert len(res.candidates) == 2
    assert res.match is None
    await client.aclose()


@pytest.mark.asyncio
async def test_finde_kunde_none_legt_nichts_an():
    client, r = _make_resolver(_customer_handler)
    res = await r.finde_kunde("Nixgibts")
    assert res.status == "none"
    assert res.match is None
    await client.aclose()


@pytest.mark.asyncio
async def test_hole_dokument():
    client, _ = _make_resolver(_customer_handler)
    doc = await client.get_doc("Customer", "CUST-0007")
    assert doc["customer_name"] == "Acme GmbH"
    await client.aclose()


@pytest.mark.asyncio
async def test_http_fehler_wird_erpnext_error():
    client, _ = _make_resolver(_customer_handler)
    with pytest.raises(ErpNextError) as exc:
        await client.get_list("Unbekannt")
    assert exc.value.status_code == 404
    await client.aclose()
