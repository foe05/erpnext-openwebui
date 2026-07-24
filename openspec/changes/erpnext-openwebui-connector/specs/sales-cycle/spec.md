## ADDED Requirements

### Requirement: Kontakt anlegen
Der Connector SHALL Werkzeuge bereitstellen, um Leads und Kunden (Contact/Customer) anzulegen und einen Lead in einen Kunden zu überführen.

#### Scenario: Lead anlegen
- **WHEN** `kontakt_anlegen` mit Namen und Kontaktdaten für einen Interessenten aufgerufen wird
- **THEN** legt der Connector einen Lead in ERPNext an und gibt dessen echte ID zurück

#### Scenario: Lead zu Kunde konvertieren
- **WHEN** ein bestehender Lead als Kunde übernommen werden soll
- **THEN** erzeugt der Connector einen Customer aus dem Lead und gibt die Customer-ID zurück

### Requirement: Angebot erstellen
Der Connector SHALL zu einer aufgelösten Party — Lead oder Customer — ein Quotation-Dokument mit Positionen als Entwurf erstellen. Positionen folgen der connector-weiten Hybrid-Item-Strategie, Preise der Preisliste-mit-Override, und ein Standard-Steuertemplate wird als Default gesetzt.

#### Scenario: Angebot an Lead oder Kunde
- **WHEN** `angebot_erstellen` mit einer aufgelösten Party (Lead- oder Customer-ID) und Positionen aufgerufen wird
- **THEN** legt der Connector eine Quotation im Entwurf an, deren `quotation_to`/`party_name` korrekt auf Lead bzw. Customer zeigt, und gibt die echte ID (z. B. `QTN-0042`) samt `grand_total` zurück

#### Scenario: Position mit bekanntem Item
- **WHEN** eine Position auf ein bestehendes Item verweist
- **THEN** löst der Connector es über `finde_artikel` zu einem echten `item_code` auf und übernimmt den Preis aus der Preisliste, sofern nicht überschrieben

#### Scenario: Position ohne bekanntes Item
- **WHEN** eine Position keinem bekannten Item entspricht
- **THEN** verwendet der Connector ein generisches Service-Item mit freier Beschreibung und dem übergebenen Preis (Override), statt die Erstellung abzubrechen

#### Scenario: Steuer-Default und Override
- **WHEN** `angebot_erstellen` ohne explizites Steuertemplate aufgerufen wird
- **THEN** setzt der Connector das Standard-USt-Template (19 %); ein abweichendes Template (z. B. 7 %, Reverse-Charge/EU) wird verwendet, wenn ausdrücklich angegeben

#### Scenario: Party nicht aufgelöst
- **WHEN** `angebot_erstellen` ohne aufgelöste Party-ID aufgerufen wird
- **THEN** verweigert der Connector die Erstellung und fordert zuerst eine Auflösung an

#### Scenario: Angebot rausschicken erfordert Bestätigung
- **WHEN** ein erstelltes Angebot submittet werden soll (Vorbedingung, um es später anzunehmen)
- **THEN** führt der Connector das Submit erst nach ausdrücklicher Bestätigung aus; ohne Bestätigung bleibt das Angebot im Entwurf

### Requirement: Angebot annehmen
Der Connector SHALL die Annahme einer Quotation über die ERPNext-Übergangsmethode `make_sales_order` in einen Sales Order überführen.

#### Scenario: Annahme erzeugt Auftrag
- **WHEN** `angebot_annehmen(QTN-0042)` mit einer echten Quotation-ID aufgerufen wird
- **THEN** ruft der Connector `make_sales_order` auf und gibt die echte Sales-Order-ID (z. B. `SO-0011`) zurück

### Requirement: Projekt aus Auftrag anlegen
Der Connector SHALL zu einem Sales Order ein Project (mit optionalen Tasks) anlegen, das für die Zeiterfassung verwendet werden kann.

#### Scenario: Projekt verknüpft mit Auftrag
- **WHEN** `projekt_anlegen(SO-0011)` aufgerufen wird
- **THEN** legt der Connector ein Project an, das mit dem Auftrag/Kunden verknüpft ist, und gibt die Project-ID zurück

### Requirement: Zeit erfassen
Der Connector SHALL abrechenbare Zeiten als Zeilen an ein offenes Draft-Timesheet anhängen, das je Kombination aus Projekt und Mitarbeiter genau einmal geführt und erst durch die Abrechnung geschlossen wird.

