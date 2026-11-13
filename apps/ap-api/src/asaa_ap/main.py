from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from asaa_ap.api import router as ap_router
from asaa_ap.purchase_requests import router as purchase_requests_router
from asaa_ap.ar_api import router as ar_router
from asaa_people.api import hr_router, onboarding_router, payroll_router
from asaa_people.lifecycle import router as hr_lifecycle_router
from asaa_people.workflows import router as people_workflows_router
from asaa_ap.config import get_settings
from asaa_governance.api import router as master_data_router
from asaa_governance.authority import router as governance_router
from asaa_governance.administration import router as administration_router
from asaa_governance.authorization import router as authorization_router
from asaa_workforce_finance.api import router as workforce_finance_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)
app.include_router(ap_router)
app.include_router(purchase_requests_router)
app.include_router(ar_router)
app.include_router(hr_router)
app.include_router(hr_lifecycle_router)
app.include_router(onboarding_router)
app.include_router(payroll_router)
app.include_router(people_workflows_router)
app.include_router(master_data_router)
app.include_router(governance_router)
app.include_router(administration_router)
app.include_router(authorization_router)
app.include_router(workforce_finance_router)


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "service": "asaa-enterprise-api"}
