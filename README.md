# DigiKabu für Home Assistant

HACS-Custom-Integration für **Home Assistant 2026.10.1** und DigiKabu-Schülerkonten.
Die Integration verwendet ausschließlich die unten aufgeführten Schüler-Endpunkte.
Keine Lehrer-, Klassenlisten- oder fremden Stundenplan-APIs.

## Installation

Das Repository muss öffentlich zugänglich sein, damit HACS die Integration
und ihre Manifestdateien herunterladen kann.

1. In HACS unter **Benutzerdefinierte Repositories** dieses Repository
   `https://github.com/manuelsinger-msft/DigiKabu_HACS` als **Integration** hinzufügen.
2. **DigiKabu** herunterladen und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → DigiKabu**
   den Schüler-Benutzernamen und das Passwort eingeben. Einen API-Schlüssel nur
   angeben, falls DigiKabu einen bereitgestellt hat; der Swagger-Parameter ist optional.

Alternativ den Ordner `custom_components/digikabu` nach
`<HA-Konfiguration>/custom_components/digikabu` kopieren und HA neu starten.
Kein Eintrag in `configuration.yaml` ist nötig. Es gibt keinen YAML-Konfigurationsmodus.
Die Veröffentlichung in der allgemeinen HACS-Liste und ein GitHub-Release sind
nicht Teil dieses Repository-Inhalts.

Die Einrichtung prüft Anmeldung und Schüler-Fehlzeitenübersicht. Mehrere
Schülerkonten sind möglich, jeweils als eigener Konfigurationseintrag.
Identische Benutzernamen werden nicht doppelt eingerichtet. Die API dokumentiert
keine unveränderliche Konto-ID und keine Groß-/Kleinschreibungsregeln:
Benutzernamen werden nur an den Rändern von Leerzeichen befreit, nicht kleingeschrieben.

## Lizenz

Die Integration steht unter der [MIT-Lizenz](LICENSE).

## Unterstützte APIs

| API | Methode und Pfad | Verwendung |
| --- | --- | --- |
| APIAuth | `POST /api/authenticate` | Anmeldung und automatische Token-Erneuerung bei HTTP 401 |
| APISchueler | `GET /api/schueler/fehlzeiten` | Sensor und Aktion `digikabu.get_absences` |
| APISchueler | `PUT /api/schueler/entschuldigung` | Ausschließlich Aktion `digikabu.submit_excuse` |
| APISettings | `POST /api/settings/email` | Ausschließlich Aktion `digikabu.set_email` |
| APIStundenplan | `GET /api/stundenplan` | Sensor und Aktion `digikabu.get_timetable` |
| APITermine | `GET /api/termine/schulaufgaben` | Sensor und Aktion `digikabu.get_exams` |
| APITermine | `GET /api/termine` | Sensor und Aktion `digikabu.get_appointments` |

`idAbteilung` wird nicht gesetzt: Laut Swagger ist die Abteilung für Schüler
ohne Bedeutung. Nicht implementiert sind auch Schülerfotos,
`allstudentsandteachers` und Schulaufgaben einer beliebigen Klasse: Deren
Zugänglichkeit für Schüler ist nicht hinreichend dokumentiert.

## Sensoren

Pro Konto gibt es vier Rohdaten-Sensoren: **Fehlzeiten aktualisiert**, **Stundenplan
aktualisiert**, **Schulaufgaben aktualisiert** und **Termine aktualisiert**.
Sie sind unter einem virtuellen DigiKabu-Kontogerät zusammengefasst.

Der Zustand ist ein Zeitstempel des letzten erfolgreichen Abrufs, **nicht**
die Zahl der Fehlzeiten, ein Unterrichtsbeginn oder das Datum des nächsten Termins.
Das Attribut `response` enthält die unveränderte JSON-Antwort des jeweiligen
Endpunkts. Listen, Objekte und andere gültige JSON-Werte bleiben in ihrer Form
erhalten. Es werden keine nicht dokumentierten Feldnamen vorausgesetzt.

Alle 15 Minuten wird jeder aktivierte Sensor unabhängig aktualisiert:
heutiger Stundenplan für einen Tag, Schulaufgaben des aktuellen Monats,
Fehlzeitenübersicht und Termine. Ein Fehler lässt nur den betroffenen Sensor
`unavailable` werden; die letzte Antwort kann weiterhin vorhanden, aber veraltet
sein. Deaktivierte Sensoren werden nach dem initialen Einrichtungsabruf nicht
weiter abgefragt. HTTP-Anfragen sind pro Konto serialisiert und haben ein
30-Sekunden-Limit. Entfernen/Entladen des Eintrags beendet das Sensor-Polling.

