"""Phase 3 — Konfiguration.

Deklaratives Config-Blueprint (YAML): reihenfolge-sicher, idempotent, mit
Dry-Run/Vorschau und klarem Abbruch bei Fehler. Plus generisches Tweak-Verb und
Kundenportal-Zugang.

Blueprint-Format:
    steps:
      - doctype: Item Group
        key: item_group_name        # Feld(er) zur Idempotenz-Prüfung
        records:
          - item_group_name: Dienstleistungen
            is_group: 0

Die Reihenfolge der steps ist die Abhängigkeitsreihenfolge."""

from __future__ import annotations

import os
from typing import Any

import yaml

from .client import ErpNextClient, ErpNextError
from .config import Settings
from .guardrail import bestaetigungs_gate


class ConfigAdmin:
    def __init__(self, client: ErpNextClient, settings: Settings):
        self._client = client
        self._settings = settings

    @staticmethod
    def lade_blueprint(pfad: str) -> dict[str, Any]:
        with open(pfad, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    async def _existiert(self, doctype: str, keys: list[str], rec: dict[str, Any]) -> str | None:
        filters = [[k, "=", rec[k]] for k in keys if k in rec]
        if not filters:
            return None
        try:
            rows = await self._client.get_list(doctype, filters=filters, fields=["name"], limit=1)
        except ErpNextError:
            return None
        return rows[0]["name"] if rows else None

    async def blueprint_anwenden(
        self,
        blueprint: dict[str, Any] | None = None,
        pfad: str | None = None,
        bestaetigen: bool = False,
    ) -> dict[str, Any]:
        if blueprint is None:
            if not pfad:
                return {"status": "fehler", "hinweis": "Weder blueprint noch pfad angegeben."}
            if not os.path.exists(pfad):
                return {"status": "fehler", "hinweis": f"Blueprint-Datei nicht gefunden: {pfad}"}
            blueprint = self.lade_blueprint(pfad)
        steps = blueprint.get("steps", [])
        if not steps:
            return {"status": "leer", "hinweis": "Blueprint enthält keine steps."}

        # Vorschau/Dry-Run: prüfen, was angelegt vs. übersprungen würde
        plan: list[dict[str, Any]] = []
        for step in steps:
            dt = step["doctype"]
            keys = [step["key"]] if isinstance(step["key"], str) else list(step["key"])
            for rec in step.get("records", []):
                vorhanden = await self._existiert(dt, keys, rec)
                plan.append(
                    {
                        "doctype": dt,
                        "schluessel": {k: rec.get(k) for k in keys},
                        "aktion": "vorhanden" if vorhanden else "anlegen",
                    }
                )
        if not bestaetigen:
            anzulegen = sum(1 for p in plan if p["aktion"] == "anlegen")
            return {
                "status": "vorschau",
                "anzulegen": anzulegen,
                "vorhanden": len(plan) - anzulegen,
                "plan": plan,
                "hinweis": "Zum Anwenden erneut mit bestaetigen=true aufrufen.",
            }

        # Anwenden: in Reihenfolge, idempotent, Abbruch ohne Halbzustand bei Fehler
        ergebnis: list[dict[str, Any]] = []
        for step in steps:
            dt = step["doctype"]
            keys = [step["key"]] if isinstance(step["key"], str) else list(step["key"])
            for rec in step.get("records", []):
                vorhanden = await self._existiert(dt, keys, rec)
                if vorhanden:
                    ergebnis.append({"doctype": dt, "id": vorhanden, "aktion": "übersprungen"})
                    continue
                try:
                    created = await self._client.create_doc(dt, rec)
                    ergebnis.append({"doctype": dt, "id": created["name"], "aktion": "angelegt"})
                except ErpNextError as e:
                    return {
                        "status": "abgebrochen",
                        "bei": {"doctype": dt, "schluessel": {k: rec.get(k) for k in keys}},
                        "fehler": str(e.detail)[:300],
                        "bisher": ergebnis,
                    }
        return {"status": "fertig", "ergebnis": ergebnis}

    async def config_anlegen(
        self, doctype: str, daten: dict[str, Any], schluessel_feld: str | None = None
    ) -> dict[str, Any]:
        """Ein einzelnes Config-Objekt idempotent anlegen (z. B. Item Group,
        Steuerklasse). schluessel_feld dient der Vorhandensein-Prüfung."""
        if schluessel_feld and schluessel_feld in daten:
            vorhanden = await self._existiert(doctype, [schluessel_feld], daten)
            if vorhanden:
                return {"id": vorhanden, "typ": doctype, "aktion": "vorhanden"}
        created = await self._client.create_doc(doctype, daten)
        return {"id": created["name"], "typ": doctype, "aktion": "angelegt"}

    async def portal_zugang_anlegen(
        self, kunde_id: str, email: str, vorname: str | None = None, bestaetigen: bool = False
    ) -> dict[str, Any]:
        """Einem Kunden Portal-Zugang geben: Website-User mit Customer-Rolle,
        verknüpft über einen Contact. Legt einen echten Login an."""
        gate = bestaetigungs_gate(
            bestaetigen,
            f"Portal-Login für {email} (Kunde {kunde_id}) anlegen",
            {"kunde": kunde_id, "email": email},
        )
        if gate:
            return gate
        # Website-User anlegen (Portal-Nutzer, kein Desk-Zugang)
        user = await self._client.create_doc(
            "User",
            {
                "email": email,
                "first_name": vorname or email.split("@")[0],
                "user_type": "Website User",
                "send_welcome_email": 0,
                "roles": [{"role": "Customer"}],
            },
        )
        # Contact anlegen und mit Kunde + User verknüpfen
        contact = await self._client.create_doc(
            "Contact",
            {
                "first_name": vorname or email.split("@")[0],
                "user": email,
                "email_ids": [{"email_id": email, "is_primary": 1}],
                "links": [{"link_doctype": "Customer", "link_name": kunde_id}],
            },
        )
        return {
            "user": user["name"],
            "contact": contact["name"],
            "kunde": kunde_id,
            "hinweis": "Portal-Login angelegt (kein Welcome-Mail versandt). Passwort-Reset bei Bedarf.",
        }
