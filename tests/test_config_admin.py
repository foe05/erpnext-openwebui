"""Tests für Phase 3 (Config-Blueprint) gegen ein gemocktes ERPNext."""

from __future__ import annotations

import httpx
import pytest

from erpnext_connector.client import ErpNextClient
from erpnext_connector.config import Settings
from erpnext_connector.config_admin import ConfigAdmin
from erpnext_connector.guardrail import STATUS_BESTAETIGUNG

SETTINGS = Settings(base_url="https://x.frappe.cloud", api_key="k", api_secret="s")

BP = {
    "steps": [
        {"doctype": "Item Group", "key": "item_group_name",
         "records": [{"item_group_name": "Neu"}, {"item_group_name": "Alt"}]},
    ]
}


def _admin(handler) -> ConfigAdmin:
    ac = httpx.AsyncClient(
        base_url=SETTINGS.base_url,
        headers={"Authorization": SETTINGS.auth_header},
        transport=httpx.MockTransport(handler),
    )
    return ConfigAdmin(ErpNextClient(SETTINGS, http_client=ac), SETTINGS)


def _handler(existing_names):
    def h(request):
        # Existenz-Prüfung: "Alt" existiert, "Neu" nicht
        if request.method == "GET" and request.url.path == "/api/resource/Item Group":
            import json as _j
            filters = _j.loads(request.url.params.get("filters", "[]"))
            wanted = filters[0][2] if filters else None
            data = [{"name": wanted}] if wanted in existing_names else []
            return httpx.Response(200, json={"data": data})
        if request.method == "POST" and request.url.path == "/api/resource/Item Group":
            import json as _j
            body = _j.loads(request.content)
            return httpx.Response(200, json={"data": {"name": body["item_group_name"]}})
        return httpx.Response(404, json={})
    return h


@pytest.mark.asyncio
async def test_blueprint_vorschau_schreibt_nicht():
    admin = _admin(_handler(existing_names={"Alt"}))
    res = await admin.blueprint_anwenden(blueprint=BP, bestaetigen=False)
    assert res["status"] == "vorschau"
    assert res["anzulegen"] == 1   # nur "Neu"
    assert res["vorhanden"] == 1   # "Alt"


@pytest.mark.asyncio
async def test_blueprint_anwenden_idempotent():
    admin = _admin(_handler(existing_names={"Alt"}))
    res = await admin.blueprint_anwenden(blueprint=BP, bestaetigen=True)
    assert res["status"] == "fertig"
    aktionen = {r["id"]: r["aktion"] for r in res["ergebnis"]}
    assert aktionen["Neu"] == "angelegt"
    assert aktionen["Alt"] == "übersprungen"


@pytest.mark.asyncio
async def test_blueprint_bricht_bei_fehler_ab():
    def h(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})  # nichts existiert
        return httpx.Response(417, json={"exception": "kaputt"})  # create scheitert
    admin = _admin(h)
    res = await admin.blueprint_anwenden(blueprint=BP, bestaetigen=True)
    assert res["status"] == "abgebrochen"
    assert res["bei"]["schluessel"]["item_group_name"] == "Neu"


@pytest.mark.asyncio
async def test_portal_zugang_braucht_bestaetigung():
    admin = _admin(lambda r: httpx.Response(200, json={"data": {"name": "x"}}))
    res = await admin.portal_zugang_anlegen("CUST-1", "a@b.de")
    assert res["status"] == STATUS_BESTAETIGUNG