Zusätzlich gibt es **Card-Stundenplan Woche 1** und **Card-Stundenplan Woche 2**.
Diese werden ausschließlich durch `digikabu.get_card_timetable` befüllt,
nicht durch das reguläre Polling. Details und Dashboard-Konfiguration siehe unten.

## Daten gezielt abrufen

Für den Alltag reichen die automatisch aktualisierten Sensoren. Wenn du
einen anderen Zeitraum oder die Daten sofort abrufen möchtest, stehen dir
DigiKabu-Aktionen zur Verfügung. Dafür brauchst du keine Programmierkenntnisse.
Die hier gezeigten Abrufe lesen nur Daten; sie senden keine Entschuldigung
und ändern keine E-Mail-Adresse.

### Abruf über die Oberfläche

1. Öffne **Einstellungen → Automationen & Szenen → Skripte** und erstelle
   ein neues Skript.
2. Wähle **Aktion hinzufügen**, suche nach **DigiKabu** und wähle den
   gewünschten Abruf aus, zum Beispiel **Schulaufgaben abrufen**.
3. Wähle dein **Schülerkonto** und fülle bei Bedarf Zeitraum oder Monat aus.
   Speichere das Skript und führe es aus. Du kannst es später wiederverwenden
   oder dieselbe Aktion in einer Automation einsetzen.

Zum einmaligen Ausprobieren und direkten Anzeigen der JSON-Antwort gibt es
zusätzlich **Entwicklerwerkzeuge → Aktionen**. Der technische Menüname bedeutet
hier nur: Aktion auswählen, Schülerkonto auswählen und ausführen. Es ist
keine Änderung an `configuration.yaml` nötig.

| Was möchtest du abrufen? | Aktion | Zusätzliche Angaben |
| --- | --- | --- |
| Termine des Schülerkontos | **Termine abrufen** (`digikabu.get_appointments`) | Keine |
| Schulaufgaben des aktuellen Monats | **Schulaufgaben abrufen** (`digikabu.get_exams`) | Monat weglassen oder `-1` |
| Schulaufgaben eines bestimmten Monats | **Schulaufgaben abrufen** (`digikabu.get_exams`) | Monat `1` bis `12`, z. B. `10` für Oktober; kein Jahresparameter |
| Heutiger Stundenplan | **Stundenplan abrufen** (`digikabu.get_timetable`) | Datum weglassen, Anzahl `1` |
| Stundenplan ab einem bestimmten Tag | **Stundenplan abrufen** (`digikabu.get_timetable`) | Startdatum und Anzahl Kalendertage |
| Eine oder zwei Wochen für das Dashboard | **Card-Stundenplan abrufen** (`digikabu.get_card_timetable`) | Datum in der ersten Woche und `1` oder `2` Wochen; siehe Card-Anleitung unten |
| Fehlzeitenübersicht | **Fehlzeiten abrufen** (`digikabu.get_absences`) | Keine |

### Kopierbare Beispiele für Skripte und Automationen

Die Beispiele sind vollständige Skript-Konfigurationen für den YAML-Editor
eines Skripts. In einer Automation kannst du die Schritte unter `sequence`
als Aktionen übernehmen. YAML ist optional: Die gleichen Felder lassen sich
auch über die Oberfläche einstellen.

Ersetze **`DEIN_KONFIGURATIONSEINTRAG`** durch die ID deines DigiKabu-Kontos.
`config_entry_id` ist diese Konto-ID, **nicht** der Benutzername oder eine
Sensor-Entity-ID. Am einfachsten wählst du das Schülerkonto zunächst in einer
Aktion über die Oberfläche aus; im YAML-Editor derselben Aktion kannst du
anschließend den eingesetzten Wert ablesen. Ein fehlender, fremder oder
nicht geladener Eintrag wird abgewiesen.

**Termine abrufen:**

```yaml
alias: DigiKabu Termine abrufen
sequence:
  - action: digikabu.get_appointments
    data:
      config_entry_id: DEIN_KONFIGURATIONSEINTRAG
    response_variable: termine
```

Die Antwort steht danach für weitere Schritte desselben Skripts unter
`termine.data` bereit. Der Abruf benötigt weder Datum noch Abteilung:
`idAbteilung` ist laut DigiKabu für Schüler ohne Bedeutung.

**Schulaufgaben des aktuellen Monats abrufen:**

```yaml
alias: DigiKabu Schulaufgaben abrufen
sequence:
  - action: digikabu.get_exams
    data:
      config_entry_id: DEIN_KONFIGURATIONSEINTRAG
      monat: -1
    response_variable: schulaufgaben
```

