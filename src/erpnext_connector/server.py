"""MCP-Server des ERPNext-Connectors.

Exponiert die Phase-0-Werkzeuge ("das Rohr"): generische Lesewerkzeuge und die
Auflösungsschicht. Der Server spricht MCP (stdio) — Claude/Claude Code sprechen
ihn direkt an, OpenWebUI über den mcpo-Proxy davor.

Die Docstrings der Werkzeuge sind bewusst ausführlich: das LLM liest sie, um zu
entscheiden, wann es welches Werkzeug ruft."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import ErpNextClient
from .config import load_settings
from .resolve import Resolver

mcp = FastMCP("erpnext-connector")

_settings = load_settings()
_client = ErpNextClient(_settings)
_resolver = Resolver(_client)


# -- Generische Lesewerkzeuge --------------------------------------------------


@mcp.tool()
async def hole(doctype: str, id: str) -> dict[str, Any]:
    """Ein einzelnes ERPNext-Dokument anhand seiner echten ID holen.

    Args:
        doctype: DocType-Name, z. B. "Customer", "Quotation", "Sales Invoice".
        id: Die echte ID des Dokuments, z. B. "CUST-0007" oder "QTN-0042".

    Nutze zuvor ein finde_*-Werkzeug, wenn du nur einen Namen, aber keine ID hast.
    """
    return await _client.get_doc(doctype, id)


@mcp.tool()
async def liste(
    doctype: str,
    filter: list | None = None,
    fields: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Eine gefilterte Liste von ERPNext-Dokumenten holen.

    Args:
        doctype: DocType-Name, z. B. "Sales Order".
        filter: ERPNext-Filter als Liste von [feld, operator, wert], z. B.
            [["status", "=", "Open"]]. Ohne Filter kommen die zuletzt geänderten.
        fields: Felder, die zurückgegeben werden sollen. Ohne Angabe liefert
            ERPNext einen Standardsatz.
        limit: Maximale Anzahl Datensätze (Default 20).
    """
    return await _client.get_list(
        doctype, filters=filter, fields=fields, limit=limit, order_by="modified desc"
    )


@mcp.tool()
async def suche(doctype: str, text: str, fields: list[str] | None = None) -> list[dict[str, Any]]:
    """Freitext-Suche über den Namen eines DocTypes (Teilstring, case-insensitive).

    Args:
        doctype: DocType-Name, z. B. "Item".
        text: Suchtext; matcht gegen das Namensfeld (name like %text%).
        fields: Optionale Feldauswahl.

    Für die geführte Auflösung von Kunden/Parties/Artikeln nutze bevorzugt die
    spezialisierten finde_*-Werkzeuge — sie unterscheiden eindeutig/mehrdeutig/keins.
    """
    return await _client.get_list(
        doctype,
        filters=[["name", "like", f"%{text}%"]],
        fields=fields,
        order_by="modified desc",
    )


# -- Auflösungsschicht (Name -> echte ID) --------------------------------------


@mcp.tool()
async def finde_kunde(text: str) -> dict[str, Any]:
    """Einen Kunden (Customer) anhand des Namens zu seiner echten ID auflösen.

    Liefert {status, match|candidates, hinweis}:
    - status "unique": genau ein Treffer in `match` (echte ID in match.name).
    - status "ambiguous": mehrere `candidates` — beim Nutzer rückfragen, nicht raten.
    - status "none": nichts gefunden — nichts anlegen.
    """
    return (await _resolver.finde_kunde(text)).to_dict()


@mcp.tool()
async def finde_party(text: str) -> dict[str, Any]:
    """Eine Party für ein Angebot auflösen — sucht in Leads UND Customers.

    Angebote gehen oft an Leads (vor der Kundwerdung). Jeder Kandidat trägt
    `party_type` ("Lead" oder "Customer") und `id`. Gleiche Statuslogik wie
    finde_kunde (unique/ambiguous/none).
    """
    return (await _resolver.finde_party(text)).to_dict()


@mcp.tool()
async def finde_artikel(text: str) -> dict[str, Any]:
    """Einen Artikel (Item) anhand des Namens zu seinem echten item_code auflösen.

    'none' ist hier ein reguläres Ergebnis: findet sich kein Katalog-Item, kann
    die Hybrid-Item-Strategie auf ein generisches Service-Item mit freier
    Beschreibung zurückfallen (relevant für angebot_erstellen/rechnung_aus_zeiten).
    """
    return (await _resolver.finde_artikel(text)).to_dict()


@mcp.tool()
async def finde_angebot(text: str) -> dict[str, Any]:
    """Ein Angebot (Quotation) über den Kundennamen zu seiner echten ID auflösen.

    Nötig, bevor ein Angebot angenommen wird (angebot_annehmen braucht die echte
    QTN-ID). unique/ambiguous/none wie bei finde_kunde.
    """
    return (await _resolver.finde_angebot(text)).to_dict()


@mcp.tool()
async def finde_projekt(text: str) -> dict[str, Any]:
    """Ein Projekt (Project) anhand des Namens zu seiner echten ID auflösen.

    Vorbedingung fürs Abrechnen: rechnung_aus_zeiten keyt auf die Projekt-ID.
    unique/ambiguous/none wie bei finde_kunde.
    """
    return (await _resolver.finde_projekt(text)).to_dict()
