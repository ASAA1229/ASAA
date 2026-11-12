from fastapi import FastAPI
from asaa_ap.api import router
from asaa_ap.config import get_settings

app = FastAPI(title=get_settings().app_name, version="0.1.0")
app.include_router(router)


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "service": "asaa-ap-api"}
