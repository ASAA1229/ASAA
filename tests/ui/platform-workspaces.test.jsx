import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuditTrailWorkspace, GovernanceWorkspace, NotificationsWorkspace, ReportsWorkspace } from "../../src/PlatformWorkspaces.jsx";
import { axeViolations } from "./helpers.js";

const claims = (...p) => ({ permissions: p });
const router = routes => vi.fn(async (path, options = {}) => {
  const key = Object.keys(routes).find(k => `${options.method || "GET"} ${path}`.startsWith(k));
  if (!key) throw new Error(`unexpected ${options.method || "GET"} ${path}`);
  const r = routes[key];
  return typeof r === "function" ? r(options) : r;
});

describe("AuditTrailWorkspace", () => {
  const event = { id: "e1", created_at: "2026-11-14T10:00:00Z", actor_id: "alice", action: "supplier.created", entity_type: "supplier", entity_id: "s1", outcome: "success", details: { status: "Draft" }, correlation_id: null };

  it("is gated, then lists events, passes filters to the API, expands details and has no axe violations", async () => {
    const api = router({ "GET /api/v1/ap/audit-events": [event] });
    const { rerender, container } = render(<AuditTrailWorkspace api={api} claims={claims()} connected />);
    expect(screen.getByText("Access not granted")).toBeInTheDocument();
    expect(api).not.toHaveBeenCalled();
    rerender(<AuditTrailWorkspace api={api} claims={claims("audit:read")} connected />);
    expect(await screen.findByText("supplier.created")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Actor"), "alice");
    await waitFor(() => expect(api.mock.calls.some(([p]) => p.includes("actor_id=alice") && p.includes("offset=0"))).toBe(true));
    await userEvent.click(screen.getByRole("button", { name: /Details for supplier.created/ }));
    expect(screen.getByText(/"status": "Draft"/)).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("shows empty and error states", async () => {
    const empty = router({ "GET /api/v1/ap/audit-events": [] });
    const { unmount } = render(<AuditTrailWorkspace api={empty} claims={claims("audit:read")} connected />);
    expect(await screen.findByText("No audit events match")).toBeInTheDocument();
    unmount();
    const failing = vi.fn(async () => { throw new Error("boom"); });
    render(<AuditTrailWorkspace api={failing} claims={claims("audit:read")} connected />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});

describe("NotificationsWorkspace", () => {
  const dead = { id: "m1", created_at: "2026-11-14T10:00:00Z", recipient_subject: "bob", template_code: "x.y", status: "DeadLetter", attempts: 5, max_attempts: 5, last_error: "permanent: nope" };
  const base = { "GET /api/v1/notifications/messages": [dead], "GET /api/v1/notifications/status": { pending: 0, sent: 3, dead_letter: 1, suppressed: 0, stale_pending: 0, alert: true },
    "GET /api/v1/notifications/templates": [], "GET /api/v1/notifications/preferences/me": { email: true, sms: false } };

  it("shows delivery status and lets only processors retry a dead letter", async () => {
    let retried = false;
    const api = router({ ...base, "POST /api/v1/notifications/messages/m1/retry": () => { retried = true; return dead; } });
    const { unmount } = render(<NotificationsWorkspace api={api} claims={claims("notification:outbox:read")} connected />);
    expect(await screen.findByText("permanent: nope")).toBeInTheDocument();
    expect(screen.getByLabelText("Delivery summary")).toHaveTextContent("1 dead letter");
    expect(screen.queryByRole("button", { name: /Retry message/ })).not.toBeInTheDocument();
    unmount();
    render(<NotificationsWorkspace api={api} claims={claims("notification:outbox:read", "notification:process")} connected />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry message m1" }));
    await waitFor(() => expect(retried).toBe(true));
  });

  it("saves a personal channel preference through the self-service endpoint", async () => {
    let body;
    const api = router({ ...base, "PUT /api/v1/notifications/preferences/me": o => { body = JSON.parse(o.body); return {}; } });
    render(<NotificationsWorkspace api={api} claims={claims()} connected />);
    await userEvent.click(screen.getByRole("tab", { name: "My preferences" }));
    await userEvent.click(await screen.findByLabelText("sms"));
    await waitFor(() => expect(body).toEqual({ channel: "sms", enabled: true }));
  });
});

describe("GovernanceWorkspace", () => {
  const delegation = { id: "d1", status: "Pending Approval", version: 1, delegator_subject: "a", delegate_subject: "b", scope_code: "fin", action_code: "approve", effective_from: "2026-12-01T00:00:00Z", effective_to: "2026-12-31T00:00:00Z", effective_now: false };

  it("offers approve only with the permission and sends the expected version", async () => {
    let approved;
    const api = router({ "GET /api/v1/governance/delegations": [delegation], "GET /api/v1/governance/decisions": [],
      "POST /api/v1/governance/delegations/d1/approve": o => { approved = JSON.parse(o.body); return delegation; } });
    const { unmount, container } = render(<GovernanceWorkspace api={api} claims={claims("governance:delegation:read")} connected />);
    expect(await screen.findByText("fin")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve d1/ })).not.toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
    unmount();
    render(<GovernanceWorkspace api={api} claims={claims("governance:delegation:read", "governance:delegation:approve")} connected />);
    await userEvent.click(await screen.findByRole("button", { name: "Approve d1" }));
    await waitFor(() => expect(approved).toEqual({ expected_version: 1 }));
  });

  it("surfaces maker-checker refusals", async () => {
    const api = router({ "GET /api/v1/governance/delegations": [delegation], "GET /api/v1/governance/decisions": [],
      "POST /api/v1/governance/delegations/d1/approve": () => { throw new Error("delegation_self_approval_forbidden"); } });
    render(<GovernanceWorkspace api={api} claims={claims("governance:delegation:read", "governance:delegation:approve")} connected />);
    await userEvent.click(await screen.findByRole("button", { name: "Approve d1" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("delegation_self_approval_forbidden");
  });
});

describe("ReportsWorkspace", () => {
  const summary = { generated_at: "2026-11-14T10:00:00Z", currency_note: "Amounts are per currency and are never converted or summed across currencies.", sections: {
    receivables: { label: "Receivables", sources: ["ar_invoices"], data: { invoices_by_status: { Issued: 2 }, outstanding_by_currency: { INR: "100.00", USD: "50.00" } } },
    workforce: { label: "Workforce", sources: ["hr_employees"], data: { employees_by_status: { Active: 4 } } } } };

  it("renders sections with lineage, keeps currencies separate, and filters sections for Financial reporting", async () => {
    const api = router({ "GET /api/v1/reports/summary": summary });
    const { unmount, container } = render(<ReportsWorkspace api={api} connected />);
    const region = await screen.findByRole("region", { name: "Receivables" });
    expect(region).toHaveTextContent("ar_invoices");
    expect(region).toHaveTextContent("INR: 100.00");
    expect(region).toHaveTextContent("USD: 50.00");
    expect(await axeViolations(container)).toEqual([]);
    unmount();
    render(<ReportsWorkspace api={api} connected name="Financial reporting" only={["receivables"]} />);
    await screen.findByRole("region", { name: "Receivables" });
    expect(screen.queryByRole("region", { name: "Workforce" })).not.toBeInTheDocument();
  });

  it("shows an empty state when no section is permitted", async () => {
    render(<ReportsWorkspace api={router({ "GET /api/v1/reports/summary": { generated_at: "2026-11-14T10:00:00Z", currency_note: "n", sections: {} } })} connected />);
    expect(await screen.findByText("No report sections available")).toBeInTheDocument();
  });
});
