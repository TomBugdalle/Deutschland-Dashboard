"""Leitzinsen -> data/macro_monthly.json (ecb_mro, fed_eff) und data/key_figures.json (ecb, fed)

EZB: Data Portal (SDMX-CSV), Hauptrefinanzierungssatz, Einlagesatz, Spitzenrefinanzierungssatz.
Fed: FRED, FEDFUNDS (effektiver Satz, Monatsdurchschnitt), DFEDTARL/DFEDTARU (Zielspanne).
Das Skript hält außerdem das 12-Monats-Fenster von macro_monthly aktuell (neue, leere Monatszeilen).
"""
import csv
import io
from datetime import date, timedelta

from common import MON, de, ddmmyyyy, http_get, load, save, set_key_figure

ECB = "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.{k}.LEV?format=csvdata&startPeriod={start}"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"


def parse_ecb(text):
    """-> sortierte Liste [(iso-datum, wert)]"""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("OBS_VALUE") not in (None, ""):
            out.append((r["TIME_PERIOD"], float(r["OBS_VALUE"])))
    return sorted(out)


def parse_fred(text):
    out = []
    rd = csv.reader(io.StringIO(text))
    next(rd, None)
    for row in rd:
        if len(row) >= 2 and row[1] not in (".", ""):
            out.append((row[0], float(row[1])))
    return sorted(out)


def last_on_or_before(series, iso):
    val = None
    for d, v in series:
        if d <= iso:
            val = v
        else:
            break
    return val


def since(series):
    """Datum, seit dem der letzte Wert unverändert gilt."""
    if not series:
        return None
    cur = series[-1][1]
    d = series[-1][0]
    for dd, v in reversed(series):
        if v != cur:
            break
        d = dd
    return d


def month_window(today, n=12):
    y, m = today.year, today.month
    months = []
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(months))


def roll_rows(rows, today):
    by = {r["month"]: r for r in rows}
    out = []
    for mo in month_window(today):
        if mo in by:
            out.append(by[mo])
        else:
            y, m = mo.split("-")
            out.append({"month": mo, "label": f"{MON[int(m) - 1]} {y[2:]}", "inflation": None, "unemployment": None,
                        "ifo": None, "inflation_status": "", "zew_exp": None, "ecb_mro": None, "fed_eff": None})
    return out


def run(today=None, texts=None):
    today = today or date.today()
    start = (today.replace(day=1) - timedelta(days=400)).isoformat()
    t = texts or {}
    get = lambda key, url: t[key] if key in t else http_get(url)  # noqa: E731
    mro = parse_ecb(get("MRR_FR", ECB.format(k="MRR_FR", start=start)))
    dfr = parse_ecb(get("DFR", ECB.format(k="DFR", start=start)))
    mlf = parse_ecb(get("MLFR", ECB.format(k="MLFR", start=start)))
    ff = parse_fred(get("FEDFUNDS", FRED.format(sid="FEDFUNDS", start=start)))
    lo = parse_fred(get("DFEDTARL", FRED.format(sid="DFEDTARL", start=start)))
    hi = parse_fred(get("DFEDTARU", FRED.format(sid="DFEDTARU", start=start)))
    if not (mro and dfr and mlf and ff and lo and hi):
        raise RuntimeError("Leitzins-Quellen lieferten keine Werte")

    rows = roll_rows(load("macro_monthly"), today)
    ff_by_month = {d[:7]: v for d, v in ff}
    for r in rows:
        y, m = map(int, r["month"].split("-"))
        nxt = date(y + (m == 12), m % 12 + 1, 1)
        eom = min(nxt - timedelta(days=1), today).isoformat()
        v = last_on_or_before(mro, eom)
        if v is not None:
            r["ecb_mro"] = v
        if r["month"] in ff_by_month:
            r["fed_eff"] = ff_by_month[r["month"]]
    changed = save("macro_monthly", rows)

    kf = load("key_figures")
    set_key_figure(
        kf, "ecb",
        display=f"{de(dfr[-1][1], 2)} % ({de(mro[-1][1], 2)} % / {de(mlf[-1][1], 2)} %)",
        period=f"seit {ddmmyyyy(since(dfr))}",
    )
    set_key_figure(
        kf, "fed",
        display=f"{de(lo[-1][1], 2)}–{de(hi[-1][1], 2)} %",
        period=f"seit {ddmmyyyy(since(hi))}",
    )
    changed |= save("key_figures", kf)
    print(f"rates: EZB MRO {mro[-1]}, Fed eff. {ff[-1]}, geändert={changed}")
    return changed


if __name__ == "__main__":
    run()
