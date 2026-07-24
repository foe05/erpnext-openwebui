## ADDED Requirements

### Requirement: Deklaratives Config-Blueprint
Der Connector SHALL eine ERPNext-Konfiguration aus einer deklarativen Blueprint-Datei (YAML) anwenden, statt Erstkonfiguration per freiem Chat entstehen zu lassen.

#### Scenario: Blueprint anwenden
- **WHEN** `config_blueprint_anwenden` mit einer gültigen Blueprint-Datei aufgerufen wird
- **THEN** legt der Connector die beschriebenen Config-DocTypes (z. B. Company, Konten, Steuertemplates, Item-Gruppen) in ERPNext an bzw. aktualisiert sie

### Requirement: Reihenfolge-sichere und idempotente Anwendung
Der Connector SHALL das Blueprint in einer abhängigkeits-korrekten Reihenfolge anwenden und wiederholbar (idempotent) sein.

#### Scenario: Korrekte Reihenfolge
- **WHEN** ein Blueprint abhängige Objekte enthält (z. B. Fiskaljahr vor Konten vor Steuertemplates)
- **THEN** wendet der Connector sie in korrekter Reihenfolge an, sodass keine Abhängigkeit vor ihrer Voraussetzung angelegt wird

#### Scenario: Wiederholte Anwendung ohne Duplikate
- **WHEN** dasselbe Blueprint erneut angewendet wird
- **THEN** entstehen keine Duplikate; bereits vorhandene Objekte werden erkannt und höchstens aktualisiert

#### Scenario: Abbruch bei Fehler ohne Halbzustand
- **WHEN** ein Schritt der Blueprint-Anwendung fehlschlägt
- **THEN** meldet der Connector den fehlgeschlagenen Schritt klar und setzt nicht blind mit abhängigen Folgeschritten fort

### Requirement: Selling-Config-Bündel bereitstellen
Der Connector SHALL über das Config-Blueprint das zusammenhängende Selling-Config-Bündel bereitstellen, ohne das Phase 1 (Angebot → Zeit → Rechnung) zwar formal läuft, aber falsche oder 0-Beträge erzeugt: generische Service-Items, eine Verkaufspreisliste mit Item Prices, Steuertemplates und Abrechnungssätze pro Tätigkeitsart.

#### Scenario: Generische Service-Items vorhanden
- **WHEN** das Blueprint angewendet wurde
- **THEN** existieren die generischen Service-Items, auf die die Hybrid-Item-Strategie von `angebot_erstellen` und `rechnung_aus_zeiten` zurückfallen kann

#### Scenario: Verkaufspreisliste vorhanden
- **WHEN** das Blueprint angewendet wurde
- **THEN** existiert eine Verkaufspreisliste mit Item Prices, aus der `angebot_erstellen` Positionspreise als Default zieht (Override pro Zeile bleibt möglich)

#### Scenario: Steuertemplates vorhanden
- **WHEN** das Blueprint angewendet wurde
- **THEN** existiert ein Standard-USt-Template (19 %) sowie die Varianten (z. B. 7 %, Reverse-Charge/EU), die Angebot und Rechnung als Default bzw. Override nutzen

#### Scenario: Activity-Type-Sätze vorhanden
- **WHEN** das Blueprint angewendet wurde
- **THEN** haben die verwendeten Tätigkeitsarten hinterlegte Abrechnungssätze (Activity Type bzw. Activity Cost), sodass `zeit_erfassen` keine 0-€-Zeilen erzeugt

### Requirement: Kleine Config-Tweaks als Verben
Der Connector SHALL einzelne Konfigurationsänderungen (z. B. neue Steuerklasse, neue Item-Gruppe) als gezielte Chat-Verben ermöglichen.

#### Scenario: Einzelne Config-Änderung
- **WHEN** ein Tweak-Verb (z. B. `item_gruppe_anlegen`) aufgerufen wird
- **THEN** legt der Connector das betreffende Config-Objekt an und gibt dessen ID zurück

### Requirement: Kundenportal aktivieren
Der Connector SHALL das ERPNext-eigene Kundenportal aktivieren können, ohne es selbst nachzubauen.

#### Scenario: Portal einschalten
- **WHEN** die Portal-Aktivierung angefordert wird
- **THEN** setzt der Connector die nötigen ERPNext-Einstellungen/Rollen, sodass Kunden den bestehenden Portal-Zugang nutzen können
