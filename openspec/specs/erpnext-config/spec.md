# erpnext-config

## Purpose

Konfiguration von ERPNext über den Connector: deklaratives, idempotentes Config-Blueprint (statt fragiler Erstkonfiguration per Chat), gezielte Einzel-Tweaks und Kundenportal-Zugang. Insbesondere das Selling-Config-Bündel, das Phase 1 überhaupt erst korrekt rechnen lässt.

## Requirements

### Requirement: Deklaratives Config-Blueprint
Der Connector SHALL eine ERPNext-Konfiguration aus einer deklarativen Blueprint-Datei (YAML) anwenden, statt Erstkonfiguration per freiem Chat entstehen zu lassen. Ohne Bestätigung liefert er zunächst eine Vorschau (Dry-Run), was angelegt bzw. übersprungen würde.

#### Scenario: Vorschau ohne Bestätigung
- **WHEN** `config_blueprint_anwenden` ohne Bestätigung aufgerufen wird
- **THEN** liefert der Connector eine Vorschau (anzulegen/vorhanden je Datensatz), ohne etwas zu schreiben

#### Scenario: Blueprint anwenden
- **WHEN** `config_blueprint_anwenden` mit Bestätigung für ein gültiges Blueprint aufgerufen wird
- **THEN** legt der Connector die beschriebenen Config-DocTypes (z. B. Item-Gruppen, Tätigkeitsarten, Service-Items) in ERPNext an

### Requirement: Reihenfolge-sichere und idempotente Anwendung
Der Connector SHALL das Blueprint in einer abhängigkeits-korrekten Reihenfolge anwenden und wiederholbar (idempotent) sein.

#### Scenario: Korrekte Reihenfolge
- **WHEN** ein Blueprint abhängige Objekte enthält (z. B. Item-Gruppe vor darauf verweisendem Item)
- **THEN** wendet der Connector sie in der Blueprint-Reihenfolge an, sodass keine Abhängigkeit vor ihrer Voraussetzung angelegt wird

#### Scenario: Wiederholte Anwendung ohne Duplikate
- **WHEN** dasselbe Blueprint erneut angewendet wird
- **THEN** entstehen keine Duplikate; bereits vorhandene Objekte werden anhand ihres Schlüsselfelds erkannt und übersprungen

#### Scenario: Abbruch bei Fehler ohne Halbzustand
- **WHEN** ein Schritt der Blueprint-Anwendung fehlschlägt
- **THEN** meldet der Connector den fehlgeschlagenen Schritt klar und setzt nicht blind mit abhängigen Folgeschritten fort

### Requirement: Selling-Config-Bündel bereitstellen
Der Connector SHALL über das Config-Blueprint das zusammenhängende Selling-Config-Bündel bereitstellen können, ohne das Phase 1 (Angebot → Zeit → Rechnung) zwar formal läuft, aber falsche oder 0-Beträge erzeugt: generische Service-Items, eine Verkaufspreisliste, Steuertemplates und Abrechnungssätze pro Tätigkeitsart.

#### Scenario: Generische Service-Items vorhanden
- **WHEN** das Blueprint angewendet wurde
- **THEN** existieren die generischen Service-Items, auf die die Hybrid-Item-Strategie von `angebot_erstellen` und `rechnung_aus_zeiten` zurückfallen kann

#### Scenario: Verkaufspreisliste vorhanden
- **WHEN** das Blueprint angewendet wurde
- **THEN** existiert eine Verkaufspreisliste, aus der `angebot_erstellen` Positionspreise als Default zieht (Override pro Zeile bleibt möglich)

#### Scenario: Steuertemplates vorhanden
- **WHEN** das Blueprint angewendet wurde bzw. die Templates im ERPNext-Kontenrahmen gepflegt sind
- **THEN** existiert ein Standard-USt-Template (19 %) sowie die Varianten (z. B. 7 %, Reverse-Charge/EU), die Angebot und Rechnung als Default bzw. Override nutzen

#### Scenario: Activity-Type-Sätze vorhanden
- **WHEN** das Blueprint angewendet wurde
- **THEN** haben die verwendeten Tätigkeitsarten hinterlegte Abrechnungssätze (Activity Type bzw. Activity Cost), sodass `zeit_erfassen` keine 0-€-Zeilen erzeugt

### Requirement: Kleine Config-Tweaks als Verben
Der Connector SHALL einzelne Konfigurationsänderungen (z. B. neue Item-Gruppe, neue Tätigkeitsart, Steuerklasse) als gezieltes, idempotentes Verb ermöglichen.

#### Scenario: Einzelne Config-Änderung
- **WHEN** `config_anlegen` mit DocType, Daten und Schlüsselfeld aufgerufen wird
- **THEN** legt der Connector das betreffende Config-Objekt an bzw. überspringt es, wenn es schon existiert, und gibt dessen ID zurück

### Requirement: Kundenportal-Zugang
Der Connector SHALL einem Kunden Zugang zum ERPNext-eigenen Kundenportal geben können, ohne das Portal selbst nachzubauen.

#### Scenario: Portal-Zugang anlegen
- **WHEN** `portal_zugang_anlegen` mit Kunde und E-Mail bestätigt aufgerufen wird
- **THEN** legt der Connector einen Website-User mit Customer-Rolle plus verknüpften Contact an, sodass der Kunde den bestehenden Portal-Zugang nutzen kann

#### Scenario: Portal-Zugang erfordert Bestätigung
- **WHEN** `portal_zugang_anlegen` ohne Bestätigung aufgerufen wird
- **THEN** liefert der Connector eine Vorschau/Rückfrage, statt sofort einen Login anzulegen
