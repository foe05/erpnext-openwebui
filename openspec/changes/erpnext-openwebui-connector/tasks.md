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

- [x] 3.1 `kundenhistorie` (Belege + Kommunikation + offene Erinnerungen; live verifiziert an HG Mirower Heide)
- [x] 3.2 `aktivitaet_loggen` (Communication an Party; live angelegt)
- [x] 3.3 `erinnerung_anlegen` (ToDo mit Fälligkeit + allocated_to; live angelegt)
- [x] 3.4 Push-Mechanismus: ToDo wird mit Fälligkeit + Zuständigem angelegt; Zustellung übernimmt ERPNexts eigenes Assignment/Notification-System (abhängig von deren Notification-Konfig)
- [x] 3.5 Pull bleibt Pull: der Connector antwortet nur auf Tool-Aufrufe und erzeugt selbst keine Chat-Nachrichten (Push läuft ausschließlich über ERPNext)

## 4. Phase 3 — Konfiguration

- [x] 4.1 Blueprint-Format (YAML, steps mit doctype/key/records = Abhängigkeitsreihenfolge) definiert; `deploy/blueprint.example.yaml`
- [x] 4.2 `config_blueprint_anwenden` (Vorschau/Dry-Run ohne bestaetigen, idempotent via key-Prüfung, klarer Abbruch bei Fehler) — live verifiziert
- [x] 4.3 Selling-Config im Beispiel-Blueprint (Item Group, Activity Types, generisches Service-Item); Steuertemplates bewusst im UI/Kontenrahmen belassen (konten-abhängige Zeilen)
- [x] 4.4 `config_anlegen` (generisches, idempotentes Tweak-Verb; deckt Item Group/Activity Type/Steuerklasse etc. ab)
- [x] 4.5 `portal_zugang_anlegen` (Website-User + Contact mit Customer-Rolle, unter Guardrail) — implementiert, Guardrail live verifiziert
- [ ] 4.6 Ersten realen Config-Blueprint erstellen und anwenden — Mechanismus verifiziert (Wegwerf-Datensatz); realen Inhalt in `deploy/blueprint.example.yaml` nach Bedarf füllen und anwenden

## 5. Absicherung & Betrieb

- [ ] 5.1 `make_*`-Pflichtfelder/Steuer-/Preisregeln an der echten ERPNext-Instanz verifizieren
- [ ] 5.2 Secret-Handling und VM-Zugriff absichern
- [ ] 5.3 Logging/Monitoring für Connector und `mcpo` einrichten
- [ ] 5.4 Deploy-/Rollback-Ablauf je Phase dokumentieren (Dienst stoppen / Tool deaktivieren)
