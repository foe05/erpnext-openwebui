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
from .sales import SalesCycle

mcp = FastMCP("erpnext-connector")

_settings = load_settings()
_client = ErpNextClient(_settings)
_resolver = Resolver(_client)
_sales = SalesCycle(_client, _resolver, _settings)


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
    return await _client.get_list(doctype, filters=filter, fields=fields, limit=limit)


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


# -- Vertriebs-Rücken (Phase 1) ------------------------------------------------


@mcp.tool()
async def kontakt_anlegen(
    name: str,
    typ: str = "Lead",
    email: str | None = None,
    telefon: str | None = None,
    firma: str | None = None,
) -> dict[str, Any]:
    """Einen Kontakt anlegen — Lead (Default) oder Customer.

    Args:
        name: Name der Person/Firma.
        typ: "Lead" (Interessent) oder "Customer" (Kunde).
        email, telefon, firma: optionale Kontaktdaten (v. a. für Leads).
    Gibt die echte ID zurück. Für Lead→Kunde später `lead_zu_kunde`.
    """
    return await _sales.kontakt_anlegen(name, typ, email, telefon, firma)


@mcp.tool()
async def lead_zu_kunde(lead_id: str) -> dict[str, Any]:
    """Einen bestehenden Lead in einen Customer überführen (ERPNext make_customer).

    Args:
        lead_id: echte Lead-ID (via finde_party auflösen).
    Gibt die neue Customer-ID zurück.
    """
    return await _sales.lead_zu_kunde(lead_id)


@mcp.tool()
async def angebot_erstellen(
    party_typ: str,
    party_id: str,
    positionen: list[dict[str, Any]],
    gueltig_bis: str | None = None,
    steuer_template: str | None = None,
) -> dict[str, Any]:
    """Ein Angebot (Quotation) als Entwurf erstellen — an Lead oder Kunde.

    Args:
        party_typ: "Lead" oder "Customer".
        party_id: echte ID der Party (via finde_party/finde_kunde auflösen).
        positionen: Liste von {beschreibung, menge, preis?, artikel?}. Bekannte
            Artikel werden aufgelöst; sonst greift das generische Service-Item.
            `preis` überschreibt den Preislisten-Preis.
        gueltig_bis: optionales Datum (YYYY-MM-DD).
        steuer_template: optionales Steuertemplate; ohne Angabe der 19%-Default.
    Legt einen Entwurf an. Zum Rausschicken/Annehmen: `angebot_annehmen`.
    """
    return await _sales.angebot_erstellen(
        party_typ, party_id, positionen, gueltig_bis, steuer_template
    )


@mcp.tool()
async def angebot_annehmen(
    angebot_id: str, bestaetigen: bool = False, lieferdatum: str | None = None
) -> dict[str, Any]:
    """Ein Angebot annehmen: verbucht es (submit) und erzeugt einen Sales Order.

    Args:
        angebot_id: echte Quotation-ID (via finde_angebot auflösen).
        bestaetigen: submit verbucht Daten — erst mit bestaetigen=true ausführen.
        lieferdatum: Lieferdatum des Auftrags (YYYY-MM-DD); ohne Angabe heute.
    Bei einem Angebot an einen Lead: zuerst lead_zu_kunde nötig.
    """
    return await _sales.angebot_annehmen(angebot_id, bestaetigen, lieferdatum)


@mcp.tool()
async def projekt_anlegen(
    sales_order_id: str, projektname: str | None = None
) -> dict[str, Any]:
    """Zu einem Sales Order ein Projekt anlegen (für die Zeiterfassung).

    Args:
        sales_order_id: echte Sales-Order-ID.
        projektname: optionaler Name; sonst aus Kunde + Auftrag generiert.
    """
    return await _sales.projekt_anlegen(sales_order_id, projektname)


@mcp.tool()
async def zeit_erfassen(
    projekt_id: str,
    activity_type: str,
    dauer_stunden: float,
    beschreibung: str,
    mitarbeiter: str | None = None,
    abgerechnete_stunden: float | None = None,
    datum: str | None = None,
) -> dict[str, Any]:
    """Abrechenbare Zeit erfassen — hängt an ein offenes Timesheet je (Projekt, Mitarbeiter).

    Args:
        projekt_id: echte Projekt-ID (via finde_projekt auflösen).
        activity_type: Tätigkeitsart (bestimmt den Abrechnungssatz).
        dauer_stunden: geleistete Stunden.
        beschreibung: was gemacht wurde.
        mitarbeiter: Employee-ID; ohne Angabe der konfigurierte Default.
        abgerechnete_stunden: falls abweichend von geleistet (sonst = dauer_stunden).
        datum: optionales Datum.
    Warnt, wenn der Abrechnungssatz 0 ist. Abrechnen später: `rechnung_aus_zeiten`.
    """
    return await _sales.zeit_erfassen(
        projekt_id, activity_type, dauer_stunden, beschreibung, mitarbeiter,
        abgerechnete_stunden, datum,
    )


@mcp.tool()
async def rechnung_aus_zeiten(
    projekt_id: str, service_item: str | None = None, bestaetigen: bool = False
) -> dict[str, Any]:
    """Alle offenen abrechenbaren Timesheets eines Projekts zu EINER Rechnung aggregieren.

    Args:
        projekt_id: echte Projekt-ID (via finde_projekt auflösen).
        service_item: Rechnungs-/Service-Item; ohne Angabe der konfigurierte Default.
        bestaetigen: submittet die Timesheets — erst mit bestaetigen=true ausführen.
    Aggregiert über mehrere Mitarbeiter, eine Zeile je Tätigkeitsart. Die Rechnung
    entsteht als Entwurf; zum Verbuchen: verbuchen('Sales Invoice', <id>).
    """
    return await _sales.rechnung_aus_zeiten(projekt_id, service_item, bestaetigen)


@mcp.tool()
async def zahlung_verbuchen(
    rechnung_id: str, betrag: float | None = None, bestaetigen: bool = False
) -> dict[str, Any]:
    """Eine Zahlung (Payment Entry) zu einer Rechnung erfassen und verbuchen.

    Args:
        rechnung_id: echte Sales-Invoice-ID.
        betrag: Teilbetrag; ohne Angabe der offene Betrag der Rechnung.
        bestaetigen: verbucht die Zahlung — erst mit bestaetigen=true ausführen.
    """
    return await _sales.zahlung_verbuchen(rechnung_id, betrag, bestaetigen)


@mcp.tool()
async def verbuchen(doctype: str, id: str, bestaetigen: bool = False) -> dict[str, Any]:
    """Ein Dokument verbuchen (submit) — der bewusste zweite Schritt, z. B. für Rechnungen.

    Args:
        doctype: z. B. "Sales Invoice".
        id: echte ID.
        bestaetigen: verbucht Daten — erst mit bestaetigen=true ausführen.
    """
    return await _sales.verbuchen(doctype, id, bestaetigen)


@mcp.tool()
async def stornieren(doctype: str, id: str, bestaetigen: bool = False) -> dict[str, Any]:
    """Ein verbuchtes Dokument stornieren (cancel).

    Args:
        doctype: z. B. "Sales Invoice".
        id: echte ID.
        bestaetigen: storniert Daten — erst mit bestaetigen=true ausführen.
    """
    return await _sales.stornieren(doctype, id, bestaetigen)
