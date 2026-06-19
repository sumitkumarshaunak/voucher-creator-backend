import os

import uvicorn

from app import app

__all__ = ["app"]


if __name__ == "__main__":
    host = os.environ.get("BACKEND_HOST", "0.0.0.0")
    port = int(os.environ.get("BACKEND_PORT", "8000"))
    uvicorn.run("server:app", host=host, port=port, reload=False)
