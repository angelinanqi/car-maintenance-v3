"""Run from the repository root with python -m backend."""
import uvicorn

from backend.settings import BACKEND_HOST, BACKEND_PORT

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=BACKEND_HOST, port=BACKEND_PORT)
