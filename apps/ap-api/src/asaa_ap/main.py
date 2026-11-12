from fastapi import FastAPI
from asaa_ap.api import router as ap_router
from asaa_ap.ar_api import router as ar_router
from asaa_people.api import hr_router, onboarding_router, payroll_router
from asaa_people.lifecycle import router as hr_lifecycle_router
from asaa_people.workflows import router as people_workflows_router
from asaa_ap.config import get_settings
from asaa_governance.api import router as master_data_router
from asaa_governance.authority import router as governance_router
from asaa_workforce_finance.api import router as workforce_finance_router

app = FastAPI(title=get_settings().app_name, version="0.4.0")
app.include_router(ap_router)
app.include_router(ar_router)
app.include_router(hr_router)
app.include_router(hr_lifecycle_router)
app.include_router(onboarding_router)
app.include_router(payroll_router)
app.include_router(people_workflows_router)
app.include_router(master_data_router)
app.include_router(governance_router)
app.include_router(workforce_finance_router)


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "service": "asaa-enterprise-api"}
