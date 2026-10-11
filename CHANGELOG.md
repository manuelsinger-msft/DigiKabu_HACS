# Changelog

## 0.9.1 - 2026-10-11

### Neu

- Aktion `digikabu.get_card_timetable` für ein oder zwei aufeinanderfolgende
  Schulwochen mit optionalem Gruppenfilter und zwei zusätzlichen Card-Sensoren.
- Für die Stundenplan Card aufbereitete Daten mit fünf Wochentagen,
  Unterrichtszeiten, Pausenzeile und parallelen Unterrichtsgruppen.
- Kontospezifischer, über HA-Neustarts erhaltener Vergleichscache:
  geänderte Stunden werden gelb, vollständig entfallene Stunden rot markiert.
  Erstmalig befüllte Tage werden nicht pauschal als geändert markiert;
  vorhandene Änderungsmarkierungen bleiben erhalten.
- Zwei schreibgeschützte Kalender für Schulaufgaben und Termine, verwendbar
  mit Calendar Card Pro und anderen HA-Kalenderkarten.

### Dokumentation und Versionierung

- Benutzerfreundliche Aufrufbeispiele für Stundenplan, Schulaufgaben und
  Termine sowie Installation und Verwendung der Stundenplan Card.
- Beobachtete API-Grenzen dokumentiert: Startdatum von heute minus sieben
  bis plus sechs Tagen, höchstens 14 Abruf-Tage und zurückgelieferte Daten
  bis heute plus 19 Tage. Der Vergleichscache umfasst entsprechend höchstens
  27 Datumswerte. Diese Grenzen sind empirisch, keine Servergarantie.
- Kalender-Antwortformate, Monats-/Jahresgrenzen und Speicherung persönlicher
  Laufzeitdaten in HA einschließlich Backups erläutert.
- Integrationsmanifest und Projektversion auf `0.9.1` vereinheitlicht.
- Aktueller Repository-Inhalt vor Veröffentlichung statisch auf echte
  Zugangsdaten und versehentlich mitgelieferte Schülerdaten geprüft:
  keine entsprechenden Funde. Keine vollständige Git-Historienprüfung.

Das individuell eingerichtete Tablet-Dashboard und seine lokalen Kartenanpassungen
sind nicht Bestandteil dieses Integrations-Releases.

## 0.9 - 2026-10-11

- Erstes veröffentlichtes Release für Home Assistant 2026.10.1.
- Schüler-APIs für Anmeldung, Fehlzeiten, Online-Entschuldigungen,
  E-Mail-Einstellungen, eigenen Stundenplan, Schulaufgaben und Termine.
- UI-Einrichtung, Reauthentifizierung, vier Rohdaten-Sensoren sowie
  ausdrücklich aufzurufende Lese- und Schreibaktionen.
- Deutsche und englische Übersetzungen, HACS-Paketierung und MIT-Lizenz.

Der Tag `v0.9` enthält unverändert die damalige interne Version `0.1.0`.
