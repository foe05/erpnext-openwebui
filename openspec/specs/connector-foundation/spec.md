# connector-foundation

## Purpose

Grundgerüst des ERPNext-Connectors: ein eigenständiger MCP-Server als Man-in-the-Middle zwischen den Chat-Frontends (OpenWebUI via mcpo, Claude direkt) und der ERPNext-REST-API, plus die Auflösungsschicht, die menschliche Bezeichnungen in echte ERPNext-IDs übersetzt.

## Requirements

### Requirement: MCP-Server als Man-in-the-Middle
Der Connector SHALL als eigenständiger MCP-Server laufen, der ERPNext ausschließlich über dessen REST-API (`/api/resource`, `/api/method`) anspricht und keinen Code in ERPNext deployt.

#### Scenario: Server erreicht ERPNext
- **WHEN** der Connector startet und eine Test-Leseoperation gegen ERPNext ausführt
- **THEN** authentifiziert er sich mit dem hinterlegten Service-Account und erhält eine gültige Antwort von der ERPNext-REST-API

#### Scenario: ERPNext bleibt code-frei
- **WHEN** der Connector eine Aktion ausführt
- **THEN** geschieht dies nur über REST-Aufrufe, ohne dass in der hosted ERPNext-Instanz zusätzlicher Code installiert sein muss

### Requirement: Zwei Türen zum selben Server
Der Connector SHALL sowohl von OpenWebUI (über einen `mcpo`-OpenAPI-Proxy) als auch von MCP-Clients (Claude/Claude Code, direkt) nutzbar sein, wobei beide Türen dieselbe Werkzeug-Oberfläche bedienen.

#### Scenario: Zugriff über OpenWebUI
- **WHEN** OpenWebUI über den `mcpo`-Proxy ein Werkzeug aufruft
- **THEN** wird der Aufruf an den MCP-Server übersetzt und liefert dasselbe Ergebnis wie ein direkter MCP-Aufruf

#### Scenario: Zugriff direkt über MCP
- **WHEN** ein MCP-Client den Server direkt anspricht
- **THEN** stehen dieselben Werkzeuge ohne `mcpo`-Zwischenschicht zur Verfügung

### Requirement: Service-Account-Authentifizierung
Der Connector SHALL einen einzigen ERPNext-Service-Account (API-Key/Secret) halten, dessen Credentials nicht im Klartext im Code liegen.

#### Scenario: Credentials aus sicherer Quelle
- **WHEN** der Connector Credentials benötigt
- **THEN** liest er API-Key/Secret aus Umgebung/Secret-Store statt aus fest kodiertem Quelltext

### Requirement: Auflösung Name zu ID
Der Connector SHALL Werkzeuge bereitstellen, die menschliche Bezeichnungen in echte ERPNext-Dokument-IDs auflösen, damit Folgeaktionen nie auf geratenen IDs arbeiten.

#### Scenario: Eindeutiger Treffer
- **WHEN** `finde_kunde("Acme")` aufgerufen wird und genau ein passender Kunde existiert
- **THEN** liefert das Werkzeug dessen echte ID (z. B. `CUST-0007`) zurück

#### Scenario: Mehrdeutiger Treffer
- **WHEN** eine Auflösung mehrere plausible Kandidaten findet
- **THEN** liefert das Werkzeug die Kandidatenliste zur Rückfrage zurück, statt selbst einen zu wählen

#### Scenario: Kein Treffer
- **WHEN** eine Auflösung keinen passenden Datensatz findet
- **THEN** meldet das Werkzeug „nicht gefunden" und legt nichts an

#### Scenario: Party-Auflösung über Lead und Customer
- **WHEN** eine Party für ein Angebot aufgelöst werden soll (`finde_party`/`finde_kontakt`)
- **THEN** durchsucht das Werkzeug sowohl Leads als auch Customers und liefert Treffer mit Angabe des Party-Typs (Lead oder Customer) zurück

#### Scenario: Artikel-Auflösung
- **WHEN** `finde_artikel("Beratung")` aufgerufen wird und ein passendes Item existiert
- **THEN** liefert das Werkzeug dessen echten `item_code` zurück; existiert keines, meldet es „nicht gefunden", damit die Hybrid-Item-Strategie auf ein generisches Service-Item zurückfallen kann

### Requirement: Generische Lesewerkzeuge
Der Connector SHALL generische Werkzeuge `suche`, `hole` und `liste` bereitstellen, um beliebige DocTypes lesend abzufragen.

#### Scenario: Einzeldokument holen
- **WHEN** `hole(doctype, id)` mit einer gültigen ID aufgerufen wird
- **THEN** liefert das Werkzeug die Felder dieses Dokuments zurück

#### Scenario: Gefilterte Liste
- **WHEN** `liste(doctype, filter)` aufgerufen wird
- **THEN** liefert das Werkzeug die passenden Datensätze anhand der ERPNext-Filter zurück
