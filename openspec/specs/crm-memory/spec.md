# crm-memory

## Purpose

CRM & Gedächtnis: Kundenhistorien zusammenführen, Kontaktaktivitäten dokumentieren und an künftige Kundenkontakte erinnern. Erinnerungen sind bewusst Push über ERPNexts eigenes Notification/ToDo-System — getrennt vom Pull-basierten Chat.

## Requirements

### Requirement: Kundenhistorie abrufen
Der Connector SHALL zu einem aufgelösten Kunden eine zusammengeführte Historie aus Kommunikation und verknüpften Dokumenten liefern.

#### Scenario: Historie zusammenführen
- **WHEN** `kundenhistorie` mit einer echten Kunden-ID aufgerufen wird
- **THEN** liefert der Connector eine Übersicht aus Kommunikation/Aktivitäten und verknüpften Belegen (Angebote, Aufträge, Rechnungen, Projekte) sowie offenen Erinnerungen

### Requirement: Aktivität loggen
Der Connector SHALL Vertriebs-/Kontaktaktivitäten zu einem Kunden oder Lead dokumentieren können.

#### Scenario: Kontaktnotiz festhalten
- **WHEN** `aktivitaet_loggen` mit Bezug (Kunde/Lead) und Text aufgerufen wird
- **THEN** legt der Connector einen Kommunikations-/Aktivitätseintrag an, der an der Party hängt und in der Historie erscheint

### Requirement: Erinnerung anlegen
Der Connector SHALL Erinnerungen an künftige Kundenkontakte als ERPNext-Objekt (ToDo/Notification) mit Fälligkeitsdatum anlegen.

#### Scenario: Erinnerung mit Fälligkeit
- **WHEN** `erinnerung_anlegen` mit Bezug, Text und Fälligkeitsdatum aufgerufen wird
- **THEN** legt der Connector ein ToDo/Notification-Objekt mit Fälligkeit und Zuständigem an, das zum Fälligkeitszeitpunkt auslöst

### Requirement: Push-Mechanismus für Erinnerungen
Der Connector SHALL Erinnerungen proaktiv (Push) über den ERPNext-eigenen Notification/ToDo-Mechanismus zustellen, getrennt vom Pull-basierten Chat.

#### Scenario: Fällige Erinnerung wird zugestellt
- **WHEN** eine angelegte Erinnerung fällig wird
- **THEN** wird sie über den ERPNext-Notification/ToDo-Kanal ausgelöst, ohne dass der Nutzer zuvor im Chat danach fragen muss

#### Scenario: Chat bleibt Pull
- **WHEN** kein Nutzer aktiv im Chat fragt
- **THEN** erzeugt der Connector von sich aus keine Chat-Nachrichten; die Zustellung läuft ausschließlich über den ERPNext-Push-Kanal
