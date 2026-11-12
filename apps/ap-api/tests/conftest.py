import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from asaa_ap.database import Base, get_db
from asaa_ap.main import app
from asaa_ap.security import Principal, get_principal


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_principal] = lambda: Principal("tester", "org-a", frozenset({"supplier:read", "supplier:write", "supplier:status", "supplier:verify", "audit:read", "ar:customer:read", "ar:customer:write", "ar:invoice:read", "ar:invoice:write", "ar:invoice:issue", "ar:receipt:read", "ar:receipt:write", "ar:receipt:allocate", "hr:employee:read", "hr:employee:write", "hr:employment:write", "hr:employee:lifecycle", "onboarding:read", "onboarding:template:write", "onboarding:assignment:write", "onboarding:task:update", "payroll:compensation:read", "payroll:compensation:write", "payroll:period:write", "payroll:run:write", "payroll:entry:write", "payroll:read", "hr:document:read", "hr:document:write", "hr:asset:read", "hr:asset:write", "hr:leave:read", "hr:leave:request", "hr:leave:review", "hr:exit:read", "hr:exit:write", "hr:exit:complete", "onboarding:task:assign", "payroll:compensation:approve", "payroll:run:submit", "payroll:run:approve", "payroll:run:close"}))
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
