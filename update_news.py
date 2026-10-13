"""Die drei neuesten wirtschaftspolitischen Meldungen (höchstens 7 Tage alt) -> news.json

Quellen: RSS-Feeds (FEEDS unten). Ein Feed, der nicht erreichbar ist, wird übersprungen.
Auswahl: Stichwortfilter (Politik UND Wirtschaft müssen vorkommen), Gewicht nach Quelle und Aktualität,
höchstens zwei Meldungen je Quelle. Das ist eine grobe Auswahl und kein redaktionelles Urteil.
Fehlen neue Treffer, bleiben noch nicht abgelaufene bisherige Meldungen stehen.
"""
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from common import http_get, load, save

# (Anzeigename, URL, Quellengewicht) – Primärquellen zählen mehr
FEEDS = [
    ("Destatis", "https://www.destatis.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/Aktuell.xml", 3),
    ("tagesschau", "https://www.tagesschau.de/wirtschaft/index~rss2.xml", 2),
]
MAX_AGE_DAYS = 7
N = 3

POLITIK = ["bundesregierung", "regierung", "koalition", "bundestag", "bundesrat", "kabinett", "gesetz", "minister",
           "kanzler", "merz", "klingbeil", "reiche", "haushalt", "steuer", "schuldenbremse", "sondervermögen",
           "förder", "subvention", "eu-kommission", "bundesbank", "ezb", "zentralbank", "tarif", "mindestlohn",
           "bürgergeld", "rente", "zölle", "zoll", "handelsabkommen", "sanktion", "abgabe", "entlastung", "iwf"]
WIRTSCHAFT = ["wirtschaft", "konjunktur", "wachstum", "inflation", "preise", "zins", "arbeitsmarkt", "arbeitslos",
              "industrie", "unternehmen", "export", "import", "energie", "strom", "gas", "netzentgelt", "co2",
              "investition", "schulden", "defizit", "bip", "prognose", "ifo", "zew", "rezession", "haushalt", "steuer",
              "mittelstand", "lieferkette", "handel", "bürgergeld", "rente", "mindestlohn"]
TAGS = [
    ("Energie & Klima", ["energie", "strom", "gas", "netzentgelt", "co2", "klima", "emission"]),
    ("Geldpolitik", ["ezb", "zins", "bundesbank", "zentralbank", "leitzins"]),
    ("Haushalt & Steuern", ["haushalt", "steuer", "schulden", "defizit", "schuldenbremse", "sondervermögen"]),
    ("Konjunktur", ["konjunktur", "prognose", "wachstum", "bip", "ifo", "zew", "rezession", "inflation"]),
    ("Arbeit & Soziales", ["arbeitsmarkt", "arbeitslos", "rente", "mindestlohn", "bürgergeld", "tarif"]),
    ("Handel & Zölle", ["zoll", "zölle", "export", "handelsabkommen", "sanktion"]),
]


def _text(el, *names):
    for n in names:
        for child in el:
            if child.tag.split("}")[-1] == n and (child.text or "").strip():
                return child.text.strip()
    return ""


def _link(el):
    for child in el:
        if child.tag.split("}")[-1] == "link":
            if child.text and child.text.strip():
                return child.text.strip()
            if child.get("href"):
                return child.get("href")
    return ""


def _date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def clean(s, n=None):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    if n and len(s) > n:
        s = s[:n].rsplit(" ", 1)[0].rstrip(",;:") + " …"
    return s


def parse_feed(xml_text, name, weight):
    root = ET.fromstring(xml_text.lstrip())
    items = [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]
    out = []
    for it in items:
        title = clean(_text(it, "title"))
        link = _link(it)
        d = _date(_text(it, "pubDate", "published", "updated", "date"))
        summ = clean(_text(it, "description", "summary", "encoded", "content"), 260)
        if title and link and d:
            out.append({"title": title, "url": link, "dt": d, "summary": summ, "source": name, "weight": weight})
    return out


def score(item, now):
    text = (item["title"] + " " + item["summary"]).lower()
    pol = sum(k in text for k in POLITIK)
    wirt = sum(k in text for k in WIRTSCHAFT)
    if pol == 0 or wirt == 0:
        return 0
    age_days = max((now - item["dt"]).total_seconds() / 86400, 0)
    fresh = 1 - min(age_days / MAX_AGE_DAYS, 1)  # 1 = gerade erschienen
    in_title = sum(k in item["title"].lower() for k in POLITIK + WIRTSCHAFT)
    return pol + wirt + 2 * in_title + 3 * item["weight"] + 4 * fresh


def tag_for(item):
    text = (item["title"] + " " + item["summary"]).lower()
    best, best_n = "Wirtschaftspolitik", 0
    for tag, keys in TAGS:
        n = sum(k in text for k in keys)
        if n > best_n:
            best, best_n = tag, n
    return best


def pick(items, now, n=N):
    fresh = [i for i in items if timedelta(0) <= now - i["dt"] <= timedelta(days=MAX_AGE_DAYS)]
    ranked = sorted(((score(i, now), i) for i in fresh), key=lambda t: t[0], reverse=True)
    chosen, per_source, seen = [], {}, set()
    for sc, i in ranked:
        if sc <= 0 or i["url"] in seen or per_source.get(i["source"], 0) >= 2:
            continue
        chosen.append(i)
        seen.add(i["url"])
        per_source[i["source"]] = per_source.get(i["source"], 0) + 1
        if len(chosen) == n:
            break
    return sorted(chosen, key=lambda i: i["dt"], reverse=True)


def to_row(i, idx, tz):
    d = i["dt"].astimezone(tz)
    return {"id": f"n{idx}", "date": d.date().isoformat(), "date_label": f"{d.day}.{d.month}.{d.year}",
            "tag": tag_for(i), "headline": i["title"], "summary": i["summary"], "source": i["source"], "url": i["url"]}


def run(now=None, feeds_xml=None):
    now = now or datetime.now(timezone.utc)
    tz = timezone(timedelta(hours=2 if 3 < now.month < 11 else 1))  # grob MESZ/MEZ, nur fürs Datumslabel
    items, errors = [], []
    for name, url, weight in FEEDS:
        try:
            xml_text = feeds_xml[name] if feeds_xml is not None else http_get(url)
            items += parse_feed(xml_text, name, weight)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    for e in errors:
        print(f"::warning::Feed nicht lesbar – {e}")
    if len(errors) == len(FEEDS):
        raise RuntimeError("Kein News-Feed erreichbar")

    chosen = pick(items, now)
    rows = [to_row(i, k + 1, tz) for k, i in enumerate(chosen)]
    if len(rows) < N:  # auffüllen mit noch gültigen bisherigen Meldungen
        have = {r["url"] for r in rows}
        old = [r for r in load("news") if r["url"] not in have
               and (now.date() - datetime.fromisoformat(r["date"]).date()).days <= MAX_AGE_DAYS]
        rows = sorted(rows + old, key=lambda r: r["date"], reverse=True)[:N]
        for k, r in enumerate(rows):
            r["id"] = f"n{k + 1}"
    if not rows:
        print("::warning::Keine aktuellen Meldungen gefunden; news.json bleibt unverändert.")
        return False
    changed = save("news", rows)
    print(f"news: {len(rows)} Meldungen, {len(items)} Kandidaten, geändert={changed}")
    return changed


if __name__ == "__main__":
    run()
