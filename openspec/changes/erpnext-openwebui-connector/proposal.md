## Why

Ein kleines Team (1–2 Personen) soll ERPNext aus dem OpenWebUI-Chat heraus bedienen können — Kontakte anlegen, den kompletten Vertriebszyklus (Angebot → Annahme → Projekt → Zeiterfassung → Rechnung) führen, CRM-Historien pflegen und an Kundenkontakte erinnert werden. ERPNext läuft hosted bei Frappe (kein eigener Code deploybar), OpenWebUI läuft selbst gehostet unter `chat.broetzens.de`. Es fehlt das verbindende Werkzeug dazwischen.

## What Changes

- **Neuer Connector-Dienst** als MCP-Server auf einer Hetzner-VM, der als Man-in-the-Middle zwischen den Chat-Frontends und der ERPNext-REST-API sitzt. Er hält einen ERPNext-Service-Account (API-Key/Secret) und übersetzt natürliche Sprache in REST-Aufrufe.
- **Zwei Türen zum selben Server**: OpenWebUI konsumiert ihn über `mcpo` (OpenAPI-Proxy, da OpenWebUI kein MCP spricht); Claude/Claude Code sprechen MCP direkt an.
- **Auflösungsschicht** (Name → echte ID) als Rückgrat: `finde_kunde`, `finde_angebot`, `suche`, `hole`, `liste`. Verhindert, dass das LLM IDs halluziniert.
- **Vertriebs-Verben**, die die ERPNext-eigenen Übergangsmethoden (`make_sales_order`, `make_sales_invoice`, …) nutzen statt Geschäftslogik nachzubauen.
- **CRM-Verben** plus ein **Push-Mechanismus** für Erinnerungen (ERPNext Notification/ToDo) — bewusst getrennt vom Pull-basierten Chat.
- **Deklaratives Config-Blueprint** (YAML) für die initiale ERPNext-Konfiguration, geordnet und idempotent angewendet — statt fragiler „Erstkonfig per Chat".
- Voller Lese-/Schreibzugriff über den Service-Account; **leichte Bestätigung nur bei `submit`/`cancel`** (Vorgänge, die Geld/Bestand verbuchen).

## Capabilities

### New Capabilities
- `connector-foundation`: MCP-Server-Grundgerüst, ERPNext-Auth/Service-Account, zwei Türen (mcpo + MCP direkt), und die Auflösungsschicht (`suche`, `hole`, `liste`, `finde_*`). Das „Rohr", das alle vier Hops end-to-end beweist.
- `sales-cycle`: Vertriebs-Rücken — `kontakt_anlegen`, `angebot_erstellen`, `angebot_annehmen`, `projekt_anlegen`, `zeit_erfassen`, `rechnung_aus_zeiten`, `zahlung_verbuchen`; nutzt ERPNext-`make_*`-Übergänge; Bestätigung bei submit/cancel.
- `crm-memory`: `kundenhistorie`, `aktivitaet_loggen`, `erinnerung_anlegen` sowie der Push-Mechanismus für proaktive Erinnerungen via ERPNext Notification/ToDo.
- `erpnext-config`: deklaratives Config-Blueprint (idempotentes, reihenfolge-sicheres Anwenden), kleine Config-Tweak-Verben und Aktivierung des Kundenportals.

### Modified Capabilities
<!-- Greenfield-Projekt: keine bestehenden Capabilities. -->

## Impact

- **Neuer Dienst / neue Codebasis**: MCP-Server (Hetzner-VM), plus `mcpo`-Proxy-Deployment für OpenWebUI.
- **ERPNext (hosted bei Frappe)**: unangetastet — nur REST-Zugriff; benötigt einen Service-Account mit API-Key/Secret. Kein Code-Deployment dort.
- **OpenWebUI (`chat.broetzens.de`)**: neuer Tool-Server-Eintrag (zeigt auf `mcpo`).
- **Abhängigkeiten**: ERPNext-REST-API (`/api/resource`, `/api/method`), MCP-SDK, `mcpo`.
- **Betrieb**: ein kleiner Zusatzdienst auf bestehender VM; Secrets-Handling (API-Key/Secret) neu.
- **Sicherheit/Risiko**: Kern-Risiko ist die Auflösung Name→ID; sekundär das Submit/Cancel-Guardrail.
