import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AdministrationWorkspace from "../../src/AdministrationWorkspace.jsx";

const role = { id: "r-unit", role_code: "unit.lead", name: "Unit lead", scope_type: "Unit", permissions: ["hr:employee:read"], status: "Active", version: 1, created_by: "x" };
const units = [{ id: "u1", name: "Operations", unit_type: "Division", unit_code: "OPS", status: "Active" }, { id: "u2", name: "Finance", unit_type: "Department", unit_code: "FIN", status: "Active" }];
const customers = [{ id: "c1", legal_name: "Northwind Example Ltd" }];

function makeApi(extra = {}) {
  const calls = [];
  const handlers = {
    "GET /api/v1/authorization/roles": [role], "GET /api/v1/authorization/assignments": [],
    "GET /api/v1/authorization/scope-mode": { mode: "narrow", default: "narrow", modes: ["token", "narrow", "strict"] },
    "GET /api/v1/administration/units": units, "GET /api/v1/ar/customers": customers,
    "GET /api/v1/authorization/effective-access": { subject: "s1", mode: "narrow", assignments: [{ id: "a1", role_name: "Unit lead", scope_type: "Unit", scope_reference: "unit:u1" }],
      permissions: { "payroll:read": { permission: "payroll:read", sensitive: true, unrestricted: false, units: ["u1"], departments: [], projects: [], customers: [], records: [] } } },
    ...extra };
  const api = vi.fn(async (path, options = {}) => {
    const method = options.method || "GET";
    calls.push({ path, method, body: options.body ? JSON.parse(options.body) : undefined });
    const key = Object.keys(handlers).find(k => `${method} ${path}`.startsWith(k));
    if (!key) throw new Error("unexpected " + method + " " + path);
    return handlers[key];
  });
  return { api, calls };
}

describe("authorization scopes in the admin workspace", () => {
  it("offers all six scope types, names units in the picker and shows the mode read-only without permission", async () => {
    const { api } = makeApi();
    const claims = { permissions: ["authorization:role:read", "authorization:role:write", "authorization:assignment:read", "authorization:assignment:create"] };
    render(<AdministrationWorkspace name="Identity & access" api={api} claims={claims} connected />);
    expect(await screen.findByText(/Data scope mode: narrow/)).toBeInTheDocument();
    expect(screen.getByText(/Read only: changing the mode needs/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("New role template"));
    const scope = screen.getByLabelText("Scope");
    expect([...scope.options].map(o => o.value)).toEqual(["Organization", "Unit", "Department", "Project", "Customer", "Record"]);
    await userEvent.click(screen.getByText("Cancel"));
    await userEvent.click(screen.getByText("Request access"));
    await userEvent.selectOptions(screen.getByLabelText(/Approved role template/), "r-unit");
    const picker = screen.getByLabelText("Unit scope");
    expect([...picker.options].map(o => o.textContent)).toContain("Operations (Division)");
  });

  it("changes the mode only with the privileged permission and shows effective access", async () => {
    const { api, calls } = makeApi({ "PUT /api/v1/authorization/scope-mode": { mode: "strict" } });
    const claims = { permissions: ["authorization:role:read", "authorization:assignment:read", "authorization:scope-mode:write"] };
    render(<AdministrationWorkspace name="Identity & access" api={api} claims={claims} connected />);
    await screen.findByText(/Data scope mode: narrow/);
    await userEvent.selectOptions(screen.getByLabelText("Scope mode"), "strict");
    await userEvent.type(screen.getByPlaceholderText("Reason (audited)"), "tighten access");
    await userEvent.click(screen.getByText("Change mode"));
    await waitFor(() => expect(calls.some(c => c.method === "PUT" && c.body.mode === "strict")).toBe(true));
    await userEvent.type(screen.getByLabelText("Subject for effective access"), "s1");
    await userEvent.click(screen.getByText("Show effective access"));
    expect(await screen.findByText("payroll:read (sensitive)")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
  });
});