Die Antwort steht unter `schulaufgaben.data`. Für Oktober beispielsweise
`monat: 10` einsetzen. Zulässig sind `-1` für den aktuellen Monat
(auch der Standard ohne Monatsangabe) oder `1` bis `12`.

**Heutigen Stundenplan abrufen:**

```yaml
alias: DigiKabu Stundenplan heute abrufen
sequence:
  - action: digikabu.get_timetable
    data:
      config_entry_id: DEIN_KONFIGURATIONSEINTRAG
      anzahl: 1
    response_variable: stundenplan
```

`datum` ist optional; ohne Angabe verwendet DigiKabu seinen Standard,
wie beim automatisch abgefragten heutigen Stundenplan.

**Montag bis Freitag einer bestimmten Woche abrufen:**

```yaml
alias: DigiKabu Stundenplan einer Woche abrufen
sequence:
  - action: digikabu.get_timetable
    data:
      config_entry_id: DEIN_KONFIGURATIONSEINTRAG
      datum: "2026-10-12T00:00:00+02:00"
      anzahl: 5
    response_variable: stundenplan
```

Das Beispiel liest **12. bis 16. Oktober 2026**. Ersetze das Datum für deine
gewünschte Woche; die weiter unten beschriebenen API-Grenzen gelten dabei.
`anzahl` zählt **Kalendertage einschließlich des Starttags**, nicht
Unterrichtstage, und ist eine positive ganze Zahl (Standard `1`).
Für zwei Wochen von Montag bis zum Freitag der Folgewoche sind es `12`
Kalendertage. Für ein Stundenplan-Dashboard verwende stattdessen
`get_card_timetable`: Diese Aktion übernimmt die Aufbereitung und befüllt
die Card-Sensoren.

Die vier ursprünglichen Leseaktionen liefern
`{"data": <ursprüngliche JSON-Antwort>}`. `response_variable` gibt der Antwort
einen Namen für nachfolgende Schritte derselben Skript- oder
Automationsausführung; es erzeugt keinen zusätzlichen Sensor und zeigt
allein noch keine Daten im Dashboard an. Du kannst die Antwort auch in der
Ablaufverfolgung des ausgeführten Skripts nachsehen.
Diese gezielten Rohdaten-Abrufe ändern weder den Standardzeitraum noch die
gespeicherte Antwort der vier automatisch aktualisierten Sensoren.

### Beobachtete API-Grenzen: Vergangenheit und Zukunft

Ein autorisierter Live-Test am **11.10.2026** zeigte für
`GET /api/stundenplan` getrennte Grenzen für das **Startdatum `datum`**
und die **Abruflänge `anzahl`**:

| Parameter / Richtung | Beobachtetes Ergebnis |
| --- | --- |
| Startdatum in der Vergangenheit | **04.10.2026, 00:00 Uhr** wurde akzeptiert: **−7 Kalendertage** gegenüber dem Testdatum. Der 03.10. und frühere getestete Tage wurden mit HTTP 400 abgewiesen. |
| Startdatum in der Zukunft | **17.10.2026, exakt 00:00 Uhr** wurde akzeptiert: **+6 Kalendertage**. Schon 00:00:01 Uhr desselben Tages sowie spätere getestete Tage wurden mit HTTP 400 abgewiesen. |
| Abruflänge | `anzahl: 14` wurde akzeptiert; `anzahl: 15` wurde mit HTTP 400 abgewiesen. `anzahl` zählt Kalendertage einschließlich des Starttags, nicht Unterrichtstage. |
| Gesamter Zeitraum | Start **17.10.2026, 00:00 Uhr** mit `anzahl: 14` lieferte Unterrichtseinträge bis **30.10.2026**, also **+19 Kalendertage** gegenüber dem Testdatum. Die obere Startdatumsgrenze begrenzt somit nicht das Ende des abgerufenen Zeitraums. |

Die Vorzeichen beziehen sich auf den Abstand des Datums zum Testtag:
**negativ = Vergangenheit, positiv = Zukunft**. Sie sind **keine Werte für
`anzahl`**: Dieser Parameter muss eine positive ganze Zahl sein. Rückwärts
abrufen bedeutet ein früheres `datum` setzen und von dort vorwärts lesen,
nicht eine negative Anzahl übergeben.

Die für die Webseite beobachtete Navigation bis 28.09. bzw. 23.10. ist
nicht mit den API-Grenzen gleichzusetzen. Der 28.09. konnte über diese API
nicht abgerufen werden; über einen zulässigen Start und längere Abruflänge
waren dagegen Daten nach dem 23.10. erreichbar. Erfolgreiche Antworten mit
leerer Liste (z. B. am Wochenende) bedeuten ein akzeptiertes Datum, nicht
zwingend vorhandenen Unterricht.

