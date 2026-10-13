"""Tagesrendite der jeweils jüngsten 10-jährigen Bundesanleihe (Bundesbank) -> data/bund_daily.json

Quelle 1: Bundesbank-Zeitreihe BBSSY.D.REN.EUR.A630.000000WT1010.A (CSV-Download).
          Achtung: Die Zeitreihen-Datenbank hinkt zeitweise hinterher (im Oktober 2026 stand sie
          seit dem 03.08.2026 still).
Quelle 2: tägliche Bundesbank-PDFs derselben Reihe (Seite "Tägliche Renditen der jeweils
          jüngsten Bundeswertpapiere"). Sie füllen die Tage nach dem Ende der CSV auf.
          Braucht `pdftotext` (Paket poppler-utils).
"""
import re
import subprocess
import tempfile
from datetime import date, timedelta
from urllib.parse import urljoin

from common import MON, de, ddmmyyyy, http_get, load, save, set_key_figure

SERIES = "BBSSY.D.REN.EUR.A630.000000WT1010.A"
CSV_URL = (
    "https://www.bundesbank.de/statistic-rmi/StatisticDownload?tsId=" + SERIES +
    "&its_csvFormat=en&its_fileFormat=csv&mode=its&its_from={start}"
)
PAGE_URL = (
    "https://www.bundesbank.de/de/statistiken/geld-und-kapitalmaerkte/zinssaetze-und-renditen/"
    "taegliche-renditen-der-jeweils-juengsten-bundeswertpapiere-772218"
)
MONTH_RE = {
    "jan": 1, "feb": 2, "mär": 3, "mar": 3, "märz": 3, "apr": 4, "mai": 5, "jun": 6, "juni": 6,
    "jul": 7, "juli": 7, "aug": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dez": 12,
}


def parse_csv(text):
    """-> ({iso-datum: wert}, 'last update'-Zeitstempel oder None)"""
    rows, last_update = {}, None
    for line in text.splitlines():
        m = re.match(r"^(\d{4}-\d{2}-\d{2}),([0-9]+(?:\.[0-9]+)?)\b", line)
        if m:
            rows[m.group(1)] = float(m.group(2))
            continue
        m = re.match(r"^last update,([^,]+)", line)
        if m:
            last_update = m.group(1)
    return rows, last_update


def parse_pdf_text(text, today):
    """Zeilen wie 'Okt. 12. 3,83 3,83 3,72 3,46 3,35 3,24 3,11' (Laufzeiten 1..? Jahre).
    Die 4. Zahl ist die Rendite der 10-jährigen Bundesanleihe. Das Jahr steht nicht in der
    Zeile und wird rückwärts ab `today` bestimmt.
    """
    pat = re.compile(r"^\s*([A-Za-zäöüÄÖÜ]+)\.?\s+(\d{1,2})\.\s+((?:-?\d+,\d+\s+){3,}-?\d+,\d+)\s*$")
    found = []
    for line in text.splitlines():
        m = pat.match(line)
        if not m:
            continue
        mon = MONTH_RE.get(m.group(1).lower())
        if not mon:
            continue
        nums = [float(x.replace(",", ".")) for x in m.group(3).split()]
        found.append((mon, int(m.group(2)), nums[3]))
    out = {}
    year = today.year
    prev_month = None
    for mon, day, val in reversed(found):
        if prev_month is None:
            if date(year, mon, min(day, 28)) > today:
                year -= 1
        elif mon > prev_month:
            year -= 1
        prev_month = mon
        try:
            out[date(year, mon, day).isoformat()] = val
        except ValueError:
            continue
    return out


def pdf_links(html):
    links = re.findall(r'href="([^"]+?\.pdf[^"]*)"', html)
    links = [urljoin(PAGE_URL, l.replace("&amp;", "&")) for l in links]
    pref = [l for l in links if "rendbund" in l.lower() or "rendite" in l.lower()]
    return pref or links


def fetch_pdf_values(today):
    html = http_get(PAGE_URL)
    out = {}
    for url in pdf_links(html):
        raw = http_get(url, binary=True)
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(raw)
            f.flush()
            txt = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, check=True).stdout
        out.update(parse_pdf_text(txt, today))
    return out


def build_rows(values):
    rows = []
    for iso in sorted(values):
        y, m, d = iso.split("-")
        rows.append({"date": iso, "label": f"{int(d)}.{int(m)}.{y[2:]}", "tip": ddmmyyyy(iso), "kind": "Tageswert", "y10": values[iso]})
    return rows


def run(today=None, csv_text=None, pdf_values=None):
    today = today or date.today()
    existing = {r["date"]: r["y10"] for r in load("bund_daily")}
    values = dict(existing)

    start = (today - timedelta(days=400)).isoformat()
    if csv_text is None:
        csv_text = http_get(CSV_URL.format(start=start))
    csv_rows, last_update = parse_csv(csv_text)
    if not csv_rows:
        raise RuntimeError("Bundesbank-CSV enthält keine Werte")
    values.update(csv_rows)
    csv_max = max(csv_rows)

    try:
        pv = pdf_values if pdf_values is not None else fetch_pdf_values(today)
    except Exception as e:  # noqa: BLE001
        pv = {}
        print(f"::warning::PDF-Quelle nicht lesbar ({e}); es gelten nur CSV-Werte.")
    for iso, v in pv.items():
        if iso > csv_max:  # PDF füllt nur, was die CSV noch nicht hat
            values[iso] = v

    latest = max(values)
    ly, lm, ld = map(int, latest.split("-"))
    cutoff = date(ly - 1, lm, ld) + timedelta(days=1)
    values = {k: v for k, v in values.items() if k >= cutoff.isoformat() and k <= today.isoformat()}
    rows = build_rows(values)
    changed = save("bund_daily", rows)

    age = (today - date.fromisoformat(max(values))).days
    if age > 5:
        print(f"::warning::Neuester Bund-Renditewert ist {age} Tage alt ({max(values)}). CSV-Stand: {last_update}.")

    first, last = rows[0], rows[-1]
    kf = load("key_figures")
    set_key_figure(
        kf, "bund10",
        display=f"{de(first['y10'], 2)} % ({first['tip']}) → {de(last['y10'], 2)} % ({last['tip']})",
        period=f"Stand {last['tip']}",
    )
    changed |= save("key_figures", kf)
    print(f"bund_daily: {len(rows)} Werte, {first['tip']} bis {last['tip']}, geändert={changed}")
    return changed


if __name__ == "__main__":
    run()
