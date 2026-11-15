"""Register catalogue: which register types exist, which portal workspace shows them and which extra fields they accept.

Field kinds: str, int, bool, date (YYYY-MM-DD), enum (with choices), ref (a reference NAME such as a secret-store key, never a secret),
strlist and transitions (workflow definitions only). Unknown fields are rejected so records cannot smuggle arbitrary data.
These registers record governance information; they do not enforce it (for example a retention rule is not an automatic deletion job).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

REF_NAME = re.compile(r"^[A-Za-z0-9_.:/-]{1,100}$")
STATE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]{0,39}$")


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    label: str
    required: bool = False
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegisterType:
    key: str
    workspace: str
    label: str
    plural: str
    fields: tuple[Field, ...] = field(default_factory=tuple)


SEVERITY = ("Low", "Medium", "High", "Critical")
TYPES: dict[str, RegisterType] = {t.key: t for t in [
    RegisterType("policy", "Policies & procedures", "Policy or procedure", "Policies and procedures", (
        Field("document_type", "enum", "Document type", True, ("Policy", "Procedure", "Standard", "Guideline")),
        Field("scope", "str", "Scope"), Field("acknowledgement_required", "bool", "Acknowledgement required"))),
    RegisterType("risk", "Risk & internal controls", "Risk", "Risks", (
        Field("category", "str", "Category"), Field("likelihood", "enum", "Likelihood", True, ("Low", "Medium", "High")),
        Field("impact", "enum", "Impact", True, ("Low", "Medium", "High")), Field("mitigation", "str", "Mitigation"))),
    RegisterType("control", "Risk & internal controls", "Internal control", "Internal controls", (
        Field("control_type", "enum", "Control type", True, ("Preventive", "Detective", "Corrective")),
        Field("frequency", "enum", "Frequency", True, ("Continuous", "Daily", "Weekly", "Monthly", "Quarterly", "Annual")),
        Field("related_risk_code", "str", "Related risk code"))),
    RegisterType("obligation", "Compliance & obligations", "Compliance obligation", "Compliance obligations", (
        Field("source", "str", "Source (regulation, contract, standard)", True), Field("jurisdiction", "str", "Jurisdiction (only once confirmed)"),
        Field("evidence_reference", "str", "Evidence reference"))),
    RegisterType("contract", "Legal contracts", "Contract", "Contracts", (
        Field("counterparty", "str", "Counterparty", True),
        Field("contract_type", "enum", "Contract type", True, ("Customer", "Supplier", "Employment", "Partnership", "Other")),
        Field("renewal_date", "date", "Renewal date"), Field("auto_renew", "bool", "Auto-renews"))),
    RegisterType("retention_rule", "Privacy & data retention", "Retention rule", "Retention rules", (
        Field("data_category", "str", "Data category", True), Field("retention_period_months", "int", "Retention period (months)", True),
        Field("legal_basis", "str", "Legal basis (once confirmed)"),
        Field("disposal_method", "enum", "Disposal method", True, ("Delete", "Anonymise", "Archive")))),
    RegisterType("article", "Knowledge base", "Knowledge article", "Knowledge articles", (
        Field("space", "str", "Space or collection"), Field("tags", "str", "Tags (comma separated)"))),
    RegisterType("announcement", "Announcements & communication", "Announcement", "Announcements", (
        Field("audience", "str", "Audience", True), Field("publish_on", "date", "Publish on"))),
    RegisterType("integration", "Integrations & connectors", "Integration", "Integrations", (
        Field("kind", "enum", "Kind", True, ("Identity", "Finance", "Payroll", "Messaging", "Storage", "Other")),
        Field("credential_reference", "ref", "Credential reference (name in the secret store, never the secret)"),
        Field("health_status", "enum", "Health", True, ("Unknown", "Healthy", "Degraded", "Failing")),
        Field("last_sync_note", "str", "Last sync note"))),
    RegisterType("workflow_definition", "Workflow & approvals", "Workflow definition", "Workflow definitions", (
        Field("initial_state", "str", "Initial state", True), Field("states", "strlist", "States", True),
        Field("transitions", "transitions", "Transitions (from, to, action, optional permission)", True))),
    RegisterType("security_incident", "Security operations", "Security incident", "Security incidents", (
        Field("severity", "enum", "Severity", True, SEVERITY), Field("detected_on", "date", "Detected on"), Field("containment", "str", "Containment"))),
    RegisterType("operational_incident", "Operational incidents", "Operational incident", "Operational incidents", (
        Field("severity", "enum", "Severity", True, SEVERITY), Field("service", "str", "Affected service"), Field("detected_on", "date", "Detected on"))),
]}


# Record-keeping registers for the remaining planned workspaces. They capture owned, versioned, reviewed records only; the domain
# workflows (scheduling, pipelines, recruiting stages, forecasting ...) are NOT implemented by them.
STATUS3 = ("Planned", "Active", "Closed")
_MORE = [
    RegisterType("document", "Documents & records", "Document record", "Document records", (
        Field("document_type", "str", "Document type", True),
        Field("classification", "enum", "Classification", True, ("Public", "Internal", "Confidential", "Restricted")),
        Field("storage_reference", "ref", "Storage reference (name/key in approved storage, never a link with a secret)"),
        Field("retention_until", "date", "Retain until"), Field("legal_hold", "bool", "Legal hold"))),
    RegisterType("project", "Portfolio & projects", "Project", "Projects", (
        Field("project_status", "enum", "Project status", True, STATUS3), Field("sponsor", "str", "Sponsor"),
        Field("start_date", "date", "Start date"), Field("end_date", "date", "End date"))),
    RegisterType("requirement", "Requirements & roadmaps", "Requirement", "Requirements", (
        Field("priority", "enum", "Priority", True, ("P0", "P1", "P2")), Field("acceptance_criteria", "str", "Acceptance criteria"),
        Field("target_release", "str", "Target release"))),
    RegisterType("product", "Products & lifecycle", "Product", "Products", (
        Field("lifecycle_stage", "enum", "Lifecycle stage", True, ("Discovery", "Build", "Live", "Sunset", "Retired")), Field("product_owner", "str", "Product owner"))),
    RegisterType("repository", "Repositories & engineering", "Repository", "Repositories", (
        Field("host", "str", "Host (e.g. github.com)"), Field("default_branch", "str", "Default branch"), Field("owning_team", "str", "Owning team"))),
    RegisterType("test_plan", "QA & testing", "Test plan", "Test plans", (
        Field("scope", "str", "Scope", True), Field("last_run_result", "enum", "Last run result", False, ("Not run", "Passed", "Failed")))),
    RegisterType("pipeline", "CI/CD & pipelines", "Pipeline", "Pipelines", (
        Field("system", "str", "CI/CD system", True), Field("last_status", "enum", "Last status", False, ("Unknown", "Passing", "Failing")))),
    RegisterType("environment", "Environments & architecture", "Environment", "Environments", (
        Field("kind", "enum", "Kind", True, ("Development", "Test", "Staging", "Production")), Field("hosting_reference", "str", "Hosting reference"))),
    RegisterType("release", "Releases & artifacts", "Release", "Releases", (
        Field("version_label", "str", "Version", True), Field("commit_reference", "str", "Commit reference"),
        Field("release_status", "enum", "Release status", True, ("Planned", "Released", "Rolled back")))),
    RegisterType("technical_article", "Technical knowledge", "Technical article", "Technical articles", (
        Field("component", "str", "Component"), Field("tags", "str", "Tags (comma separated)"))),
    RegisterType("service", "Service catalogue", "Service", "Services", (
        Field("service_owner", "str", "Service owner", True), Field("support_hours", "str", "Support hours"))),
    RegisterType("engagement", "Client delivery", "Client engagement", "Client engagements", (
        Field("client", "str", "Client", True), Field("engagement_status", "enum", "Status", True, STATUS3))),
    RegisterType("work_order", "Work orders & scheduling", "Work order", "Work orders", (
        Field("assignee", "str", "Assignee"), Field("scheduled_for", "date", "Scheduled for"), Field("work_status", "enum", "Status", True, ("Open", "In progress", "Done")))),
    RegisterType("sla", "Support & SLAs", "Service level definition", "Service level definitions", (
        Field("response_target_minutes", "int", "Response target (minutes)", True), Field("resolution_target_minutes", "int", "Resolution target (minutes)"))),
    RegisterType("inventory_item", "Inventory & stock", "Inventory item", "Inventory items", (
        Field("sku", "str", "SKU", True), Field("quantity_on_hand", "int", "Quantity on hand", True), Field("location", "str", "Location"))),
    RegisterType("facility_request", "Facilities, travel & logistics", "Facilities or travel request", "Facilities and travel requests", (
        Field("request_kind", "enum", "Kind", True, ("Facility", "Travel", "Logistics")), Field("needed_by", "date", "Needed by"))),
    RegisterType("account", "CRM & customer accounts", "Customer account", "Customer accounts", (
        Field("segment", "str", "Segment"), Field("account_owner", "str", "Account owner", True))),
    RegisterType("lead", "Leads & sales pipeline", "Lead", "Leads", (
        Field("source", "str", "Source"), Field("stage", "enum", "Stage", True, ("New", "Qualified", "Proposal", "Won", "Lost")))),
    RegisterType("proposal", "Proposals & quotations", "Proposal", "Proposals", (
        Field("customer", "str", "Customer", True), Field("valid_until", "date", "Valid until"))),
    RegisterType("order", "Orders & subscriptions", "Order or subscription", "Orders and subscriptions", (
        Field("customer", "str", "Customer", True), Field("order_kind", "enum", "Kind", True, ("Order", "Subscription")))),
    RegisterType("feedback", "Customer onboarding & feedback", "Customer feedback", "Customer feedback", (
        Field("customer", "str", "Customer"), Field("sentiment", "enum", "Sentiment", False, ("Positive", "Neutral", "Negative")))),
    RegisterType("campaign", "Marketing & campaigns", "Campaign", "Campaigns", (
        Field("channel", "str", "Channel"), Field("campaign_status", "enum", "Status", True, STATUS3))),
    RegisterType("team_space", "Team spaces & collaboration", "Team space", "Team spaces", (
        Field("purpose", "str", "Purpose"), Field("space_owner", "str", "Owner", True))),
    RegisterType("meeting", "Calendar & meetings", "Meeting record", "Meeting records", (
        Field("meeting_date", "date", "Meeting date", True), Field("attendees", "str", "Attendees"), Field("decisions", "str", "Decisions"), Field("action_items", "str", "Action items"))),
    RegisterType("form_request", "Forms & service requests", "Service request", "Service requests", (
        Field("request_type", "str", "Request type", True), Field("requested_by", "str", "Requested by"))),
    RegisterType("vacancy", "Recruitment", "Vacancy", "Vacancies", (
        Field("department", "str", "Department"), Field("headcount", "int", "Headcount", True))),
    RegisterType("goal", "Performance & learning", "Goal or development plan", "Goals and development plans", (
        Field("goal_owner", "str", "Goal owner", True), Field("due_date", "date", "Due date"))),
]
_MORE2 = [
    RegisterType("budget", "Budgets & forecasting", "Budget line", "Budget lines", (
        Field("fiscal_period", "str", "Fiscal period (e.g. 2027-Q1)", True), Field("currency", "currency", "Currency (ISO code)", True),
        Field("planned_amount", "money", "Planned amount", True), Field("cost_centre", "str", "Cost centre"))),
    RegisterType("scenario", "Forecasting & scenarios", "Forecast scenario", "Forecast scenarios", (
        Field("horizon", "str", "Horizon (e.g. 12 months)", True), Field("assumptions", "str", "Assumptions (stated explicitly)", True),
        Field("uncertainty_note", "str", "Uncertainty and limits of this scenario", True), Field("method", "str", "Method used"))),
    RegisterType("automation", "Automation & agents", "Automation definition", "Automation definitions", (
        Field("trigger", "str", "Trigger", True), Field("action", "str", "Action", True), Field("scope", "str", "Scope of data and systems", True),
        Field("execution_mode", "enum", "Execution mode (live execution is not available)", True, ("Disabled", "Dry-run only")),
        Field("stop_procedure", "str", "How to stop it", True))),
    RegisterType("shift_roster", "Attendance & shifts", "Shift or attendance record", "Shift and attendance records", (
        Field("employee_subject", "str", "Employee (identity subject)", True), Field("shift_date", "date", "Date", True),
        Field("start_time", "str", "Start (HH:MM)"), Field("end_time", "str", "End (HH:MM)"),
        Field("arrangement", "enum", "Arrangement", True, ("Office", "Remote", "Hybrid", "Field")))),
    RegisterType("recovery_plan", "Backup & recovery", "Recovery plan", "Recovery plans", (
        Field("system", "str", "System", True), Field("rpo_minutes", "int", "RPO (minutes) - pending owner approval"),
        Field("rto_minutes", "int", "RTO (minutes) - pending owner approval"), Field("runbook_reference", "str", "Runbook reference"))),
]
_MORE3 = [
    RegisterType("er_case", "Employee relations", "Employee relations case", "Employee relations cases", (
        Field("case_type", "enum", "Case type", True, ("Grievance", "Investigation", "Appeal", "Other")),
        Field("case_stage", "enum", "Stage", True, ("Opened", "Investigating", "Findings recorded", "Appeal", "Closed")),
        Field("investigator_subject", "str", "Authorised investigator (identity subject)"),
        Field("next_milestone", "str", "Next milestone"), Field("milestone_due", "date", "Milestone due"),
        Field("outcome_note", "str", "Outcome note (no evidence text here)"))),
    RegisterType("ai_use_case", "AI intelligence", "AI use case", "AI use cases", (
        Field("purpose", "str", "Purpose", True), Field("approved_sources", "str", "Approved data sources", True),
        Field("human_review_required", "bool", "Human review of every output (must be on)", True),
        Field("provenance_required", "bool", "Outputs must cite sources", True),
        Field("deployment_mode", "enum", "Mode (no model is connected; live use is not available)", True, ("Disabled", "Evaluation only")),
        Field("risk_note", "str", "Risk and limits", True))),
]
TYPES.update({t.key: t for t in _MORE})
TYPES.update({t.key: t for t in _MORE3})
TYPES.update({t.key: t for t in _MORE2})


class DataError(ValueError):
    pass


def validate_data(register_type: str, data: dict) -> dict:
    """Return the cleaned data dict or raise DataError."""
    spec = TYPES[register_type]
    known = {f.name: f for f in spec.fields}
    unknown = set(data) - set(known)
    if unknown:
        raise DataError("unknown fields: " + ", ".join(sorted(unknown)))
    cleaned: dict = {}
    for f in spec.fields:
        value = data.get(f.name)
        if value in (None, ""):
            if f.required:
                raise DataError(f"{f.name} is required")
            continue
        if f.kind == "str":
            if not isinstance(value, str) or len(value) > 500:
                raise DataError(f"{f.name} must be text up to 500 characters")
        elif f.kind == "int":
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1200:
                raise DataError(f"{f.name} must be a whole number between 0 and 1200")
        elif f.kind == "money":
            try:
                amount = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise DataError(f"{f.name} must be a decimal amount") from None
            if not amount.is_finite() or amount < 0 or amount > Decimal("999999999999.99") or amount != amount.quantize(Decimal("0.01")):
                raise DataError(f"{f.name} must be a non-negative amount with at most 2 decimal places")
            value = str(amount.quantize(Decimal("0.01")))
        elif f.kind == "currency":
            if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value):
                raise DataError(f"{f.name} must be a 3-letter ISO currency code in capitals")
        elif f.kind == "bool":
            if not isinstance(value, bool):
                raise DataError(f"{f.name} must be true or false")
        elif f.kind == "date":
            try:
                date.fromisoformat(value)
            except (TypeError, ValueError):
                raise DataError(f"{f.name} must be a date (YYYY-MM-DD)") from None
        elif f.kind == "enum":
            if value not in f.choices:
                raise DataError(f"{f.name} must be one of: " + ", ".join(f.choices))
        elif f.kind == "ref":
            if not isinstance(value, str) or not REF_NAME.match(value):
                raise DataError(f"{f.name} must be a reference name (letters, digits, . _ : / -), not a secret value")
        elif f.kind == "strlist":
            if not isinstance(value, list) or not value or len(value) > 30 or not all(isinstance(v, str) and STATE_NAME.match(v) for v in value) or len(set(value)) != len(value):
                raise DataError(f"{f.name} must be a list of 1-30 unique state names")
        elif f.kind == "transitions":
            if not isinstance(value, list) or not value or len(value) > 100:
                raise DataError("transitions must be a list of 1-100 transitions")
            for t in value:
                if not isinstance(t, dict) or set(t) - {"from", "to", "action", "permission"} or not {"from", "to", "action"} <= set(t):
                    raise DataError("each transition needs from, to, action (and optionally permission)")
                if not all(isinstance(t[k], str) and t[k] for k in ("from", "to", "action")):
                    raise DataError("transition fields must be non-empty text")
        cleaned[f.name] = value
    if register_type == "ai_use_case" and not (cleaned.get("human_review_required") is True and cleaned.get("provenance_required") is True):
        raise DataError("AI use cases must require human review and source provenance")
    if register_type == "workflow_definition":
        states = set(cleaned["states"])
        if cleaned["initial_state"] not in states:
            raise DataError("initial_state must be one of the states")
        seen = set()
        for t in cleaned["transitions"]:
            if t["from"] not in states or t["to"] not in states:
                raise DataError("transitions may only reference declared states")
            key = (t["from"], t["action"])
            if key in seen:
                raise DataError(f"duplicate action {t['action']!r} from state {t['from']!r}")
            seen.add(key)
        reachable, frontier = {cleaned["initial_state"]}, [cleaned["initial_state"]]
        while frontier:
            node = frontier.pop()
            for t in cleaned["transitions"]:
                if t["from"] == node and t["to"] not in reachable:
                    reachable.add(t["to"])
                    frontier.append(t["to"])
        if states - reachable:
            raise DataError("unreachable states: " + ", ".join(sorted(states - reachable)))
    return cleaned


def describe() -> list[dict]:
    return [{"key": t.key, "workspace": t.workspace, "label": t.label, "plural": t.plural,
             "fields": [{"name": f.name, "kind": f.kind, "label": f.label, "required": f.required, "choices": list(f.choices)} for f in t.fields]}
            for t in TYPES.values()]
