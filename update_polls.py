"""Sonntagsfrage (Bundestag, Infratest dimap) -> data/polls.json

Quelle: DAWUM-API (https://api.dawum.de/), frei nutzbar, enthält die Umfragen der großen Institute.
Je Monat wird die erste Umfrage von Infratest dimap übernommen. Bereits gespeicherte frühere Monate
bleiben unverändert (nur der letzte gespeicherte und neue Monate werden aus der API gesetzt).
"""
import json
from datetime import date

from common import MON, http_get, load, save

URL = "https://api.dawum.de/"
KEYS = {
    "cdu/csu": "cdu_csu", "spd": "spd", "grüne": "gruene", "bündnis 90/die grünen": "gruene",
    "fdp": "fdp", "die linke": "linke", "linke": "linke", "afd": "afd", "bsw": "bsw", "sonstige": "sonstige",
}
WINDOW = 13


def first_per_month(api):
    parl = {k for k, v in api["Parliaments"].items() if v.get("Shortcut", "").lower() == "bundestag"}
    inst = {k for k, v in api["Institutes"].items() if "infratest" in v.get("Name", "").lower()}
    parties = {k: KEYS.get(v.get("Shortcut", "").lower()) for k, v in api["Parties"].items()}
    best = {}
    for s in api["Surveys"].values():
        if str(s.get("Parliament_ID")) not in parl or str(s.get("Institute_ID")) not in inst:
            continue
        d = s["Date"]
        mo = d[:7]
        if mo not in best or d < best[mo][0]:
            best[mo] = (d, s["Results"])
    out = {}
    for mo, (d, res) in best.items():
        row = {"month": mo, "label": f"{MON[int(mo[5:]) - 1]} {mo[2:4]}", "published": d,
               "cdu_csu": None, "spd": None, "gruene": None, "fdp": None, "linke": None, "afd": None, "bsw": None, "sonstige": None}
        for pid, val in res.items():
            key = parties.get(str(pid))
            if key:
                row[key] = round(float(val))
        out[mo] = row
    return out


def run(api_text=None, today=None):
    api = json.loads(api_text if api_text is not None else http_get(URL))
    new = first_per_month(api)
    if not new:
        raise RuntimeError("DAWUM lieferte keine Infratest-dimap-Umfragen für den Bundestag")
    rows = {r["month"]: r for r in load("polls")}
    last_have = max(rows) if rows else ""
    for mo, r in new.items():
        if mo >= last_have or mo not in rows:
            rows[mo] = r
    months = sorted(rows)[-WINDOW:]
    out = [rows[m] for m in months]
    changed = save("polls", out)
    print(f"polls: {len(out)} Monate, letzter {out[-1]['label']} ({out[-1]['published']}), geändert={changed}")
    return changed


if __name__ == "__main__":
    run()
