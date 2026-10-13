"""Tests mit Beispieldaten (kein Netzwerk). Aufruf: python -m unittest test_updaters -v"""
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import common  # noqa: E402
import update_bund  # noqa: E402
import update_polls  # noqa: E402
import update_rates  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "data").mkdir()
        for f in ROOT.glob("*.json"):
            shutil.copy(f, self.tmp / "data" / f.name)
        self._orig = common.DATA
        common.DATA = self.tmp / "data"

    def tearDown(self):
        common.DATA = self._orig
        shutil.rmtree(self.tmp)


CSV = '''"",BBSSY.D.REN.EUR.A630.000000WT1010.A,BBSSY.D.REN.EUR.A630.000000WT1010.A_FLAGS
"",Daily yield of the current 10 year federal bond,
unit,PROZENT,
last update,2026-10-14 12:57:29,
2026-10-09,3.47,
2026-10-10,.,No value available
2026-10-12,3.46,
2026-10-13,3.40,
2026-10-14,3.38,
'''

PDF_TXT = """Rendite der jeweils jüngsten Bundeswertpapiere
Monat Tag 1 2 5 10
Okt. 12. 3,83 3,83 3,72 3,46 3,35 3,24 3,11
Okt. 13. 3,80 3,80 3,70 3,40 3,33 3,22 3,10
Okt. 14. 3,79 3,78 3,69 3,38 3,31 3,20 3,09
Okt. 15. 3,75 3,75 3,65 3,37 3,30 3,19 3,08
"""


class TestBund(Base):
    def test_parse_csv(self):
        rows, upd = update_bund.parse_csv(CSV)
        self.assertEqual(rows["2026-10-12"], 3.46)
        self.assertNotIn("2026-10-10", rows)
        self.assertEqual(upd, "2026-10-14 12:57:29")

    def test_parse_pdf_year_inference(self):
        v = update_bund.parse_pdf_text(PDF_TXT, date(2026, 10, 15))
        self.assertEqual(v["2026-10-15"], 3.37)
        self.assertEqual(v["2026-10-12"], 3.46)
        v = update_bund.parse_pdf_text("Dez. 30. 2,85 2,85 2,85 2,85 2,0 2,0 2,0\nJan. 2. 2,87 2,87 2,87 2,87 2,0 2,0 2,0\n".replace("2,0", "2,00"), date(2026, 1, 5))
        self.assertEqual(sorted(v), ["2025-12-30", "2026-01-02"])

    def test_run_merges_csv_and_pdf(self):
        update_bund.run(today=date(2026, 10, 15), csv_text=CSV, pdf_values={"2026-10-15": 3.37, "2026-10-13": 9.99})
        rows = json.loads((common.DATA / "bund_daily.json").read_text())
        by = {r["date"]: r["y10"] for r in rows}
        self.assertEqual(by["2026-10-13"], 3.40)  # CSV hat Vorrang vor PDF
        self.assertEqual(by["2026-10-15"], 3.37)  # PDF füllt nach CSV-Ende auf
        self.assertEqual(rows[0]["date"], "2025-10-16")  # 12-Monats-Fenster
        kf = {r["id"]: r for r in json.loads((common.DATA / "key_figures.json").read_text())}
        self.assertIn("3,37 %", kf["bund10"]["display"])


ECB_MRO = "KEY,FREQ,TIME_PERIOD,OBS_VALUE\nX,D,2026-09-10,2.40\nX,D,2026-09-16,2.65\nX,D,2026-10-12,2.65\n"
ECB_DFR = "KEY,FREQ,TIME_PERIOD,OBS_VALUE\nX,D,2026-09-10,2.25\nX,D,2026-09-16,2.50\nX,D,2026-10-12,2.50\n"
ECB_MLF = "KEY,FREQ,TIME_PERIOD,OBS_VALUE\nX,D,2026-09-10,2.65\nX,D,2026-09-16,2.90\nX,D,2026-10-12,2.90\n"
FF = "observation_date,FEDFUNDS\n2026-08-01,3.63\n2026-09-01,3.75\n2026-10-01,.\n"
LO = "observation_date,DFEDTARL\n2026-09-15,3.50\n2026-09-16,3.75\n2026-10-12,3.75\n"
HI = "observation_date,DFEDTARU\n2026-09-15,3.75\n2026-09-16,4.00\n2026-10-12,4.00\n"


class TestRates(Base):
    def test_run(self):
        update_rates.run(today=date(2026, 11, 3), texts={"MRR_FR": ECB_MRO, "DFR": ECB_DFR, "MLFR": ECB_MLF,
                                                         "FEDFUNDS": FF, "DFEDTARL": LO, "DFEDTARU": HI})
        rows = json.loads((common.DATA / "macro_monthly.json").read_text())
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[-1]["month"], "2026-11")  # neuer Monat angehängt
        self.assertEqual(rows[0]["month"], "2025-12")  # ältester Monat fällt weg
        by = {r["month"]: r for r in rows}
        self.assertEqual(by["2026-09"]["ecb_mro"], 2.65)
        self.assertEqual(by["2026-09"]["fed_eff"], 3.75)
        self.assertEqual(by["2026-11"]["ecb_mro"], 2.65)
        self.assertIsNone(by["2026-11"]["fed_eff"])
        self.assertEqual(by["2026-09"]["inflation"], 3.3)  # manuelle Werte bleiben erhalten
        kf = {r["id"]: r for r in json.loads((common.DATA / "key_figures.json").read_text())}
        self.assertEqual(kf["ecb"]["display"], "2,50 % (2,65 % / 2,90 %)")
        self.assertEqual(kf["ecb"]["period"], "seit 16.09.2026")
        self.assertEqual(kf["fed"]["display"], "3,75–4,00 %")


API = {
    "Parliaments": {"0": {"Shortcut": "Bundestag"}, "1": {"Shortcut": "Baden-Württemberg"}},
    "Institutes": {"1": {"Name": "Allensbach"}, "2": {"Name": "Infratest dimap"}},
    "Parties": {"1": {"Shortcut": "CDU/CSU"}, "2": {"Shortcut": "SPD"}, "3": {"Shortcut": "GRÜNE"}, "4": {"Shortcut": "FDP"},
                "5": {"Shortcut": "DIE LINKE"}, "6": {"Shortcut": "AfD"}, "7": {"Shortcut": "BSW"}, "9": {"Shortcut": "Sonstige"}},
    "Surveys": {
        "10": {"Date": "2026-11-05", "Institute_ID": "2", "Parliament_ID": "0", "Results": {"1": 24.0, "2": 13.0, "3": 12.0, "5": 11.0, "6": 28.0, "9": 12.0}},
        "11": {"Date": "2026-11-19", "Institute_ID": "2", "Parliament_ID": "0", "Results": {"1": 99.0, "6": 99.0}},
        "12": {"Date": "2026-11-02", "Institute_ID": "1", "Parliament_ID": "0", "Results": {"1": 1.0}},
        "13": {"Date": "2026-11-03", "Institute_ID": "2", "Parliament_ID": "1", "Results": {"1": 2.0}},
    },
}


class TestPolls(Base):
    def test_run(self):
        update_polls.run(api_text=json.dumps(API))
        rows = json.loads((common.DATA / "polls.json").read_text())
        self.assertEqual(len(rows), 13)
        last = rows[-1]
        self.assertEqual((last["month"], last["published"], last["afd"], last["cdu_csu"]), ("2026-11", "2026-11-05", 28, 24))
        self.assertIsNone(last["fdp"])
        self.assertEqual(rows[0]["month"], "2025-11")


if __name__ == "__main__":
    unittest.main()
