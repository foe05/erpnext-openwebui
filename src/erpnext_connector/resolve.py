"""Auflösungsschicht — das Rückgrat des Connectors.

Übersetzt menschliche Bezeichnungen ("Acme") in echte ERPNext-IDs
("CUST-0007"), damit Folgeaktionen nie auf geratenen IDs arbeiten.

Jede Auflösung liefert genau eine von drei Lagen:
- unique:    genau ein Treffer  -> `match` gesetzt
- ambiguous: mehrere Kandidaten -> `candidates` gesetzt, Rückfrage nötig
- none:      kein Treffer       -> nichts anlegen, "nicht gefunden"

Das LLM soll bei `ambiguous` zurückfragen und bei `none` nicht raten."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .client import ErpNextClient

Status = Literal["unique", "ambiguous", "none"]


@dataclass
class Resolution:
    status: Status
    match: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    hinweis: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _classify(candidates: list[dict[str, Any]], *, was: str, suchtext: str) -> Resolution:
    if not candidates:
        return Resolution(
            status="none",
            hinweis=f"Kein {was} zu '{suchtext}' gefunden. Nichts angelegt.",
        )
    if len(candidates) == 1:
        return Resolution(status="unique", match=candidates[0])
    return Resolution(
        status="ambiguous",
        candidates=candidates,
        hinweis=(
            f"Mehrere Treffer für {was} '{suchtext}'. Bitte einen Kandidaten "
            "bestätigen, bevor es weitergeht."
        ),
    )


class Resolver:
    """Bündelt die Auflösungs-Werkzeuge gegen einen ERPNext-Client."""

    def __init__(self, client: ErpNextClient, *, limit: int = 8):
        self._client = client
        self._limit = limit

    async def finde_kunde(self, text: str) -> Resolution:
        rows = await self._client.get_list(
            "Customer",
            filters=[["customer_name", "like", f"%{text}%"]],
            fields=["name", "customer_name", "customer_group", "territory"],
            limit=self._limit,
            order_by="modified desc",
        )
        return _classify(rows, was="Kunde", suchtext=text)

    async def finde_party(self, text: str) -> Resolution:
        """Party für ein Angebot: spannt Lead UND Customer auf."""
        customers = await self._client.get_list(
            "Customer",
            filters=[["customer_name", "like", f"%{text}%"]],
            fields=["name", "customer_name"],
            limit=self._limit,
            order_by="modified desc",
        )
        leads = await self._client.get_list(
            "Lead",
            filters=[["lead_name", "like", f"%{text}%"]],
            fields=["name", "lead_name", "company_name", "status"],
            limit=self._limit,
            order_by="modified desc",
        )
        candidates: list[dict[str, Any]] = []
        for c in customers:
            candidates.append(
                {"party_type": "Customer", "id": c["name"], "name": c.get("customer_name")}
            )
        for lead in leads:
            candidates.append(
                {
                    "party_type": "Lead",
                    "id": lead["name"],
                    "name": lead.get("lead_name") or lead.get("company_name"),
                    "status": lead.get("status"),
                }
            )
        return _classify(candidates, was="Party (Lead/Kunde)", suchtext=text)

    async def finde_artikel(self, text: str) -> Resolution:
        """Item-Auflösung. 'none' ist hier ein normales Signal:
        die Hybrid-Item-Strategie fällt dann auf ein generisches Service-Item zurück."""
        rows = await self._client.get_list(
            "Item",
            filters=[["item_name", "like", f"%{text}%"]],
            fields=["name", "item_code", "item_name", "stock_uom", "item_group"],
            limit=self._limit,
            order_by="modified desc",
        )
        res = _classify(rows, was="Artikel", suchtext=text)
        if res.status == "none":
            res.hinweis = (
                f"Kein Artikel zu '{text}' gefunden — Hybrid-Strategie kann auf ein "
                "generisches Service-Item mit freier Beschreibung zurückfallen."
            )
        return res

    async def finde_angebot(self, text: str) -> Resolution:
        """Quotation über Kundenname/Party oder direkte ID suchen."""
        rows = await self._client.get_list(
            "Quotation",
            filters=[["customer_name", "like", f"%{text}%"]],
            fields=["name", "party_name", "customer_name", "status", "grand_total", "transaction_date"],
            limit=self._limit,
            order_by="modified desc",
        )
        return _classify(rows, was="Angebot", suchtext=text)

    async def finde_projekt(self, text: str) -> Resolution:
        rows = await self._client.get_list(
            "Project",
            filters=[["project_name", "like", f"%{text}%"]],
            fields=["name", "project_name", "customer", "status"],
            limit=self._limit,
            order_by="modified desc",
        )
        return _classify(rows, was="Projekt", suchtext=text)
