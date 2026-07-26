"""Tests für Phase 2 (CRM & Gedächtnis) gegen ein gemocktes ERPNext."""

from __future__ import annotations

import json

import httpx
import pytest

from erpnext_connector.client import ErpNextClient
from erpnext_connector.config import Settings
from erpnext_connector.crm import CrmMemory

SETTINGS = Settings(base_url="https://x.frappe.cloud", api_key="k", api_secret="s")
SETTINGS_MIT_USER = Settings(
    base_url="https://x.frappe.cloud", api_key="k", api_secret="s",
    default_user="chef@example.com",
)


def _client(handler) -> ErpNextClient:
    ac = httpx.AsyncClient(
        base_url=SETTINGS.base_url,
        headers={"Authorization": SETTINGS.auth_header},
        transport=httpx.MockTransport(handler),
    )
    return ErpNextClient(SETTINGS, http_client=ac)


@pytest.mark.asyncio
async def test_kundenhistorie_bleibt_robust_bei_fehlern():
    # Alle Listen-Abfragen scheitern -> Historie liefert leere Blöcke, kein Fehler.
    def handler(request):
        return httpx.Response(500, json={"exc": "boom"})

    crm = CrmMemory(_client(handler), SETTINGS)
    h = await crm.kundenhistorie("CUST-1")
    assert h["kunde"] == "CUST-1"
    assert h["rechnungen"] == [] and h["projekte"] == []


@pytest.mark.asyncio
async def test_aktivitaet_loggen_baut_communication():
    captured = {}

    def handler(request):
        if request.url.path == "/api/resource/Communication" and request.method == "POST":
            captured["doc"] = json.loads(request.content)
            return httpx.Response(200, json={"data": {"name": "COMM-1"}})
        return httpx.Response(404, json={})

    crm = CrmMemory(_client(handler), SETTINGS)
    res = await crm.aktivitaet_loggen("Customer", "CUST-1", "Telefonat", "Betreff")
    assert res["id"] == "COMM-1"
    doc = captured["doc"]
    assert doc["reference_doctype"] == "Customer"
    assert doc["reference_name"] == "CUST-1"
    assert doc["content"] == "Telefonat"
    assert doc["communication_type"] == "Communication"


@pytest.mark.asyncio
async def test_erinnerung_ohne_zustaendigen_warnt():
    def handler(request):
        return httpx.Response(200, json={"data": {"name": "TODO-1"}})

    crm = CrmMemory(_client(handler), SETTINGS)  # ohne default_user
    res = await crm.erinnerung_anlegen("Customer", "CUST-1", "Nachfassen", "2026-08-01")
    assert res["id"] == "TODO-1"
    assert res["warnungen"], "ohne Zuständigen muss gewarnt werden"


@pytest.mark.asyncio
async def test_erinnerung_nutzt_default_user():
    captured = {}

    def handler(request):
        captured["doc"] = json.loads(request.content)
        return httpx.Response(200, json={"data": {"name": "TODO-2"}})

    ac = httpx.AsyncClient(
        base_url=SETTINGS_MIT_USER.base_url,
        headers={"Authorization": SETTINGS_MIT_USER.auth_header},
        transport=httpx.MockTransport(handler),
    )
    crm = CrmMemory(ErpNextClient(SETTINGS_MIT_USER, http_client=ac), SETTINGS_MIT_USER)
    res = await crm.erinnerung_anlegen("Customer", "CUST-1", "Nachfassen", "2026-08-01")
    assert not res["warnungen"]
    assert captured["doc"]["allocated_to"] == "chef@example.com"
