## 1. Phase 0 — Das Rohr (Fundament & Auflösung)

- [x] 1.1 ERPNext-Service-Account (API-Key/Secret) anlegen und Rechte prüfen — Anleitung in README (deine ERPNext-Instanz)
- [x] 1.2 MCP-Server-Grundgerüst aufsetzen (Projektstruktur, Abhängigkeiten, MCP-SDK)
- [x] 1.3 ERPNext-REST-Client mit Auth aus Umgebung/Secret-Store (kein Klartext im Code)
- [x] 1.4 Generische Lesewerkzeuge implementieren: `hole(doctype, id)`, `liste(doctype, filter)`, `suche(doctype, text)`
- [x] 1.5 Auflösungswerkzeuge implementieren: `finde_kunde`, `finde_angebot`, `finde_party` (Lead+Customer), `finde_artikel` (eindeutig/mehrdeutig/kein Treffer sauber unterscheiden)
- [x] 1.6 `mcpo`-Proxy vor OpenWebUI deployen und Tool-Server in OpenWebUI registrieren — läuft als systemd-Dienst hinter NPM (tools.broetzens.de), ufw-Freigabe für Docker-Subnetze
- [x] 1.7 End-to-end-Nachweis: `finde_kunde("...")` über OpenWebUI → mcpo → MCP → ERPNext grün
- [ ] 1.8 Direkter MCP-Zugriff (Claude/Claude Code) gegen denselben Server verifizieren — offen (optional)

## 2. Phase 1 — Vertriebs-Rücken

- [x] 2.1 `kontakt_anlegen` (Lead anlegen; Lead→Customer konvertieren via `lead_zu_kunde`)
- [x] 2.2 `angebot_erstellen`: Party Lead/Customer, Hybrid-Item (finde_artikel + generischer Fallback), Preis aus Preisliste mit Override, 19%-Steuer-Default; Draft anlegen, Submit unter Guardrail
- [x] 2.3 `angebot_annehmen` via `make_sales_order` → Sales-Order-ID
- [x] 2.4 `projekt_anlegen` aus Sales Order (Project + Auftrag-Verknüpfung)
- [x] 2.5 `finde_projekt` für die Projekt-Auflösung ergänzen (Vorbedingung für 2.7) — bereits in Phase 0 (resolve.py)
- [x] 2.6 `zeit_erfassen`: an offenes Draft-TS je (Projekt, Mitarbeiter) anhängen; `billing_hours`-Override; Warnung bei Satz = 0
- [x] 2.7 `rechnung_aus_zeiten`: alle offenen abrechenbaren TS eines Projekts sammeln, submitten und zu EINER Sales Invoice aggregieren (`timesheets[]` selbst befüllen, Zeile je Tätigkeitsart)
- [x] 2.8 Submit/Cancel-Bestätigungs-Guardrail implementieren (`guardrail.py`, `bestaetigen`-Parameter; auch `verbuchen`/`stornieren`)
- [x] 2.9 `zahlung_verbuchen` (Payment Entry zu Invoice, Submit gemäß Guardrail)
- [x] 2.10 Gesamten Flow Kontakt→Angebot→Annahme→Projekt→Zeit→Rechnung end-to-end live getestet (Kontakt, Angebot ANG26-00002 → Auftrag SAL-ORD-2026-00002 → Projekt → Zeit 160€ → Rechnung RE26-00004). Offen nur: ERPNext-Steuerkonfig (Item Tax Template), kein Connector-Thema

## 3. Phase 2 — CRM & Erinnerungen

- [ ] 3.1 `kundenhistorie` (Kommunikation/Aktivitäten + verknüpfte Belege zusammenführen)
- [ ] 3.2 `aktivitaet_loggen` (Kontaktnotiz an Party, erscheint in Historie)
- [ ] 3.3 `erinnerung_anlegen` (ToDo/Notification mit Fälligkeit)
- [ ] 3.4 Push-Zustellung fälliger Erinnerungen über ERPNext-Notification/ToDo verifizieren
- [ ] 3.5 Prüfen, dass der Connector ohne Nutzerfrage keine Chat-Nachrichten erzeugt (Pull bleibt Pull)

## 4. Phase 3 — Konfiguration

- [ ] 4.1 Blueprint-Format (YAML) definieren inkl. Abhängigkeitsreihenfolge
- [ ] 4.2 `config_blueprint_anwenden` implementieren (idempotent, reihenfolge-sicher, klarer Abbruch bei Fehler)
- [ ] 4.3 Selling-Config-Bündel ins Blueprint aufnehmen: generische Service-Items, Verkaufspreisliste + Item Prices, Steuertemplates (19 % Default, 7 %, Reverse-Charge/EU), Activity-Type-Sätze
- [ ] 4.4 Kleine Tweak-Verben (z. B. `item_gruppe_anlegen`, `steuerklasse_anlegen`)
- [ ] 4.5 Kundenportal-Aktivierung (ERPNext-Einstellungen/Rollen setzen)
- [ ] 4.6 Ersten realen Config-Blueprint gegen die Ziel-Instanz erstellen und anwenden

## 5. Absicherung & Betrieb

- [ ] 5.1 `make_*`-Pflichtfelder/Steuer-/Preisregeln an der echten ERPNext-Instanz verifizieren
- [ ] 5.2 Secret-Handling und VM-Zugriff absichern
- [ ] 5.3 Logging/Monitoring für Connector und `mcpo` einrichten
- [ ] 5.4 Deploy-/Rollback-Ablauf je Phase dokumentieren (Dienst stoppen / Tool deaktivieren)
