"""Run from the repository root with python -m backend."""
import logging

import uvicorn

from backend.settings import BACKEND_HOST, BACKEND_PORT

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(name)s: %(message)s')
    logging.getLogger('backend').setLevel(logging.INFO)
    uvicorn.run("backend.main:app", host=BACKEND_HOST, port=BACKEND_PORT)