**Dies sind Beobachtungen für das getestete Konto und den 11.10.2026,
keine in Swagger zugesicherten dauerhaften Grenzen.** Insbesondere die
sekundengenaue obere Grenze deutet auf eine zeitabhängige Serverprüfung hin;
ihre Ursache ist nicht belegt. Startzeiten möglichst auf **00:00 Uhr in
Europe/Berlin** setzen und HTTP 400 als abgewiesene Anfrage behandeln.
Die rohe Leseaktion erzwingt derzeit nur `anzahl >= 1`, keine feste
14-Tage-Obergrenze; der Server entscheidet über die Zulässigkeit.
Die Card-Aktion normalisiert den Start auf Montag um 00:00 Uhr und benötigt
für eine bzw. zwei Wochen **5 bzw. 12 Kalendertage**. Auch dabei muss der
gewählte Montag innerhalb des aktuell vom Server akzeptierten Startfensters liegen.

### Stundenplan-Card: eine oder zwei Wochen

Die zusätzliche Leseaktion **`digikabu.get_card_timetable`** ruft ausschließlich
`GET /api/stundenplan` auf und bereitet das im Live-Abruf beobachtete
Schülerformat für die
[Stundenplan-Card](https://github.com/fabel-smith/stundenplan-card) auf.
Es wird kein neuer DigiKabu-Endpunkt verwendet.

#### Card herunterladen und installieren

Du benötigst zwei getrennte Komponenten: **Diese DigiKabu-Integration holt
die Daten**, die **Stundenplan-Card zeigt sie im Dashboard an**.
Die Card ist nicht in dieser Integration enthalten. Für diesen
Sensor-basierten Weg brauchst du **keine Stundenplan-Suite** und kein
zusätzliches Konto bei einem anderen Stundenplananbieter.

- [Stundenplan-Card: Projekt und offizielle Anleitung](https://github.com/fabel-smith/stundenplan-card)
- [Aktuelle Veröffentlichung und Downloads](https://github.com/fabel-smith/stundenplan-card/releases/latest)

**Am einfachsten über HACS installieren:**

1. Öffne **HACS → Drei-Punkte-Menü → Benutzerdefinierte Repositories**.
2. Trage `https://github.com/fabel-smith/stundenplan-card` ein und wähle
   den Typ **Dashboard**. Das ist eine Frontend-Card, keine Integration.
   Laut Card-Anleitung ist sie derzeit nicht im HACS-Standardkatalog.
3. Suche in HACS nach **Stundenplan Card** und wähle **Herunterladen**.
4. Lade Home Assistant im Browser neu. Falls die Card nicht erscheint,
   aktualisiere den Browser-Cache, beispielsweise mit **Strg + F5**.
   Für die Card allein ist normalerweise kein HA-Neustart nötig;
   eine neue Version der DigiKabu-Integration benötigt weiterhin einen Neustart.

HACS trägt die Dashboard-Ressource normalerweise automatisch ein.
Nur falls die Card danach nicht geladen wird, prüfe unter
**Einstellungen → Dashboards → Ressourcen**, ob
`/hacsfiles/stundenplan-card/stundenplan-card.js` als **JavaScript-Modul**
eingetragen ist. Keine zweite identische Ressource anlegen.
Bei einer manuellen Installation statt HACS folge der offiziellen
Card-Anleitung; der Ressourcenpfad hängt dann vom Ablageort ab.

#### DigiKabu-Daten für die Card abrufen

Die Aktion **Card-Stundenplan abrufen** wie oben beschrieben in einem Skript
oder zum einmaligen Abruf in der Aktionsansicht öffnen. Das Schülerkonto auswählen,
`datum` auf einen Tag der gewünschten ersten Woche und `weeks` auf **1 oder 2**
setzen. Das Datum wird auf Montag in **Europe/Berlin** normalisiert.
Ohne Datum gilt die aktuelle Woche, auch am Wochenende. Für die nächste Woche
also ausdrücklich deren Datum angeben.

```yaml
action: digikabu.get_card_timetable
data:
  config_entry_id: DEIN_KONFIGURATIONSEINTRAG
  datum: "2026-10-12T00:00:00+02:00"
  weeks: 2
```

Optional filtert `gruppe: "1/2"` auf genau diese Gruppe plus gemeinsame Stunden
(`1/1` oder ohne Gruppenangabe). Ohne Filter bleiben alle parallelen
Gruppen als getrennte Textblöcke derselben Zelle sichtbar. Fach, Lehrer,
Raum und Gruppe werden übernommen; Mehrfachstunden werden auf einzelne
Stunden verteilt. Freistunden bleiben leer. Samstag und Sonntag werden
nicht dargestellt; die Ausgabe umfasst je Woche Montag bis Freitag.

**Das Zeitraster ist schulabhängig:** Diese Aktion verwendet die vom Nutzer
für BSZ Wiesau bestätigten Zeiten, nicht eine vermeintlich allgemeine
DigiKabu-Zeittabelle:

| Stunde | Beginn | Ende |
| --- | --- | --- |
| 1 | 08:30 | 09:15 |
| 2 | 09:15 | 10:00 |
| Pause | 10:00 | 10:15 |
| 3 | 10:15 | 11:00 |
| 4 | 11:00 | 11:45 |
| 5 | 11:45 | 12:30 |
| 6 | 12:30 | 13:15 |
| 7 | 13:15 | 14:00 |
| 8 | 14:00 | 14:45 |
| 9 | 14:45 | 15:30 |
| 10 | 15:30 | 16:15 |

Die Pause erscheint als eigene `break`-Zeile und trennt auch Mehrfachstunden.
Bei anderen Schulzeiten diese Aktion nicht ohne Anpassung des Rasters verwenden.

Die Antwort enthält `data.weeks`, eine Liste mit einer oder zwei Wochen.
Jede Woche besitzt `week_start`, `week_end`, `dates`, `days` und `rows`.
`rows` ist direkt Card-konform (`time`, `start`, `end`, fünf `cells` pro
Unterrichtszeile sowie eine Pausenzeile). Die Wochenobjekte stehen zugleich
als Attribute der beiden Card-Sensoren bereit. Ein erfolgreicher Abruf von
nur einer Woche leert den zweiten Sensor, damit dort kein alter Plan bleibt.
Eine leere API-Liste ergibt ein leeres Wochenraster. Nicht unterstützte
Antwortformen, Datumswerte und Stundenbereiche werden ausdrücklich abgewiesen;
bei einem Fehler bleiben die vorherigen Daten mit ihrem alten Abrufzeitpunkt erhalten.

#### Änderungen und Entfall seit vorherigem Abruf

Die Card-Aktion speichert pro Schülerkonto den zuletzt beobachteten Plan
**persistent über Home Assistants Storage-Helfer**. Verglichen wird je Datum,
Stundennummer und Gruppe; Fach, Lehrer und Raum gehen in den Vergleich ein.
Die ungefilterte Antwort wird verglichen, erst danach wird ein optionaler
Gruppenfilter auf die Anzeige angewendet. Ein Filterwechsel erzeugt daher
keine vermeintlichen Änderungen oder Ausfälle.

- **Erster gefüllter Abruf eines Tages:** Ausgangsplan, ohne Markierung.
  Auch wenn dieser Tag zuvor eine leere API-Antwort hatte, werden seine
  erstmals gelieferten Stunden nicht pauschal als geändert markiert.
- **Geänderter Eintrag oder neue Stunde eines bereits gefüllten Tages:**
  Text `Geaendert seit vorherigem Abruf` und gelbe Zelle.
  Der Status bleibt bei identischen Folgeabrufen und nach HA-Neustart erhalten.
- **Nicht mehr gelieferte, zuvor vorhandene Stunde:** Der letzte Eintrag
  bleibt mit `Entfallen seit vorherigem Abruf` sichtbar. Eine ausschließlich
  entfallene Zelle ist rot; bei gemischten parallelen Gruppen ist sie gelb,
  und die Texte kennzeichnen die betroffenen Gruppen einzeln.
  Auch ein später vollständig leer gelieferter, zuvor gefüllter Tag wird so
  behandelt. Ein fehlgeschlagener HTTP-Abruf gilt dagegen niemals als Entfall.
- **Wieder auftauchende Stunde:** Der Entfall wird durch eine Änderungsmarkierung
  ersetzt. Ein bestehender Änderungsstatus wird nicht bei jedem Abruf zurückgesetzt.

Die Farben werden Card-konform als `cell_styles` mitgegeben. Mehrfachstunden
werden weiterhin einzeln verglichen, sodass ein teilweiser Entfall nur die
betroffenen Stunden kennzeichnet und die Pausenzeile unverändert bleibt.
Nicht abgefragte Tage/Wochen werden nicht als entfallen behandelt.

**Das sind Vergleichsmarkierungen, keine offiziellen DigiKabu-Statusmeldungen.**
Die API übermittelt in den beobachteten Antworten weder `Änderung` noch
`entfällt`. Ein entfernter Eintrag kann beispielsweise auch eine korrigierte
Planung sein. Vor dem ersten gespeicherten Ausgangsplan sind historische
Änderungen nicht rekonstruierbar; markierte Stunden bleiben bis zur Änderung
ihres Status oder bis zum Ablauf des Datums im Cache gekennzeichnet.
Die Rohdaten-Sensoren und `get_timetable` bleiben unverändert und aktualisieren
diesen Vergleichscache nicht.

Beim Laden und nach jedem erfolgreichen Card-Abruf wird der Cache auf
**heutiges Schuldatum −7 bis +19 Kalendertage einschließlich** begrenzt
(höchstens 27 Datumswerte). Grundlage ist das beobachtete maximale
API-Fenster; es ist keine zusätzliche Garantie des Servers.
Ohne neue Abrufe oder Laden erfolgt keine zeitgesteuerte Bereinigung.
Entladen/Neustart erhält den Cache; Entfernen des DigiKabu-Kontos löscht dessen
Cache über den Storage-Helfer. Die Datei enthält Unterrichtsdaten,
aber keine Passwörter oder API-Tokens, und kann Bestandteil von HA-Backups sein.
Home Assistant protokolliert Fehler beim Schreiben seiner Storage-Dateien;
bei einem solchen Fehler kann der aktuelle Vergleich im Arbeitsspeicher
verfügbar sein, ohne einen Neustart zu überstehen.

Nach Installation der neuen Integrationsversion und HA-Neustart die Aktion
einmal ausführen. Die beiden Sensoren sind vorher `unavailable`. Ihre Daten
liegen nur im Arbeitsspeicher: Nach Entladen oder Neustart erneut abrufen.
Der Vergleichscache bleibt dabei erhalten und wird beim nächsten Abruf verwendet.
Für laufende Aktualisierungen kann die Leseaktion aus einer eigenen Automation
aufgerufen werden; es werden keine Automationen in der HA-Instanz angelegt.

#### Stundenplan im Dashboard anzeigen

1. Installiere die Card wie oben beschrieben und führe
   **Card-Stundenplan abrufen** einmal für dein Schülerkonto aus.
2. Ermittle die Entity-IDs der beiden Card-Sensoren wie nachfolgend beschrieben.
3. Öffne dein Dashboard, wähle **Bearbeiten → Karte hinzufügen → Manuell**
   und füge das folgende Kartenbeispiel mit deinen Sensor-IDs ein.
4. Speichere die Karte. Nach jedem weiteren erfolgreichen Card-Abruf
   übernimmt sie die aktualisierten Sensorattribute automatisch.

Öffne unter
**Einstellungen → Geräte & Dienste → DigiKabu** dein Kontogerät und die
Sensoren **Card-Stundenplan Woche 1** bzw. **Woche 2**. Ihre tatsächlichen
Entity-IDs findest du in den jeweiligen Entity-Einstellungen; setze sie
in diesem Dashboard-Beispiel ein. Alternativ kannst du die IDs und alle
Attribute unter **Entwicklerwerkzeuge → Zustände** nachsehen:

```yaml
type: vertical-stack
cards:
  - type: custom:stundenplan-card
    title: "Stundenplan Woche 1"
    source_type: sensor
    source_entity: sensor.DEIN_CARD_SENSOR_WOCHE_1
    source_attribute: rows
    days: [Mo, Di, Mi, Do, Fr]
    highlight_today: false
    highlight_current: false
  - type: custom:stundenplan-card
    title: "Stundenplan Woche 2"
    source_type: sensor
    source_entity: sensor.DEIN_CARD_SENSOR_WOCHE_2
    source_attribute: rows
    days: [Mo, Di, Mi, Do, Fr]
    highlight_today: false
    highlight_current: false
```

Für eine Woche genügt die erste Card. Die zweite Card ist **keine A/B-Woche**,
sondern die unmittelbar folgende Kalenderwoche. Die Card-Wochennavigation
fordert bei diesen Sensoren keine anderen Wochen an: Den Zeitraum über die
Aktion wechseln. Die Hervorhebung ist hier bewusst ausgeschaltet, weil die
angefragte Woche nicht zwingend die aktuelle ist; Datum und Abrufzeitpunkt
sind in den Sensorattributen bzw. im Sensorzustand sichtbar.
Einmalig kopierte JSON-Daten lassen sich alternativ als manuelle `rows`
der Card verwenden, werden dann aber nicht automatisch aktualisiert.

**Falls noch kein Plan angezeigt wird:** Sind die Card-Sensoren
`unavailable`, führe den Card-Abruf aus; das reguläre 15-Minuten-Polling
befüllt diese beiden Sensoren nicht. Sind die Sensoren vorhanden, aber die
Card meldet einen Fehler, prüfe die eingetragenen Entity-IDs und
`source_attribute: rows`. Bei **Custom element doesn't exist:
stundenplan-card** zuerst Installation, Ressource und Browser-Cache prüfen.
Ein erfolgreicher erster Abruf ohne Unterricht ergibt ein leeres Raster;
bei bereits gespeicherten Stunden können stattdessen Entfallmarkierungen
erscheinen. Ein abgewiesener API-Zeitraum aktualisiert den Plan nicht.
Prüfe in diesem Fall die oben dokumentierten Datumsgrenzen.

### Online-Entschuldigung

**Ein Aufruf sendet eine echte Entschuldigung.** Die Integration ruft diese
Aktion niemals selbstständig auf. Beim Einrichten, Polling und Testen wird
keine Entschuldigung abgeschickt. Konto und Eingaben vor dem Aufruf prüfen.

`submit_excuse` benötigt `config_entry_id`, `ab_datum` als ISO-Datum/Uhrzeit
und `dauer` als ganze Zahl von 1 bis 3. `grund` ist optional; ausgelassen
wird gemäß nullable Swagger-Feld `null` übertragen.

Der Beginn muss heute (nur vor 09:00 Uhr) oder morgen sein. Diese Prüfung
verwendet die Schulzeitzone **Europe/Berlin**, einschließlich Sommerzeit,
unabhängig von der HA-Zeitzone. Ein Zeitpunkt ohne Zeitzone wird als
Schulzeit interpretiert. Die Zeit wird auf Mitternacht des entsprechenden
Schultages normalisiert. DigiKabu prüft die endgültige Berechtigung und
alle serverseitigen Einschränkungen. Nach erfolgreichem HTTP-Aufruf wird
die Fehlzeitenübersicht aktualisiert.

### E-Mail-Adressen

**`set_email` ändert Daten im Schülerkonto.** Die Aktion benötigt
`config_entry_id` sowie ausdrücklich **beide** Felder `email1` und `email2`.
Ein ausgelassenes Feld wird abgewiesen, statt versehentlich einen bisherigen
Wert zu überschreiben. Bereits vorhandene Adressen können über die
dokumentierte API nicht ausgelesen werden; deshalb gibt es keine vorausgefüllten
Text-Entitäten und keine automatisch ausgeführten Schreibaktionen.

In YAML kann für ein Feld ausdrücklich `null` angegeben werden. Das wird als
`eMail1: null` bzw. `eMail2: null` übertragen; ob DigiKabu dadurch einen Wert
löscht oder anderweitig behandelt, ist nicht dokumentiert und wird nicht zugesichert.
Ein Leerstring bleibt ein Leerstring und wird nicht automatisch in `null` umgewandelt.

## Fehler und Datenschutz

Bei abgelaufenem Token wird einmal neu angemeldet und die mit **HTTP 401**
abgewiesene Anfrage einmal wiederholt. Wenn DigiKabu die Anmeldung oder das
erneuerte Token ablehnt, fordert HA eine erneute Authentifizierung an.
HTTP 403 bei Datenabfragen wird als Berechtigungs-/API-Fehler behandelt, nicht
als Endlosschleife von Neuanmeldungen. HTTP 429 und Serverfehler werden
sichtbar gemeldet; die betroffenen Sensoren versuchen den nächsten regulären Abruf.

**Schreibanfragen werden nach Timeout, Verbindungsabbruch oder Serverfehler
nicht automatisch wiederholt.** Bei Timeout/Verbindungsabbruch kann der
Server die Änderung bereits ausgeführt haben: vor einem erneuten Aufruf
in DigiKabu nachsehen. Es gibt keinen dokumentierten Idempotenzschlüssel.
Ein 2xx-Status ist die technische Erfolgsbestätigung; unbekannte
anwendungsspezifische Fehler innerhalb einer 2xx-Antwort sind ohne
dokumentiertes Antwortmodell nicht interpretierbar.

Passwort und optionaler API-Schlüssel liegen im HA-Konfigurationseintrag
und damit auch in dessen Backups. Der Token bleibt nur im Arbeitsspeicher.
TLS-Prüfung bleibt aktiv; HTTP-Weiterleitungen werden nicht verfolgt.
Fehlermeldungen enthalten weder Antwortkörper noch Zugangsdaten.
Die Integration bietet bewusst keine Diagnoseausgabe mit Schülerdaten.

**Sensorattribute können sensible Schüler- und Fehlzeitendaten enthalten.**
Sie sind für berechtigte HA-Nutzer sichtbar und können vom Recorder sowie
Backups gespeichert werden. Bei Bedarf diese Sensoren über die
Recorder-Ausschlusskonfiguration ausschließen oder deaktivieren und nur
gezielte Leseaktionen verwenden. Die Integration fügt keine Schreibautomationen
hinzu; wer solche selbst erstellt, ist für deren Ausführung verantwortlich.

## Quellen und Kompatibilitätsgrenzen

- [DigiKabu Swagger UI](https://www.digikabu.de/swagger/index.html) und
  [vollständige OpenAPI-Spezifikation](https://www.digikabu.de/swagger/v1/swagger.json),
  geprüft am 11.10.2026. Die Spezifikation bezeichnet die API als im Aufbau und
  beschreibt für diese Endpunkte **keine Erfolgs-Antwortschemata**.
- [HACS integration_blueprint](https://github.com/ludeeus/integration_blueprint/tree/cd399dac2a7e88d899dd62b3f5d8bbf91f1adadd):
  Vorlage für Struktur, Config Flow, Session-Wiederverwendung, Coordinator,
  Runtime-Daten und HACS-/hassfest-Validierung. Demo-Schalter/-Sensoren wurden
  nicht übernommen; die Implementierung ist eigenständig.
- [HA 2026.10.1](https://github.com/home-assistant/core/tree/2026.10.1) und die
  offiziellen Entwicklerdokumente für
  [Config Flows](https://developers.home-assistant.io/docs/core/integration/config_flow/),
  [Coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/),
  [Aktionen](https://developers.home-assistant.io/docs/dev_101_services/) und
  [Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/).
  Diese Custom-Integration beansprucht keine offiziell geprüfte Quality-Scale-Stufe.
- Für das nicht dokumentierte Authentifizierungsformat dient zusätzlich der
  öffentliche Client
  [kabuApp AuthApi.java](https://github.com/Mika-techs/kabuApp/blob/30fefb73a75eb04e5111496de47cc2609c57ee24/app/src/main/java/org/kabuapp/kabuapp/feature/auth/AuthApi.java)
  als Beleg: JSON-kodierter oder unkodierter JWT-String sowie HTTP 400 bei
  abgewiesenen Zugangsdaten. Das ist ein Sekundärbeleg, keine Zusicherung
  des API-Anbieters. Abweichende Token-Objekte werden ausdrücklich abgewiesen.

Es werden deshalb bewusst **keine Kalenderereignisse, Uhrzeiten oder
Abwesenheitszähler aus geratenen Antwortfeldern erzeugt**. Die API-Daten
sind vollständig über Sensorattribute und Leseaktionen verfügbar.
Am 11.10.2026 wurde auf ausdrücklichen Nutzerwunsch ein Wochenstundenplan
über die bereits eingerichtete HA-Instanz gelesen. Die Card-Aufbereitung basiert
auf den dabei beobachteten Feldern `datum`, `anfStd`, `endStd`, `uFachBez`,
`lehrer`, `raumLongtext` und `gruppe`; diese sind weiterhin kein offiziell
zugesichertes Antwortschema. Reale Schülerdaten werden nicht als Testdateien
mitgeliefert. Andere Endpunkte und echte Schreibänderungen wurden nicht live getestet.
Die technische HA-Kompatibilität und die unten beschriebenen Mock-Tests
ersetzen keine vollständige Prüfung mit einem autorisierten Konto.
Das mitgelieferte Symbol ist eine eigenständig gestaltete Stundenplan-Grafik
für diese Custom-Integration, kein offizielles DigiKabu-Logo.

## Entwicklung

Home Assistant 2026.10.1 benötigt **Python ≥ 3.14.2**, verwendet
`probatio` für Schemas und bringt die benötigte `aiohttp`-Version mit.
Die Integration installiert keine zusätzlichen Laufzeitabhängigkeiten.

```text
uv sync --locked --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Die Tests verwenden das echte HA-Paket **2026.10.1** und synthetische Antworten:
Authentifizierung, Endpunkt-/Payload-/Parameterverträge, Token-Erneuerung,
Fehlerpfade, Config Flow/Doubletten/Reauth, Einrichtung/Entladen, Sensoren,
kontobezogene Aktionen und Entschuldigungsfristen einschließlich Sommerzeit.
Die Card-Tests prüfen Wochenzuordnung, Uhrzeiten und Pausen, parallele Gruppen,
Fehler bei unbekannten Antwortformen sowie die tatsächliche HA-Sensoraktualisierung.
Cache-Tests prüfen leere Erstabrufe, dauerhafte Änderungs-/Entfallmarkierungen,
Wiederauftauchen, Teilentfall, Gruppenfilter, parallele Abrufe, Neustart,
Kontentrennung und die exakten Datumsgrenzen der Bereinigung.
Für `aiohttp 3.14` ergänzt der HTTP-Mock dessen neues `stream_writer`-Argument
über den öffentlichen `aioresponses`-Response-Hook; Produktivcode wird dafür
nicht verändert. GitHub Actions ergänzt Tests, Ruff, hassfest und HACS-Prüfung.
HACS-Brand-Bilder liegen lokal in `custom_components/digikabu/brand`.
