"""Führt alle Updater aus. Ein Fehler in einer Quelle stoppt die anderen nicht.
Exit-Code 1, wenn mindestens eine Quelle fehlschlug (Workflow wird dann rot, committet aber trotzdem)."""
import sys
import traceback

import update_bund
import update_news
import update_polls
import update_rates
from common import now_iso, save

failed = []
for name, mod in [("bund", update_bund), ("rates", update_rates), ("polls", update_polls), ("news", update_news)]:
    try:
        mod.run()
    except Exception:  # noqa: BLE001
        failed.append(name)
        print(f"::error::Update '{name}' fehlgeschlagen")
        traceback.print_exc()

if len(failed) < 4:
    save("meta", {"updated": now_iso()})
sys.exit(1 if failed else 0)
