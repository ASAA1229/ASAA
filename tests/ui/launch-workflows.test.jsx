import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "../../src/App.jsx";
import { axeViolations, makeToken, mockApi, respond } from "./helpers.js";

const ALL_READ = [
  "supplier:read", "supplier:write", "ar:customer:read", "ar:customer:write", "ar:invoice:read", "ar:invoice:write",
  "ar:invoice:issue", "ar:receipt:read", "hr:employee:read", "hr:leave:read", "onboarding:read", "hr:exit:read",
  "expense:claim:read", "expense:claim:write", "tms:timesheet:read", "procurement:request:read", "procurement:request:write",
];

const customers = [{ id: "c1", legal_name: "Acme Traders Pvt Ltd", status: "Active", version: 1 }];
const invoices = [{ id: "i1", customer_id: "c1", invoice_number: "INV-1001", status: "Draft", currency: "INR", outstanding: "1180.00", total: "1180.00", version: 1, lines: [] }];
const suppliers = [{ id: "s1", legal_name: "Globex Supplies", status: "Pending Verification", version: 1, category: "Stationery" }];

const routes = {
  "GET /api/v1/me": { subject: "u1" },
  "GET /api/v1/ar/customers": customers,
  "GET /api/v1/ar/invoices": invoices,
  "GET /api/v1/ar/receipts": [],
  "GET /api/v1/ap/suppliers": suppliers,
  "GET /api/v1/ap/purchase-requests": [],
  "GET /api/v1/workforce-finance/timesheets": [],
  "GET /api/v1/workforce-finance/expenses": [],
  "GET /api/v1/hr/employees": [{ id: "e1", employee_number: "E-001", first_name: "Asha", last_name: "Rao", employment_type: "Employee", status: "Active", version: 1 }],
  "GET /api/v1/hr/leave-requests": [],
  "GET /api/v1/onboarding/templates": [],
  "GET /api/v1/onboarding/assignments": [],
  "GET /api/v1/hr/exit-cases": [],
};

async function signIn(permissions, overrides = {}) {
  const calls = mockApi({ ...routes, ...overrides });
  const view = render(<App />);
  await pasteToken(makeToken({ sub: "u1", name: "Test Admin", org_id: "org-a", permissions }));
  await userEvent.click(screen.getByRole("button", { name: /Connect with development token/ }));
  await screen.findByText("API connected");
  return { ...view, calls };
}
async function pasteToken(token) {
  await userEvent.click(screen.getByPlaceholderText(/Paste a development access token/));
  await userEvent.paste(token);
}
const openSection = name => userEvent.click(within(document.querySelector("nav")).getByRole("button", { name: new RegExp(`^${name}`) }));

describe("sign-in screen", () => {
  it("rejects an empty token without calling the API", async () => {
    const calls = mockApi({});
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Connect with development token/ }));
    expect(await screen.findByText(/Enter an access token/)).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });

  it("returns to the sign-in screen when the API answers 401", async () => {
    mockApi({ "GET /api/v1/ap/suppliers": respond(401, { detail: "Invalid or expired access token" }) });
    render(<App />);
    await pasteToken(makeToken({ sub: "u", permissions: ["supplier:read"] }));
    await userEvent.click(screen.getByRole("button", { name: /Connect with development token/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Connect with development token/ })).toBeInTheDocument());
    expect(screen.queryByText("API connected")).not.toBeInTheDocument();
  });

  it("has no automated accessibility violations", async () => {
    mockApi({});
    const { container } = render(<App />);
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("authenticated session", () => {
  it("sends the bearer token and only requests endpoints the token is permitted to read", async () => {
    const { calls } = await signIn(["supplier:read", "ar:customer:read"]);
    const paths = calls.map(c => c.path).sort();
    expect(paths).toEqual(["/api/v1/ap/suppliers", "/api/v1/ar/customers", "/api/v1/me"]);
    expect(calls[0].headers.Authorization).toMatch(/^Bearer .+\..+\./);
  });

  it("overview shows live AR figures and has no accessibility violations", async () => {
    const { container } = await signIn(ALL_READ);
    expect(await screen.findByText("Receivables outstanding")).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("AR workspace lists customers and invoices with status", async () => {
    const { container } = await signIn(ALL_READ);
    await openSection("AR");
    expect(await screen.findByText("INV-1001")).toBeInTheDocument();
    expect(container.textContent).toContain("Draft");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("AP workspace lists suppliers with verification status", async () => {
    const { container } = await signIn(ALL_READ);
    await openSection("AP");
    expect(await screen.findByText("Globex Supplies")).toBeInTheDocument();
    expect(container.textContent).toContain("Pending Verification");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("people directory renders the employee list for HR readers", async () => {
    const { container } = await signIn(ALL_READ);
    await openSection("People directory");
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("a session with a single read permission renders without crashing (regression: partial permissions)", async () => {
    const { container } = await signIn(["supplier:read"]);
    expect(await screen.findByText("Receivables outstanding")).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("people directory explains missing access instead of listing employees", async () => {
    const { calls } = await signIn(["supplier:read"]);
    await openSection("People directory");
    expect(await screen.findByText("Directory access not granted")).toBeInTheDocument();
    expect(calls.filter(c => c.path.includes("/hr/"))).toEqual([]);
  });

  it("payroll workspace makes no payroll API call without payroll permissions", async () => {
    const { calls } = await signIn(ALL_READ);
    await openSection("Compensation & payroll");
    await screen.findAllByText(/payroll/i);
    expect(calls.filter(c => c.path.includes("payroll"))).toEqual([]);
  });

  it("creates a customer through the quick-create dialog and Escape closes the dialog", async () => {
    const created = [];
    const { container, calls } = await signIn(ALL_READ, {
      "POST /api/v1/ar/customers": options => { created.push(JSON.parse(options.body)); return respond(201, { id: "c2" }); },
    });
    await openSection("AR");
    await userEvent.click(await screen.findByRole("button", { name: "Customer" }));
    const dialog = await screen.findByRole("dialog", { name: "Add customer" });
    expect(await axeViolations(dialog)).toEqual([]);
    await userEvent.type(within(dialog).getByLabelText(/Customer legal name/), "Initech Ltd");
    await userEvent.click(within(dialog).getByRole("button", { name: /save|create|add/i }));
    await waitFor(() => expect(created).toEqual([{ legal_name: "Initech Ltd" }]));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.filter(c => c.method === "GET" && c.path === "/api/v1/ar/customers").length).toBeGreaterThan(1);

    await userEvent.click(screen.getByRole("button", { name: "Customer" }));
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(container.querySelector('[role="dialog"]')).toBeNull());
  });

  it("surfaces an API validation error from a failed create without closing the dialog", async () => {
    await signIn(ALL_READ, { "POST /api/v1/ar/customers": respond(422, { detail: "Customer already exists" }) });
    await openSection("AR");
    await userEvent.click(await screen.findByRole("button", { name: "Customer" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Customer legal name/), "Dup");
    await userEvent.click(within(dialog).getByRole("button", { name: /save|create|add/i }));
    expect(await within(dialog).findByText(/Customer already exists/)).toBeInTheDocument();
  });
});
