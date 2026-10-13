# Deutschland Dashboard

Statische Seite (`index.html`) mit Daten aus den `*.json`-Dateien. Eine GitHub Action holt täglich neue Werte, committet sie und veröffentlicht die Seite über GitHub Pages. Alle Dateien liegen im Hauptordner, nur der Workflow muss in `.github/workflows/`.

## Einrichten (einmalig)

1. Im Repo **Add file → Upload files** und alle Dateien aus dem ZIP (außer `update.yml`) per Dateiauswahl hochladen, dann **Commit changes**.
2. **Add file → Create new file**. Im Namensfeld `.github/workflows/update.yml` eintippen (jeder Schrägstrich legt einen Ordner an). Den Inhalt der mitgelieferten Datei `update.yml` einfügen, **Commit changes**.
3. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. **Settings → Actions → General → Workflow permissions: Read and write permissions**, speichern.
5. Reiter **Actions → „Daten aktualisieren und veröffentlichen" → Run workflow**. Nach ein bis zwei Minuten steht die Seite unter `https://<benutzername>.github.io/Deutschland-Dashboard/`.

Danach läuft alles täglich um 05:30 UTC von selbst. Die hochgeladene `update.yml` im Hauptordner darf gelöscht werden; wirksam ist nur die Kopie in `.github/workflows/`.

## Was automatisch läuft

| Daten | Skript | Quelle |
|---|---|---|
| Bund-Rendite (10 J., Tageswerte, 12 Monate) | `update_bund.py` | Bundesbank-Zeitreihe `BBSSY.D.REN.EUR.A630.000000WT1010.A` plus tägliche Bundesbank-PDFs |
| EZB-Leitzinsen, Fed Funds, Zielspanne | `update_rates.py` | EZB Data Portal, FRED |
| Sonntagsfrage (Infratest dimap) | `update_polls.py` | DAWUM-API |
| Die drei neuesten Meldungen (≤ 7 Tage) | `update_news.py` | RSS-Feeds (Bundesregierung, Destatis, tagesschau, ZEIT), Stichwortfilter |

`update_rates.py` hält außerdem das 12-Monats-Fenster von `macro_monthly.json` aktuell: Zu Monatsbeginn kommt eine leere Zeile dazu, die älteste fällt weg.

## Was von Hand gepflegt wird

- `macro_monthly.json`: `inflation`, `unemployment`, `ifo`, `zew_exp` (nach Veröffentlichung eintragen; `inflation_status` auf `"vorläufig"` setzen, solange es nur die Schnellmeldung ist).
- `key_figures.json`: Staatsfinanzen, Prognosen, Euroraum, USA (nur `bund10`, `ecb`, `fed` werden automatisch überschrieben).
- `notes.json`, `chart_meta.json`, `sources.json`: Texte, Quellenangaben, Termine.

Dateien direkt auf GitHub bearbeiten (Stift-Symbol) und committen; die Seite wird danach neu veröffentlicht.

## Bekannte Schwachstellen

- **Meldungen sind eine Stichwort-Auswahl.** `update_news.py` wählt aus RSS-Feeds per Stichwortliste (oben im Skript: `POLITIK`, `WIRTSCHAFT`, `FEEDS`) und Quellengewicht. Das kann Unwichtiges nach vorn bringen oder Wichtiges verpassen. Feeds und Stichworte lassen sich im Skript anpassen. Nicht erreichbare Feeds werden übersprungen (Warnung im Log); Bundesregierung, tagesschau und ZEIT lieferten im ersten Lauf Treffer; der Destatis-Feed wurde danach korrigiert und ist noch ungeprüft.
- **Bundesbank-Zeitreihe hinkt hinterher.** Im Oktober 2026 stand die CSV seit dem 03.08.2026 still. Die jüngsten Tage kommen deshalb aus den PDFs auf der Bundesbank-Seite. Ändert die Bundesbank Seite oder PDF-Layout, fehlen diese Tage und die Action meldet eine Warnung.
- **Erster Lauf ist der echte Test.** Die Parser sind mit Beispieldaten getestet (`python -m unittest test_updaters`), die Netzwerkabrufe konnten bei der Erstellung nicht live geprüft werden. Bei einem roten Lauf zeigt das Log im Schritt „Daten abrufen", welche Quelle gescheitert ist; die anderen laufen trotzdem weiter.
- Die Sonntagsfrage nutzt DAWUM statt POLITICO Poll of Polls (keine öffentliche API).

## Lokal ansehen

```
python -m http.server 8000
```
Dann `http://localhost:8000` öffnen (nicht die Datei direkt, sonst blockiert der Browser `fetch`).
