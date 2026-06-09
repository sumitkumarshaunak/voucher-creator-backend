from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import load_backend_env


def create_app():
    load_backend_env()

    app = FastAPI(title="Voucher Creator API")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=(
            r"^http://("
            r"localhost|"
            r"127\.0\.0\.1|"
            r"0\.0\.0\.0|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
            r"):\d+$"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
