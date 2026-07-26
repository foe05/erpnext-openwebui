"""Phase 2 — CRM & Gedächtnis.

Verben rund um Kundenhistorie, Aktivitäten und Erinnerungen. Erinnerungen sind
bewusst PUSH: der Connector legt ein ERPNext-ToDo an, dessen Zustellung ERPNext
selbst übernimmt (Assignment/Notification) — der Connector erzeugt von sich aus
keine Chat-Nachrichten.

Hinweis: Feldnamen an der echten Instanz verifizieren."""

from __future__ import annotations

from datetime import date
from typing import Any

from .client import ErpNextClient, ErpNextError
from .config import Settings


class CrmMemory:
    def __init__(self, client: ErpNextClient, settings: Settings):
        self._client = client
        self._settings = settings

    async def _safe_list(self, doctype: str, **kw: Any) -> list[dict[str, Any]]:
        """Liste holen, aber bei Fehlern (z. B. DocType fehlt) leer zurückgeben,
        damit die Historie robust bleibt."""
        try:
            return await self._client.get_list(doctype, **kw)
        except ErpNextError:
            return []

    async def kundenhistorie(self, kunde_id: str) -> dict[str, Any]:
        """Verknüpfte Belege, Kommunikation und offene Erinnerungen eines Kunden
        zusammenführen."""
        angebote = await self._safe_list(
            "Quotation",
            filters=[["party_name", "=", kunde_id]],
            fields=["name", "status", "grand_total", "transaction_date"],
            limit=10,
        )
        auftraege = await self._safe_list(
            "Sales Order",
            filters=[["customer", "=", kunde_id]],
            fields=["name", "status", "grand_total", "transaction_date"],
            limit=10,
        )
        rechnungen = await self._safe_list(
            "Sales Invoice",
            filters=[["customer", "=", kunde_id]],
            fields=["name", "status", "grand_total", "outstanding_amount", "posting_date"],
            limit=10,
        )
        projekte = await self._safe_list(
            "Project",
            filters=[["customer", "=", kunde_id]],
            fields=["name", "status", "project_name"],
            limit=10,
        )
        kommunikation = await self._safe_list(
            "Communication",
            filters=[["reference_doctype", "=", "Customer"], ["reference_name", "=", kunde_id]],
            fields=["subject", "communication_date", "communication_medium"],
            limit=15,
        )
        erinnerungen = await self._safe_list(
            "ToDo",
            filters=[
                ["reference_type", "=", "Customer"],
                ["reference_name", "=", kunde_id],
                ["status", "=", "Open"],
            ],
            fields=["name", "description", "date", "allocated_to"],
            limit=10,
        )
        return {
            "kunde": kunde_id,
            "angebote": angebote,
            "auftraege": auftraege,
            "rechnungen": rechnungen,
            "projekte": projekte,
            "kommunikation": kommunikation,
            "offene_erinnerungen": erinnerungen,
        }

    async def aktivitaet_loggen(
        self, bezug_typ: str, bezug_id: str, text: str, betreff: str | None = None
    ) -> dict[str, Any]:
        """Eine Kontaktnotiz/Aktivität als Communication an eine Party hängen —
        erscheint in deren Timeline/Historie."""
        doc = {
            "communication_type": "Communication",
            "reference_doctype": bezug_typ,
            "reference_name": bezug_id,
            "subject": betreff or "Notiz",
            "content": text,
            "sent_or_received": "Sent",
            "communication_date": date.today().isoformat(),
        }
        created = await self._client.create_doc("Communication", doc)
        return {"id": created["name"], "typ": "Communication", "bezug": f"{bezug_typ} {bezug_id}"}

    async def erinnerung_anlegen(
        self,
        bezug_typ: str,
        bezug_id: str,
        text: str,
        faellig_am: str,
        zustaendig: str | None = None,
    ) -> dict[str, Any]:
        """Eine Erinnerung als ERPNext-ToDo mit Fälligkeit anlegen (Push über
        ERPNexts eigenes Notification/Assignment-System)."""
        doc: dict[str, Any] = {
            "description": text,
            "date": faellig_am,
            "reference_type": bezug_typ,
            "reference_name": bezug_id,
        }
        empfaenger = zustaendig or self._settings.default_user
        warnungen: list[str] = []
        if empfaenger:
            doc["allocated_to"] = empfaenger
        else:
            warnungen.append(
                "Kein Zuständiger (zustaendig / ERPNEXT_DEFAULT_USER) — Erinnerung "
                "wird angelegt, aber niemandem zugewiesen (kein Push)."
            )
        created = await self._client.create_doc("ToDo", doc)
        return {
            "id": created["name"],
            "typ": "ToDo",
            "faellig_am": faellig_am,
            "warnungen": warnungen,
        }
