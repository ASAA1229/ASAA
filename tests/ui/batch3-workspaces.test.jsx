import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RegisterWorkspace from "../../src/RegisterWorkspace.jsx";
import { BackupRecoveryWorkspace, ReportsWorkspace } from "../../src/PlatformWorkspaces.jsx";
import { axeViolations } from "./helpers.js";

const router = routes => vi.fn(async (path, options = {}) => {
  const key = Object.keys(routes).find(k => `${options.method || "GET"} ${path}`.startsWith(k));
  if (!key) throw new Error(`unexpected ${options.method || "GET"} ${path}`);
  return routes[key];
});
const zero = { Draft: 0, "In Review": 0, Approved: 0, Retired: 0 };

describe("Backup & recovery workspace", () => {
  const registerRoutes = { "GET /api/v1/registers/types": [{ key: "recovery_plan", label: "Recovery plan", plural: "Recovery plans", fields: [] }],
    "GET /api/v1/registers/recovery_plan/summary": { by_status: zero, review_overdue: 0 }, "GET /api/v1/registers/recovery_plan": [] };

  it("shows healthy and unhealthy backup status and is accessible", async () => {
    const healthy = router({ ...registerRoutes, "GET /api/v1/operations/backup-status": { configured: true, ok: true, last_success_at: "2026-11-14T01:00:00Z", age_hours: 3, limit_hours: 26, last_artifact: "asaa-1.sqlite.enc" } });
    const { unmount, container } = render(<BackupRecoveryWorkspace api={healthy} claims={{ permissions: ["ops:backup:read", "register:recovery_plan:read"] }} connected />);
    expect(await screen.findByText("asaa-1.sqlite.enc")).toBeInTheDocument();
    expect(screen.getByLabelText("Backup status")).toHaveTextContent("Healthy");
    expect(await axeViolations(container)).toEqual([]);
    unmount();
    const stale = router({ ...registerRoutes, "GET /api/v1/operations/backup-status": { configured: true, ok: false, reason: "newest backup is 40.0h old", last_success_at: null, age_hours: 40 } });
    render(<BackupRecoveryWorkspace api={stale} claims={{ permissions: ["ops:backup:read", "register:recovery_plan:read"] }} connected />);
    expect(await screen.findByText("newest backup is 40.0h old")).toBeInTheDocument();
  });

  it("explains missing permission and never calls the backup API", async () => {
    const api = router({});
    render(<BackupRecoveryWorkspace api={api} claims={{ permissions: [] }} connected />);
    expect(screen.getByText("Backup status not granted")).toBeInTheDocument();
    expect(api).not.toHaveBeenCalled();
  });
});

describe("renewals and report exceptions", () => {
  it("lists upcoming contract renewals with overdue wording", async () => {
    const contract = { key: "contract", label: "Contract", plural: "Contracts", fields: [] };
    const api = router({ "GET /api/v1/registers/types": [contract], "GET /api/v1/registers/contract/summary": { by_status: zero, review_overdue: 0 },
      "GET /api/v1/registers/contract/renewals": [{ id: "1", code: "C-1", title: "Globex supply", renewal_date: "2026-11-01", days_until_renewal: -4 }, { id: "2", code: "C-2", title: "Initech", renewal_date: "2026-12-20", days_until_renewal: 35 }],
      "GET /api/v1/registers/contract": [] });
    render(<RegisterWorkspace name="Contracts & renewals" types={["contract"]} renewals api={api} claims={{ permissions: ["register:contract:read"] }} connected />);
    const panel = await screen.findByRole("region", { name: "Upcoming renewals" });
    expect(panel).toHaveTextContent("4 days overdue");
    expect(panel).toHaveTextContent("in 35 days");
  });

  it("renders reconciliation exceptions as a list", async () => {
    const api = router({ "GET /api/v1/reports/summary": { generated_at: "2026-11-14T10:00:00Z", currency_note: "n", sections: { reconciliation: { label: "Receivables reconciliation", sources: ["ar_receipts"],
      data: { exception_count: 1, exceptions: [{ type: "receipt_not_fully_allocated", reference: "r1", currency: "USD", difference: "40.00" }], note: "Not a bank reconciliation" } } } } });
    render(<ReportsWorkspace api={api} connected name="Accounting & reconciliation" only={["reconciliation"]} />);
    expect(await screen.findByText(/receipt_not_fully_allocated - r1 - USD - 40.00/)).toBeInTheDocument();
  });
});
