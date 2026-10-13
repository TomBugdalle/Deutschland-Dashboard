"""Gemeinsame Hilfen für die Update-Skripte (nur Standardbibliothek)."""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent
MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
UA = "Mozilla/5.0 (compatible; Deutschland-Dashboard-Updater; +https://github.com/TomBugdalle/Deutschland-Dashboard)"


def http_get(url, binary=False, timeout=60, retries=3):
    """GET mit Wiederholungen. Gibt str (utf-8) oder bytes zurück."""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            return raw if binary else raw.decode("utf-8-sig")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET {url} fehlgeschlagen: {last}")


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def save(name, obj):
    """Listen zeilenweise schreiben (saubere Git-Diffs), Objekte kompakt."""
    path = DATA / f"{name}.json"
    if isinstance(obj, list):
        text = "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in obj) + "\n]\n"
    else:
        text = json.dumps(obj, ensure_ascii=False) + "\n"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != text:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def de(v, d):
    """Zahl im deutschen Format (Komma)."""
    return f"{v:.{d}f}".replace(".", ",")


def ddmmyyyy(iso):
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def now_iso():
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def set_key_figure(rows, fid, **fields):
    for r in rows:
        if r["id"] == fid:
            r.update(fields)
            return True
    return False
