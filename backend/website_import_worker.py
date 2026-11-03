"""Run one browser capture at a time; Supabase owns the persistent queue."""
import logging
import signal
from threading import Event

from backend import settings
from backend.services.website_imports import run_once


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(name)s: %(message)s')
    from shared.observability import configure, ready, shutdown
    import atexit
    configure('website-worker')
    atexit.register(shutdown)
    ready()
    stop = Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    if not settings.WEBSITE_IMPORT_ENABLED:
        return
    while not stop.is_set():
        try:
            worked = run_once(stop)
        except Exception:
            logging.getLogger(__name__).exception('Website queue unavailable; apply its migration and check Supabase')
            worked = False
        stop.wait(1 if worked else 10)


if __name__ == '__main__':
    main()
