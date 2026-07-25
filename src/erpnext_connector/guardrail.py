"""Bestätigungs-Guardrail für verbuchende Vorgänge (submit/cancel).

MCP-Werkzeuge sind zustandslos (Request/Response). „Erst bestätigen, dann
verbuchen" lösen wir deshalb zweistufig über einen `bestaetigen`-Parameter:

- erster Aufruf (bestaetigen=False): der Connector führt NICHT aus, sondern gibt
  eine Vorschau zurück ("das würde X verbuchen — erneut mit bestaetigen=true").
  Der Mensch im Chat sieht die Vorschau und sagt "ja".
- zweiter Aufruf (bestaetigen=True): der Vorgang wird ausgeführt.

Anlegen/Ändern im Entwurf läuft ohne Guardrail — nur submit/cancel (bewegen
Geld/Bestand) sind geschützt."""

from __future__ import annotations

from typing import Any

STATUS_BESTAETIGUNG = "bestaetigung_erforderlich"


def bestaetigungs_gate(
    bestaetigen: bool, aktion: str, details: dict[str, Any]
) -> dict[str, Any] | None:
    """Gibt eine Bestätigungs-Antwort zurück, wenn nicht bestätigt wurde,
    sonst None (= ausführen)."""
    if bestaetigen:
        return None
    return {
        "status": STATUS_BESTAETIGUNG,
        "aktion": aktion,
        "details": details,
        "hinweis": (
            f"'{aktion}' verbucht bzw. storniert Daten und bewegt Geld/Bestand. "
            "Zum Ausführen dasselbe Werkzeug erneut mit bestaetigen=true aufrufen."
        ),
    }
