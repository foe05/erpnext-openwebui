# erpnext-openwebui

MCP-Connector, um ERPNext (REST-API) aus dem OpenWebUI-Chat — und aus Claude/Claude Code — zu bedienen.

Der Connector läuft als eigenständiger MCP-Server (Man-in-the-Middle) auf einer VM. Er hält einen ERPNext-Service-Account und übersetzt Werkzeug-Aufrufe in REST-Aufrufe. ERPNext selbst bleibt unangetastet (nur REST).

```
 OpenWebUI ──▶ mcpo ──MCP──▶ erpnext-connector ──REST──▶ ERPNext (Frappe Cloud)
 Claude/Code ─────────MCP───▶ (derselbe Server)
```

Planung/Spezifikation liegen unter `openspec/changes/erpnext-openwebui-connector/`.

## Status

**Phase 0 (das Rohr)** — REST-Client, Auflösungsschicht, generische Lesewerkzeuge. Live verifiziert.

**Phase 1 (Vertriebs-Rücken)** — Code fertig, End-to-End-Verifikation an der echten Instanz offen (Feldnamen/Mapper prüfen).

Werkzeuge:
- Lesen/Auflösen: `hole`, `liste`, `suche`, `finde_kunde`, `finde_party`, `finde_artikel`, `finde_angebot`, `finde_projekt`
- Vertrieb: `kontakt_anlegen`, `lead_zu_kunde`, `angebot_erstellen`, `angebot_annehmen`, `projekt_anlegen`, `zeit_erfassen`, `rechnung_aus_zeiten`, `zahlung_verbuchen`, `verbuchen`, `stornieren`

Verbuchende Verben (submit/cancel) verlangen `bestaetigen=true` — erster Aufruf liefert eine Vorschau.
Für korrekte Beträge in Phase 1 die Selling-Config in `.env` setzen (Service-Item, Steuertemplate, Preisliste, Employee).

## Installation (auf der VM)

Debian/Ubuntu schützt das System-Python (PEP 668) — ein direktes `pip install`
schlägt mit `externally-managed-environment` fehl. Deshalb immer in ein venv
installieren. Frische Debian-VMs brauchen dafür einmalig `python3-venv`/`-full`,
sonst hat das venv kein eigenes `pip`:

```bash
sudo apt update
sudo apt install -y python3-venv python3-full   # liefert ensurepip/pip fürs venv

python3 -m venv .venv
source .venv/bin/activate                       # ab hier ist pip lokal im venv

pip install -e .          # Connector + Abhängigkeiten
cp .env.example .env      # dann echte Werte eintragen (siehe unten)
```

Hinweis: `pip install --break-system-packages` vermeiden — das schreibt ins
System-Python und ist genau das, wovor PEP 668 warnt.

## Konfiguration — ERPNext-Service-Account (Task 1.1)

Diesen Schritt musst du in **deiner** ERPNext-Instanz ausführen:

1. In ERPNext einen Service-User anlegen (oder einen bestehenden nutzen) mit den nötigen Rollen (voller Lese-/Schreibzugriff für den geplanten Umfang).
2. Beim User unter **API Access → Generate Keys** ein API-Key/Secret erzeugen.
3. In `.env` eintragen:
   ```
   ERPNEXT_URL=https://deine-instanz.frappe.cloud
   ERPNEXT_API_KEY=...
   ERPNEXT_API_SECRET=...
   ```
   `.env` wird nicht committet (siehe `.gitignore`). In Produktion die Werte als echte Umgebungsvariablen/Secret-Store setzen.

## Betrieb

**Direkt als MCP-Server** (für Claude/Claude Code):
```bash
python -m erpnext_connector          # stdio
```

**Hinter mcpo** (für OpenWebUI, Task 1.6):
```bash
source .venv/bin/activate                  # dasselbe venv wie oben
pip install mcpo                           # Proxy ins gleiche venv
export ERPNEXT_API_KEY=... ERPNEXT_API_SECRET=...
mcpo --config deploy/mcpo.config.json --port 8000
```
mcpo aus dem aktivierten venv starten: der von mcpo gestartete `python`-Subprozess
(`command: python` in der Config) erbt dann das venv und findet den Connector.
Dann in OpenWebUI unter **Settings → Tools** einen OpenAPI-Tool-Server auf `http://<vm>:8000/erpnext` registrieren. (In Produktion hinter TLS/Reverse-Proxy stellen.)

## Verifikation (Tasks 1.7 / 1.8)

- **1.7 (über OpenWebUI):** Im Chat `finde_kunde` mit einem echten Kundennamen aufrufen — es muss die reale ID (z. B. `CUST-0007`) zurückkommen. Das beweist alle vier Hops OpenWebUI → mcpo → MCP → ERPNext.
- **1.8 (direkt über MCP):** Den Server in Claude/Claude Code als MCP-Server registrieren und dasselbe `finde_kunde` aufrufen.

## Tests

```bash
pip install -e ".[dev]"
pytest
```
Die Tests laufen gegen ein gemocktes ERPNext (kein Live-Zugang nötig) und prüfen die Auflösungslogik (eindeutig/mehrdeutig/kein Treffer), `hole` und die Fehlerbehandlung.
