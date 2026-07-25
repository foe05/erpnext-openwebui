"""Tests für Phase 1 (Vertriebs-Rücken): Guardrail, Timesheet-Aggregation und
ausgewählte Verben gegen ein gemocktes ERPNext."""

from __future__ import annotations

import json

import httpx
import pytest

from erpnext_connector.client import ErpNextClient
from erpnext_connector.config import Settings
from erpnext_connector.guardrail import STATUS_BESTAETIGUNG, bestaetigungs_gate
from erpnext_connector.resolve import Resolver
from erpnext_connector.sales import SalesCycle, aggregiere_timesheet_positionen

SETTINGS = Settings(
    base_url="https://x.frappe.cloud",
    api_key="k",
    api_secret="s",
    generic_service_item="SERV-STD",
    default_tax_template="Deutschland 19%",
)


# -- Guardrail -----------------------------------------------------------------


def test_guardrail_blockt_ohne_bestaetigung():
    res = bestaetigungs_gate(False, "Rechnung verbuchen", {"x": 1})
    assert res is not None
    assert res["status"] == STATUS_BESTAETIGUNG
    assert res["aktion"] == "Rechnung verbuchen"


def test_guardrail_laesst_mit_bestaetigung_durch():
    assert bestaetigungs_gate(True, "Rechnung verbuchen", {}) is None


# -- Aggregation (reine Funktion) ---------------------------------------------


def test_aggregation_eine_zeile_je_taetigkeit():
    timesheets = [
        {
            "name": "TS-1",
            "total_billable_hours": 5,
            "total_billable_amount": 600,
            "time_logs": [
                {"is_billable": 1, "activity_type": "Beratung", "billing_hours": 3, "billing_amount": 360},
                {"is_billable": 1, "activity_type": "Doku", "billing_hours": 2, "billing_amount": 240},
            ],
        },
        {
            "name": "TS-2",
            "total_billable_hours": 2,
            "total_billable_amount": 240,
            "time_logs": [
                {"is_billable": 1, "activity_type": "Beratung", "billing_hours": 2, "billing_amount": 240},
                {"is_billable": 0, "activity_type": "Intern", "billing_hours": 1, "billing_amount": 0},
            ],
        },
    ]
    items, links, total = aggregiere_timesheet_positionen(timesheets, "SERV-STD")

    # zwei Tätigkeitsarten -> zwei Positionen; nicht-abrechenbare Zeile ignoriert
    beschreibungen = {i["description"] for i in items}
    assert beschreibungen == {"Beratung", "Doku"}
    beratung = next(i for i in items if i["description"] == "Beratung")
    assert beratung["qty"] == 5  # 3 + 2 Stunden
    assert beratung["rate"] == 120  # 600 / 5
    assert all(i["item_code"] == "SERV-STD" for i in items)
    assert len(links) == 2
    assert total == 840.0


def test_aggregation_leere_timesheets():
    items, links, total = aggregiere_timesheet_positionen([], "SERV-STD")
    assert items == [] and total == 0.0


# -- Verben gegen Mock ---------------------------------------------------------


def _client(handler) -> ErpNextClient:
    ac = httpx.AsyncClient(
        base_url=SETTINGS.base_url,
        headers={"Authorization": SETTINGS.auth_header},
        transport=httpx.MockTransport(handler),
    )
    return ErpNextClient(SETTINGS, http_client=ac)


@pytest.mark.asyncio
async def test_angebot_erstellen_fallback_service_item():
    """Unbekannter Artikel -> generisches Service-Item + Preis-Override."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/resource/Item":
            return httpx.Response(200, json={"data": []})  # kein Artikel gefunden
        if request.url.path == "/api/resource/Quotation" and request.method == "POST":
            captured["doc"] = json.loads(request.content)
            return httpx.Response(200, json={"data": {"name": "QTN-0001", "grand_total": 1428.0}})
        return httpx.Response(404, json={"exc": "nope"})

    sales = SalesCycle(_client(handler), Resolver(_client(handler)), SETTINGS)
    res = await sales.angebot_erstellen(
        "Customer", "CUST-0007", [{"beschreibung": "Beratung", "menge": 10, "preis": 120}]
    )
    assert res["id"] == "QTN-0001"
    pos = captured["doc"]["items"][0]
    assert pos["item_code"] == "SERV-STD"  # Fallback
    assert pos["rate"] == 120  # Override
    assert captured["doc"]["taxes_and_charges"] == "Deutschland 19%"  # Default-Steuer


@pytest.mark.asyncio
async def test_angebot_annehmen_verlangt_bestaetigung_bei_draft():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/resource/Quotation/QTN-0001":
            return httpx.Response(
                200, json={"data": {"name": "QTN-0001", "quotation_to": "Customer", "docstatus": 0, "party_name": "CUST-0007"}}
            )
        return httpx.Response(404, json={"exc": "nope"})

    sales = SalesCycle(_client(handler), Resolver(_client(handler)), SETTINGS)
    res = await sales.angebot_annehmen("QTN-0001", bestaetigen=False)
    assert res["status"] == STATUS_BESTAETIGUNG  # kein Submit ohne Bestätigung


@pytest.mark.asyncio
async def test_angebot_annehmen_lead_verlangt_konvertierung():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": {"name": "QTN-9", "quotation_to": "Lead", "party_name": "LEAD-3", "docstatus": 0}}
        )

    sales = SalesCycle(_client(handler), Resolver(_client(handler)), SETTINGS)
    res = await sales.angebot_annehmen("QTN-9", bestaetigen=True)
    assert res["status"] == "aktion_erforderlich"
    assert "lead_zu_kunde" in res["hinweis"]
