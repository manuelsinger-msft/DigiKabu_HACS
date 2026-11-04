# Changelog

## 0.9.3 - 2026-11-04

### Fehlerbehebungen

- Card-Stundenplan und Schulaufgabenkalender unterstützen neben `TT.MM.JJJJ`
  auch das beobachtete API-Datumsformat `MM/TT/JJJJ`. Antworten mit
  Schrägstrichen führten bisher zu nicht verfügbaren Card-Sensoren und
  Prüfungskalendern, obwohl Verbindung und Datenabruf erfolgreich waren.
- Ein Wechsel zwischen den beiden Antwortformaten erzeugt keine falschen
  Stundenplan-Änderungsmarkierungen. Ungültige Datumsangaben werden weiterhin
  ausdrücklich abgewiesen; Termin- und Aktionsparameterformate bleiben gleich.
- Regressionstests und README für beide Datumsformate ergänzt.

## 0.9.2 - 2026-11-04

### Fehlerbehebungen

- API-Basisadresse und Geräte-Konfigurationslinks auf `https://digikabu.de`
  ohne `www` umgestellt, um den TLS-Zertifikatsfehler der bisherigen Domain
  zu vermeiden. Die Zertifikatsprüfung bleibt aktiv; Anmeldung und
  API-Verhalten bleiben unverändert.
- Bisher nur lokal vorhandene Stundenplan-Anpassungen übernommen:
  Ein ausdrücklich leeres Lehrerfeld wird bereits beim ersten Abruf als
  **Entfall (kein Lehrer eingetragen)** rot markiert. Fehlende oder
  `null`-Lehrerfelder lösen diese Regel nicht aus. Dies ist eine beobachtete
  Heuristik, keine garantierte DigiKabu-Statusangabe.
- Dieser Entfallstatus bleibt im Vergleichscache erhalten; wird wieder ein
  Lehrer eingetragen, erscheint die Stunde als geändert. Vollständig
  weggefallene alte Positionen bleiben auch bei verschobenem Unterricht als
  Entfall sichtbar; bei verkürzten Mehrfachstunden nur die entfallenen Positionen.
- Rote und gelbe Card-Markierungen setzen `bg_alpha: 1` für deckende
  Hintergrundfarben.

### Dokumentation und Absicherung

- Swagger-Links auf die Domain ohne `www` aktualisiert und Hinweise zu den
  lokal ergänzten Entfallregeln in die README übernommen.
- Regressionstests für die HTTPS-Domain und unveränderte TLS-Prüfung sowie
  für leere Lehrerfelder, wiederkehrende Lehrer und verschobene Stunden.
- Integrationsmanifest, Projektversion und Lockdatei auf `0.9.2` vereinheitlicht.

Individuelle Tablet-Dashboards und lokale Kartenanpassungen außerhalb dieses
Repositories bleiben außerhalb des Integrations-Releases. Ein Update der
laufenden Home-Assistant-Installation erfolgt nicht durch die Veröffentlichung.

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