#### Scenario: Erste Buchung öffnet ein Timesheet
- **WHEN** `zeit_erfassen` mit Projekt/Task, Tätigkeitsart, Dauer und Beschreibung aufgerufen wird und für dieses (Projekt, Mitarbeiter) noch kein offenes Timesheet existiert
- **THEN** legt der Connector ein Draft-Timesheet für dieses (Projekt, Mitarbeiter) an, hängt die Zeile mit als abrechenbar markierten Stunden an und gibt Timesheet-ID und laufenden abrechenbaren Betrag zurück

#### Scenario: Weitere Buchung hängt an
- **WHEN** `zeit_erfassen` erneut für dasselbe (Projekt, Mitarbeiter) aufgerufen wird, während ein offenes Draft-Timesheet existiert
- **THEN** hängt der Connector die Zeile an dieses bestehende Timesheet an, statt ein neues anzulegen

#### Scenario: Abgerechnete Dauer weicht von geleisteter ab
- **WHEN** `zeit_erfassen` eine abweichende abgerechnete Dauer erhält (z. B. 3,5 h geleistet, 3,0 h berechnet)
- **THEN** setzt der Connector `billing_hours` auf die abgerechnete Dauer; ohne Angabe gilt abgerechnet = geleistet

#### Scenario: Satz nicht konfiguriert
- **WHEN** die Tätigkeitsart keinen hinterlegten Abrechnungssatz hat und die Zeile damit einen Betrag von 0 ergäbe
- **THEN** warnt der Connector im Ergebnis ausdrücklich vor dem 0-Satz, statt eine stille 0-€-Zeile zu erzeugen

### Requirement: Rechnung aus Zeiten
Der Connector SHALL alle offenen abrechenbaren Timesheets eines Projekts — auch über mehrere Mitarbeiter hinweg — zu genau einer Sales Invoice aggregieren.

#### Scenario: Ein Projekt, mehrere Timesheets, eine Rechnung
- **WHEN** `rechnung_aus_zeiten` mit einer echten Projekt-ID aufgerufen wird und mehrere offene abrechenbare Timesheets (ggf. verschiedener Mitarbeiter) existieren
- **THEN** submittet der Connector diese Timesheets und erzeugt eine einzige Sales Invoice, die deren abrechenbare Stunden aggregiert, und gibt die Invoice-ID und den Gesamtbetrag zurück

#### Scenario: Rechnungszeilen je Tätigkeit
- **WHEN** die aggregierten Timesheets mehrere Tätigkeitsarten enthalten
- **THEN** gliedert der Connector die Rechnung standardmäßig in eine Zeile je Tätigkeitsart

#### Scenario: Zwei Submit-Punkte
- **WHEN** `rechnung_aus_zeiten` das Submitten der Timesheets und das Submitten der Rechnung auslöst
- **THEN** unterliegt jeder dieser verbuchenden Schritte der Bestätigungsregel; die erzeugte Rechnung bleibt bis zur ausdrücklichen Bestätigung im Entwurf

#### Scenario: Kein Rechnungs-Item konfiguriert
- **WHEN** kein Standard-Service-/Rechnungs-Item verfügbar ist, das die aggregierten Stunden als Rechnungsposition tragen kann
- **THEN** bricht der Connector klar ab und weist auf die fehlende Config-Vorbedingung hin, statt eine ungültige Rechnung zu bauen

### Requirement: Bestätigung bei submit und cancel
Der Connector SHALL Vorgänge, die verbuchen (`submit`) oder stornieren (`cancel`) — und damit Geld/Bestand bewegen — nur nach ausdrücklicher Bestätigung ausführen.

#### Scenario: Submit erfordert Bestätigung
- **WHEN** eine Aktion ein Dokument submitten würde (z. B. eine Rechnung final verbuchen)
- **THEN** führt der Connector das Submit erst nach ausdrücklicher Bestätigung aus; ohne Bestätigung bleibt das Dokument im Entwurf

#### Scenario: Anlegen bleibt bestätigungsfrei
- **WHEN** eine Aktion nur ein Dokument im Entwurf anlegt oder ändert (kein submit/cancel)
- **THEN** führt der Connector sie ohne zusätzliche Bestätigung aus

### Requirement: Zahlung verbuchen
Der Connector SHALL zu einer Sales Invoice eine Zahlung (Payment Entry) erfassen können.

#### Scenario: Zahlung zu Rechnung
- **WHEN** `zahlung_verbuchen` mit einer echten Invoice-ID und Betrag aufgerufen wird
- **THEN** legt der Connector einen Payment Entry an, der der Rechnung zugeordnet ist, und behandelt ein etwaiges Submit gemäß der Bestätigungsregel
