from fastapi import FastAPI
from asaa_ap.api import router as ap_router
from asaa_ap.ar_api import router as ar_router
from asaa_ap.config import get_settings

app = FastAPI(title=get_settings().app_name, version="0.2.0")
app.include_router(ap_router)
app.include_router(ar_router)


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "service": "asaa-finance-api"}
