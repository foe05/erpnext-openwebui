"""Phase 1 — der Vertriebs-Rücken.

Verben entlang der ERPNext-Kette Kontakt → Angebot → Annahme → Projekt → Zeit →
Rechnung → Zahlung. Übergänge nutzen ERPNext-eigene Methoden (make_sales_order,
make_sales_invoice, get_payment_entry) statt eigener Geschäftslogik.

Alles arbeitet auf echten IDs (Auflösung geschieht vorgelagert). Verbuchende
Schritte (submit/cancel) laufen über den Bestätigungs-Guardrail.

Hinweis: Feldnamen/Mapper-Methoden können je ERPNext-Version/-Konfiguration
leicht abweichen — an der echten Instanz verifizieren (Task 5.1)."""

from __future__ import annotations

from datetime import date
from typing import Any

from .client import ErpNextClient, ErpNextError
from .config import Settings
from .guardrail import bestaetigungs_gate
from .resolve import Resolver


def aggregiere_timesheet_positionen(
    timesheets: list[dict[str, Any]], service_item: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Bündelt abrechenbare Timesheet-Zeilen zu Rechnungspositionen — eine je
    Tätigkeitsart — und erzeugt die timesheets[]-Verknüpfungen für die Rechnung.

    Reine Funktion ohne I/O, damit testbar. Liefert (items, timesheet_links, summe)."""
    nach_aktivitaet: dict[str, tuple[float, float]] = {}
    links: list[dict[str, Any]] = []
    total = 0.0
    for ts in timesheets:
        ts_amount = 0.0
        for row in ts.get("time_logs", []):
            if not row.get("is_billable"):
                continue
            amount = float(row.get("billing_amount") or 0)
            hours = float(row.get("billing_hours") or 0)
            akt = row.get("activity_type") or "Leistung"
            h, a = nach_aktivitaet.get(akt, (0.0, 0.0))
            nach_aktivitaet[akt] = (h + hours, a + amount)
            ts_amount += amount
            total += amount
        links.append(
            {
                "time_sheet": ts.get("name"),
                "billing_hours": ts.get("total_billable_hours"),
                "billing_amount": ts.get("total_billable_amount") or ts_amount,
            }
        )
    items: list[dict[str, Any]] = []
    for akt, (hours, amount) in nach_aktivitaet.items():
        rate = (amount / hours) if hours else 0
        items.append(
            {"item_code": service_item, "qty": hours, "rate": rate, "description": akt}
        )
    return items, links, round(total, 2)


class SalesCycle:
    def __init__(self, client: ErpNextClient, resolver: Resolver, settings: Settings):
        self._client = client
        self._resolver = resolver
        self._settings = settings

    # -- Kontakte --------------------------------------------------------------

    async def kontakt_anlegen(
        self,
        name: str,
        typ: str = "Lead",
        email: str | None = None,
        telefon: str | None = None,
        firma: str | None = None,
    ) -> dict[str, Any]:
        if typ == "Customer":
            doc: dict[str, Any] = {"customer_name": name}
            created = await self._client.create_doc("Customer", doc)
        else:
            doc = {"lead_name": name}
            if firma:
                doc["company_name"] = firma
            if email:
                doc["email_id"] = email
            if telefon:
                doc["mobile_no"] = telefon
            created = await self._client.create_doc("Lead", doc)
            typ = "Lead"
        return {"id": created["name"], "typ": typ}

    async def lead_zu_kunde(self, lead_id: str) -> dict[str, Any]:
        kunde = await self._client.call_method(
            "erpnext.crm.doctype.lead.lead.make_customer", params={"source_name": lead_id}
        )
        created = await self._client.create_doc("Customer", kunde)
        return {"id": created["name"], "typ": "Customer", "aus_lead": lead_id}

    # -- Angebot ---------------------------------------------------------------

    async def _baue_angebotsposition(
        self, pos: dict[str, Any]
    ) -> tuple[dict[str, Any], str | None]:
        row: dict[str, Any] = {
            "qty": pos.get("menge", 1),
            "description": pos.get("beschreibung", ""),
        }
        warn: str | None = None
        suchbegriff = pos.get("artikel") or pos.get("beschreibung")
        treffer = await self._resolver.finde_artikel(suchbegriff) if suchbegriff else None
        if treffer and treffer.status == "unique" and treffer.match:
            row["item_code"] = treffer.match.get("item_code") or treffer.match.get("name")
        else:
            # Hybrid-Fallback: generisches Service-Item + freie Beschreibung
            if not self._settings.generic_service_item:
                warn = (
                    f"Position '{pos.get('beschreibung')}': kein Artikel gefunden und kein "
                    "generisches Service-Item konfiguriert (ERPNEXT_GENERIC_SERVICE_ITEM)."
                )
            row["item_code"] = self._settings.generic_service_item
            row["item_name"] = pos.get("beschreibung", "")
        if pos.get("preis") is not None:
            row["rate"] = pos["preis"]  # Override; sonst Preis aus Preisliste
        return row, warn

    async def angebot_erstellen(
        self,
        party_typ: str,
        party_id: str,
        positionen: list[dict[str, Any]],
        gueltig_bis: str | None = None,
        steuer_template: str | None = None,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        warnungen: list[str] = []
        for pos in positionen:
            row, warn = await self._baue_angebotsposition(pos)
            items.append(row)
            if warn:
                warnungen.append(warn)
        doc: dict[str, Any] = {
            "quotation_to": party_typ,
            "party_name": party_id,
            "items": items,
        }
        tax = steuer_template or self._settings.default_tax_template
        if tax:
            doc["taxes_and_charges"] = tax
        else:
            warnungen.append(
                "Kein Steuertemplate — Angebot ohne USt gerechnet (ERPNEXT_DEFAULT_TAX_TEMPLATE)."
            )
        if self._settings.default_price_list:
            doc["selling_price_list"] = self._settings.default_price_list
        if gueltig_bis:
            doc["valid_till"] = gueltig_bis
        created = await self._client.create_doc("Quotation", doc)
        return {
            "id": created["name"],
            "grand_total": created.get("grand_total"),
            "status": "entwurf",
            "warnungen": warnungen,
        }

    async def angebot_annehmen(
        self, angebot_id: str, bestaetigen: bool = False, lieferdatum: str | None = None
    ) -> dict[str, Any]:
        q = await self._client.get_doc("Quotation", angebot_id)
        schritte: list[str] = []
        if q.get("quotation_to") == "Lead":
            return {
                "status": "aktion_erforderlich",
                "hinweis": (
                    f"Angebot geht an einen Lead ({q.get('party_name')}). Für einen Auftrag "
                    "zuerst lead_zu_kunde aufrufen und das Angebot an den Kunden erstellen."
                ),
            }
        if q.get("docstatus", 0) == 0:
            gate = bestaetigungs_gate(
                bestaetigen,
                f"Angebot {angebot_id} verbuchen (submit) und Auftrag erzeugen",
                {"angebot": angebot_id, "kunde": q.get("party_name")},
            )
            if gate:
                return gate
            await self._client.submit_doc("Quotation", angebot_id)
            schritte.append("Angebot submitted")
        so_doc = await self._client.call_method(
            "erpnext.selling.doctype.quotation.quotation.make_sales_order",
            params={"source_name": angebot_id},
        )
        if not so_doc:
            return {
                "status": "fehler",
                "hinweis": f"make_sales_order lieferte kein Dokument für {angebot_id}.",
            }
        # ERPNext verlangt ein Lieferdatum (Kopf + Positionen); Mapper gibt keins mit.
        liefer = lieferdatum or date.today().isoformat()
        so_doc.setdefault("delivery_date", liefer)
        for pos in so_doc.get("items", []):
            pos.setdefault("delivery_date", liefer)
        created = await self._client.create_doc("Sales Order", so_doc)
        schritte.append("Auftrag erzeugt")
        return {"id": created["name"], "typ": "Sales Order", "schritte": schritte}

    # -- Projekt ---------------------------------------------------------------

    async def projekt_anlegen(
        self, sales_order_id: str, projektname: str | None = None
    ) -> dict[str, Any]:
        so = await self._client.get_doc("Sales Order", sales_order_id)
        doc = {
            "project_name": projektname or f"{so.get('customer', 'Projekt')} - {sales_order_id}",
            "customer": so.get("customer"),
        }
        created = await self._client.create_doc("Project", doc)
        verknuepft = False
        try:
            await self._client.update_doc(
                "Sales Order", sales_order_id, {"project": created["name"]}
            )
            verknuepft = True
        except ErpNextError:
            pass  # Verknüpfung best effort (z. B. bei submittetem Auftrag)
        return {
            "id": created["name"],
            "typ": "Project",
            "kunde": so.get("customer"),
            "auftrag_verknuepft": verknuepft,
        }

    # -- Zeit ------------------------------------------------------------------

    async def zeit_erfassen(
        self,
        projekt_id: str,
        activity_type: str,
        dauer_stunden: float,
        beschreibung: str,
        mitarbeiter: str | None = None,
        abgerechnete_stunden: float | None = None,
        datum: str | None = None,
    ) -> dict[str, Any]:
        emp = mitarbeiter or self._settings.default_employee
        warnungen: list[str] = []
        if not emp:
            warnungen.append(
                "Kein Mitarbeiter angegeben und ERPNEXT_DEFAULT_EMPLOYEE nicht gesetzt."
            )
        billing_hours = (
            abgerechnete_stunden if abgerechnete_stunden is not None else dauer_stunden
        )
        zeile: dict[str, Any] = {
            "activity_type": activity_type,
            "hours": dauer_stunden,
            "billing_hours": billing_hours,
            "is_billable": 1,
            "project": projekt_id,
            "description": beschreibung,
        }
        # offenes Draft-Timesheet für (Projekt, Mitarbeiter) suchen
        filters: list[list[Any]] = [["parent_project", "=", projekt_id], ["docstatus", "=", 0]]
        if emp:
            filters.append(["employee", "=", emp])
        offene = await self._client.get_list(
            "Timesheet", filters=filters, fields=["name"], limit=1
        )
        if offene:
            ts_name = offene[0]["name"]
            ts = await self._client.get_doc("Timesheet", ts_name)
            logs = ts.get("time_logs", []) + [zeile]
            ts_result = await self._client.update_doc(
                "Timesheet", ts_name, {"time_logs": logs}
            )
        else:
            doc: dict[str, Any] = {"parent_project": projekt_id, "time_logs": [zeile]}
            if emp:
                doc["employee"] = emp
            ts_result = await self._client.create_doc("Timesheet", doc)
            ts_name = ts_result["name"]
        zeilen = ts_result.get("time_logs", [])
        letzte = zeilen[-1] if zeilen else {}
        if not letzte.get("billing_rate"):
            warnungen.append(
                f"Abrechnungssatz für Tätigkeit '{activity_type}' ist 0 — Betrag wäre 0 €. "
                "Activity Type / Activity Cost pflegen."
            )
        return {
            "id": ts_name,
            "abrechenbar_gesamt": ts_result.get("total_billable_amount"),
            "warnungen": warnungen,
        }

    # -- Rechnung & Zahlung ----------------------------------------------------

    async def rechnung_aus_zeiten(
        self, projekt_id: str, service_item: str | None = None, bestaetigen: bool = False
    ) -> dict[str, Any]:
        proj = await self._client.get_doc("Project", projekt_id)
        kunde = proj.get("customer")
        item = service_item or self._settings.generic_service_item
        if not kunde:
            return {"status": "fehler", "hinweis": f"Projekt {projekt_id} hat keinen Kunden."}
        if not item:
            return {
                "status": "fehler",
                "hinweis": (
                    "Kein Rechnungs-/Service-Item (service_item bzw. "
                    "ERPNEXT_GENERIC_SERVICE_ITEM) — Rechnung kann keine Position tragen."
                ),
            }
        ts_liste = await self._client.get_list(
            "Timesheet",
            filters=[["parent_project", "=", projekt_id], ["total_billable_amount", ">", 0]],
            fields=["name", "docstatus"],
            limit=100,
        )
        if not ts_liste:
            return {
                "status": "leer",
                "hinweis": f"Keine abrechenbaren Timesheets für Projekt {projekt_id}.",
            }
        voll = [await self._client.get_doc("Timesheet", t["name"]) for t in ts_liste]
        items, links, total = aggregiere_timesheet_positionen(voll, item)
        if total <= 0:
            return {
                "status": "leer",
                "hinweis": "Abrechenbare Summe ist 0 — evtl. fehlen Activity-Type-Sätze.",
            }
        gate = bestaetigungs_gate(
            bestaetigen,
            f"{len(voll)} Timesheet(s) verbuchen und Rechnung über {total} erzeugen",
            {
                "projekt": projekt_id,
                "kunde": kunde,
                "timesheets": [t["name"] for t in ts_liste],
                "summe": total,
            },
        )
        if gate:
            return gate
        for t in ts_liste:
            if t.get("docstatus", 0) == 0:
                await self._client.submit_doc("Timesheet", t["name"])
        doc: dict[str, Any] = {
            "customer": kunde,
            "items": items,
            "timesheets": links,
            "project": projekt_id,
        }
        if self._settings.default_tax_template:
            doc["taxes_and_charges"] = self._settings.default_tax_template
        created = await self._client.create_doc("Sales Invoice", doc)
        return {
            "id": created["name"],
            "typ": "Sales Invoice",
            "summe": created.get("grand_total"),
            "status": "entwurf",
            "hinweis": "Rechnung als Entwurf angelegt. Zum Verbuchen: verbuchen('Sales Invoice', <id>).",
        }

    async def zahlung_verbuchen(
        self, rechnung_id: str, betrag: float | None = None, bestaetigen: bool = False
    ) -> dict[str, Any]:
        inv = await self._client.get_doc("Sales Invoice", rechnung_id)
        kunde = inv.get("customer")
        zu_zahlen = betrag if betrag is not None else (
            inv.get("outstanding_amount") or inv.get("grand_total")
        )
        gate = bestaetigungs_gate(
            bestaetigen,
            f"Zahlung {zu_zahlen} zu Rechnung {rechnung_id} verbuchen",
            {"rechnung": rechnung_id, "kunde": kunde, "betrag": zu_zahlen},
        )
        if gate:
            return gate
        pe = await self._client.call_method(
            "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
            params={"dt": "Sales Invoice", "dn": rechnung_id},
        )
        if betrag is not None:
            pe["paid_amount"] = betrag
            pe["received_amount"] = betrag
        created = await self._client.create_doc("Payment Entry", pe)
        await self._client.submit_doc("Payment Entry", created["name"])
        return {
            "id": created["name"],
            "typ": "Payment Entry",
            "betrag": zu_zahlen,
            "status": "verbucht",
        }

    # -- Generisches Verbuchen/Stornieren (zweiter Submit-Punkt) ---------------

    async def verbuchen(
        self, doctype: str, id: str, bestaetigen: bool = False
    ) -> dict[str, Any]:
        gate = bestaetigungs_gate(
            bestaetigen, f"{doctype} {id} verbuchen (submit)", {"doctype": doctype, "id": id}
        )
        if gate:
            return gate
        await self._client.submit_doc(doctype, id)
        return {"id": id, "typ": doctype, "status": "verbucht"}

    async def stornieren(
        self, doctype: str, id: str, bestaetigen: bool = False
    ) -> dict[str, Any]:
        gate = bestaetigungs_gate(
            bestaetigen, f"{doctype} {id} stornieren (cancel)", {"doctype": doctype, "id": id}
        )
        if gate:
            return gate
        await self._client.cancel_doc(doctype, id)
        return {"id": id, "typ": doctype, "status": "storniert"}
