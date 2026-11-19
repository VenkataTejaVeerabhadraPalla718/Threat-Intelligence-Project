"""Run scheduled incremental RSS synchronization. Use --once for a single sync."""
import argparse, os, time, logging
from ingest import sync_once
from common import db
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    default_interval = max(5, int(os.getenv("SYNC_INTERVAL_MINUTES", "15"))) * 60
    while True:
        try:
            logging.info("Starting incremental feed verification/sync")
            result = sync_once()
            logging.info("Sync summary: %s", result)
        except Exception:
            logging.exception("Sync failed; existing database records were not deleted")
        if args.once: break
        try:
            configured = db.platform_settings.find_one({"_id": "sync"}) or {}
            interval = int(configured.get("interval_seconds", default_interval))
        except Exception:
            interval = default_interval
        interval = interval if interval in {10, 30, 60, 300, 600, 1800} else default_interval
        logging.info("Next sync in %s seconds", interval)
        # Poll settings in short slices so a dashboard interval change takes effect promptly.
        remaining = interval
        while remaining > 0:
            step = min(5, remaining)
            time.sleep(step)
            remaining -= step
            try:
                latest = db.platform_settings.find_one({"_id": "sync"}) or {}
                new_interval = int(latest.get("interval_seconds", interval))
                if new_interval in {10, 30, 60, 300, 600, 1800} and new_interval != interval:
                    logging.info("Sync interval changed to %s seconds", new_interval)
                    interval = new_interval
                    remaining = interval
            except Exception:
                pass
if __name__ == "__main__": main()
