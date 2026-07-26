## Context

Ausgangslage: ERPNext läuft hosted bei Frappe (kein eigener Code deploybar, nur REST-API). OpenWebUI läuft selbst gehostet unter `chat.broetzens.de`. Eine Hetzner-VM steht für einen Zusatzdienst bereit. Nutzer sind 1–2 Personen eines kleinen Teams.

ERPNext bildet den kompletten Vertriebszyklus bereits nativ ab (Lead → Opportunity → Quotation → Sales Order → Project/Timesheet → Sales Invoice → Payment) und liefert die **Übergänge zwischen den Stufen als aufrufbare `make_*`-Methoden** mit (`make_sales_order`, `make_sales_invoice`, …). Der Connector muss daher keine Geschäftslogik nachbauen, sondern übersetzt natürliche Sprache in die richtigen REST-Aufrufe.

```
   chat.broetzens.de        Hetzner-VM                     Frappe Cloud
   ┌──────────────┐   ┌──────────────────────────┐   ┌────────────────┐
   │  OpenWebUI   │──▶│ mcpo  ──MCP──▶  MCP-Server │──▶│    ERPNext     │
   └──────────────┘   │                (Verben +   │REST│  (REST-API)   │
   ┌──────────────┐   │  MCP direkt──▶  Auflösung) │◀──│                │
   │ Claude/Code  │──▶│                hält API-Key│   └────────────────┘
   └──────────────┘   └──────────────────────────┘
```

## Goals / Non-Goals

**Goals:**
- Ein MCP-Server als Man-in-the-Middle, nutzbar über zwei Türen: OpenWebUI (via `mcpo`) und MCP-Clients (direkt).
- Zuverlässige Auflösung Name→echte ID als Rückgrat aller mehrstufigen Flows.
- Kompletter Vertriebszyklus per Chat, gestützt auf ERPNext-eigene `make_*`-Übergänge.
- CRM-Historie/-Aktivitäten und proaktive Erinnerungen über den ERPNext-Push-Kanal.
- Initiale Konfiguration als reviewbares, idempotentes Blueprint (nicht per freiem Chat).

**Non-Goals:**
- Kein Code-Deployment in der hosted ERPNext-Instanz.
- Keine vollautomatische Erstkonfiguration „per Chat reingeredet".
- Kein Nachbau des ERPNext-Kundenportals (nur aktivieren).
- Kein Per-User-Rechtemodell in v1 (ein Service-Account genügt für 1–2 Personen).

## Decisions

**D1 — Protokoll: MCP-Server + `mcpo` (Variante B2), nicht reiner OpenAPI-Dienst (B1).**
Begründung: derselbe Server bedient OpenWebUI *und* Claude/Claude Code. Alternative B1 (reiner FastAPI/OpenAPI-Dienst) wäre einen Prozess einfacher, aber nur von OpenWebUI nutzbar. Der „zwei Türen"-Bonus wiegt die kleine Extra-Komplexität von `mcpo` auf. `mcpo` ist nötig, weil OpenWebUI kein MCP spricht, sondern OpenAPI konsumiert.

**D2 — `make_*`-Übergänge statt eigener Geschäftslogik.**
Quotation→Sales Order und (Sales Order|Timesheet)→Sales Invoice laufen über die whitelisted ERPNext-Methoden. Alternative (Felder selbst mappen und Zieldokument bauen) wäre fehleranfällig und müsste ERPNext-interne Regeln duplizieren.

**D2b — Zeit→Rechnung-Modell: Sammeln je (Projekt, Mitarbeiter), aggregieren je Projekt.**
`zeit_erfassen` hängt Zeilen an ein offenes Draft-Timesheet, das je (Projekt, Mitarbeiter) genau einmal geführt und erst durch die Abrechnung geschlossen wird — die „Periode" ist implizit „seit der letzten Rechnung", ohne Kalenderlogik. `rechnung_aus_zeiten` keyt dagegen auf das **Projekt** und aggregiert alle offenen abrechenbaren Timesheets (auch mehrerer Mitarbeiter) zu **einer** Sales Invoice. Konsequenz: ERPNexts eingebautes `make_sales_invoice` (nimmt genau ein Timesheet) reicht nicht — der Connector baut die Rechnung und befüllt deren `timesheets[]`-Tabelle mit mehreren Quellen selbst. Abrechnungssatz kommt aus Activity Type/Activity Cost; `billing_hours` = geleistete Dauer per Default, überschreibbar. Rechnungszeilen standardmäßig je Tätigkeitsart. Verworfene Alternative „1 TS = 1 Rechnung": scheitert daran, dass ein Timesheet genau einen Mitarbeiter hat und zwei Personen am selben Projekt sonst zwei Rechnungen erzeugen würden — die kombinierte Projekt-Rechnung wurde höher gewichtet als die Einfachheit. Zwei Submit-Punkte (Timesheet, Rechnung), beide unter dem Guardrail (D4).

