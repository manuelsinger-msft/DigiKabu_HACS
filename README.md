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

Pro Konto gibt es vier Sensoren: **Fehlzeiten aktualisiert**, **Stundenplan
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

## Aktionen

Die Aktionen befinden sich unter **Entwicklerwerkzeuge → Aktionen**.
`config_entry_id` bezeichnet immer den ausgewählten DigiKabu-Schülereintrag;
die Oberfläche bietet dafür eine Kontenauswahl. Ein fehlender, fremder oder
nicht geladener Eintrag wird abgewiesen.

Die vier Leseaktionen liefern `{"data": <ursprüngliche JSON-Antwort>}`.
Sie erlauben gezielte Abfragen, ohne den Standardzeitraum der Sensoren zu ändern.
In einer HA-Skriptsequenz lässt sich die Antwort mit `response_variable` verwenden:

```yaml
- action: digikabu.get_timetable
  data:
    config_entry_id: DEIN_KONFIGURATIONSEINTRAG
    datum: "2026-10-12T00:00:00+02:00"
    anzahl: 5
  response_variable: stundenplan
```

`stundenplan.data` enthält dann die Antwort. `datum` ist optional; ohne Angabe
verwendet DigiKabu seinen Standard. `anzahl` ist eine positive ganze Zahl
(Standard 1). Bei `get_exams` ist `monat` entweder `-1` (aktueller Monat,
Standard) oder `1` bis `12`. Die anderen beiden Leseaktionen benötigen nur
`config_entry_id`.

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
Ein Live-Test mit echtem Schülerkonto wurde nicht durchgeführt; weder
Anmeldung mit realen Zugangsdaten noch echte Schreibänderungen wurden getestet.
Die technische HA-Kompatibilität und die unten beschriebenen Mock-Tests
ersetzen keine Prüfung der aktuellen DigiKabu-Antworten mit einem autorisierten Konto.
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
Für `aiohttp 3.14` ergänzt der HTTP-Mock dessen neues `stream_writer`-Argument
über den öffentlichen `aioresponses`-Response-Hook; Produktivcode wird dafür
nicht verändert. GitHub Actions ergänzt Tests, Ruff, hassfest und HACS-Prüfung.
HACS-Brand-Bilder liegen lokal in `custom_components/digikabu/brand`.