**D2c — Item-Strategie & Selling-Config (connector-weit).**
Positionen in Angebot und Rechnung folgen einer **Hybrid-Item-Strategie**: bekannte Leistungen werden über `finde_artikel` auf echte Items aufgelöst, Unbekanntes fällt auf generische Service-Items mit freier Beschreibung zurück. Preise kommen aus einer Verkaufspreisliste mit **Override pro Zeile** (für generische Items ist der Override der Normalfall). Steuern über ein **Standard-USt-Template (19 %)** als Default mit Override (7 %, Reverse-Charge/EU). Diese drei Bausteine plus die Activity-Type-Sätze (D2b) bilden ein **gemeinsames Selling-Config-Bündel**, das `angebot_erstellen` und `rechnung_aus_zeiten` teilen und das als Vorbedingung ins Config-Blueprint (Phase 3) gehört — ohne es rechnet Phase 1 formal, aber mit falschen/0-Beträgen. Angebote entstehen als **Draft**; das Submit ist ein bewusster, unter dem Guardrail (D4) stehender Schritt und zugleich Vorbedingung fürs Annehmen (`make_sales_order`). Party-Auflösung spannt bewusst **Lead und Customer** auf, da Angebote auch an Leads gehen. Verworfene Alternativen: reiner Katalog-Zwang (zu viel Pflege für eine Beratung) und rein generisches Item (schwache Auswertung).

**D3 — Auflösungsschicht als eigenständiges Rückgrat.**
Verben arbeiten nur auf echten IDs; `finde_*`/`suche` lösen menschliche Bezeichnungen auf. Bei Mehrdeutigkeit wird zurückgefragt statt geraten. Grund: LLMs halluzinieren Namen/IDs — das ist das Kern-Risiko des gesamten Connectors.

**D4 — Ein Service-Account mit vollem Zugriff; Guardrail nur bei submit/cancel.**
Für 1–2 Personen kein Per-User-Gefummel. Nur verbuchende Vorgänge (submit/cancel — bewegen Geld/Bestand) erfordern eine ausdrückliche Bestätigung. Alternative (Per-User-API-Keys für Audit-Trail) ist Tag-2-Thema.

**D5 — Konfiguration deklarativ (YAML-Blueprint), idempotent und reihenfolge-sicher.**
Erstkonfiguration ist breit und abhängigkeits-sensitiv; freier Chat ist dafür ein schlechtes Medium. Kleine Tweaks bleiben als gezielte Verben zulässig. Alternative (alles per Chat) wurde wegen Fragilität verworfen.

**D6 — Erinnerungen als Push über ERPNext-Notification/ToDo, nicht über den Chat.**
Chat ist Pull (Nutzer fragt zuerst). Erinnerungen sind Push. Der Connector legt ERPNext-Objekte an, deren Zustellung ERPNext selbst übernimmt.

## Risks / Trade-offs

- **Halluzinierte IDs (Kern-Risiko)** → Auflösungsschicht verpflichtend vor jeder Schreib-/Übergangsaktion; bei Mehrdeutigkeit Rückfrage statt Auswahl; jedes Verb gibt die echte ID zurück, die der nächste Schritt trägt.
- **Voller Schreibzugriff + LLM auf einem System of Record** → Bestätigungs-Guardrail bei submit/cancel; anlegen/ändern im Entwurf bleibt frei.
- **Extra-Zwischenschicht `mcpo`** → zusätzlicher Baustein und Fehlerquelle; akzeptiert für den „zwei Türen"-Bonus. Betrieb/Monitoring einplanen.
- **Secret-Handling des Service-Accounts** → API-Key/Secret aus Umgebung/Secret-Store, nie im Code; VM-Zugriff absichern.
- **Frappe-`make_*`-Details** (Pflichtfelder, Steuer-/Preisregeln) können pro Instanz variieren → früh an echter Instanz gegen die konkrete Konfiguration testen.
- **Blueprint-Reihenfolge/Idempotenz** → definierte Abhängigkeitsreihenfolge, Erkennung vorhandener Objekte, klarer Abbruch ohne Halbzustand.
- **Config-Vorbedingungen für die Abrechnung** (verketten Phase 1 mit Phase 3): ohne gepflegte Activity-Type-Sätze erzeugt `zeit_erfassen` 0-€-Zeilen; ohne Standard-Service-/Rechnungs-Item scheitert `rechnung_aus_zeiten`. → `zeit_erfassen` warnt aktiv bei Satz = 0; `rechnung_aus_zeiten` bricht bei fehlendem Item klar ab; beide Vorbedingungen gehören ins Config-Blueprint.

## Migration Plan

Greenfield, kein Bestand zu migrieren. Ausrollen in Phasen (auch die Reihenfolge der Umsetzung):
1. **Phase 0 — Rohr:** MCP-Server-Gerüst, Service-Account-Auth, `mcpo` vor OpenWebUI, Auflösungsschicht + ein Leseverb. Ziel: alle vier Hops (OpenWebUI → mcpo → MCP → ERPNext) einmal end-to-end grün.
2. **Phase 1 — Vertriebs-Rücken:** kontakt_anlegen … rechnung_aus_zeiten (inkl. submit-Guardrail).
3. **Phase 2 — CRM & Erinnerungen:** Historie, Aktivitäten, Push-Erinnerungen.
4. **Phase 3 — Konfiguration:** Blueprint, Tweak-Verben, Portal aktivieren.

Rollback je Phase: Connector-Tool-Eintrag in OpenWebUI deaktivieren bzw. Dienst stoppen; ERPNext bleibt unberührt (nur REST-Zugriff). Kein Schema-/Datenrückbau nötig.

## Open Questions

- Konkrete `make_*`-Pflichtfelder und Steuer-/Preisregeln der Ziel-ERPNext-Instanz (an echter Instanz verifizieren).
- Form der Submit-Bestätigung im Chat (Zwei-Schritt-Aufruf mit Bestätigungs-Token? Klartext-Rückfrage?).
- Zustell-/Anzeigeweg der Push-Erinnerungen (nur ERPNext-intern, E-Mail, oder später zusätzlich in den Chat gespiegelt?).
- Umfang des ersten Config-Blueprints (welche DocTypes gehören in die Erstkonfig?).
