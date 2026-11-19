import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "../../src/App.jsx";
import { makeToken, mockApi } from "./helpers.js";

const zero = { Draft: 0, "In Review": 0, Approved: 0, Retired: 0 };
const routes = {
  "GET /api/v1/me": { subject: "u1" },
  "GET /api/v1/registers/types": [{ key: "integration", label: "Integration", plural: "Integrations", fields: [] }],
  "GET /api/v1/registers/integration/summary": { by_status: zero, review_overdue: 0 },
  "GET /api/v1/registers/integration": [],
  "GET /api/v1/operations/backup-status": { configured: false, ok: false, reason: "not configured" },
  "GET /api/v1/operations/ecosystem": { checkedAt: "2026-11-18T10:00:00Z", registry: { loaded: true }, services: [
    { service: "jarvis", project: "JARVIS", status: "unreachable", version: null, commit: null, checkedAt: "2026-11-18T10:00:00Z" }] },
  "GET /api/v1/integration/events": [{ id: "e1", occurred_at: "2026-11-18T10:00:00Z", source: "jarvis", type: "jarvis.task.completed", project: "JARVIS", severity: "info", subject: null }],
};

async function signIn(permissions) {
  const calls = mockApi(routes);
  render(<App />);
  await userEvent.click(screen.getByPlaceholderText(/Paste a development access token/));
  await userEvent.paste(makeToken({ sub: "u1", name: "Ops", org_id: "org-a", permissions }));
  await userEvent.click(screen.getByRole("button", { name: /Connect with development token/ }));
  await screen.findByText("API connected");
  return calls;
}
const openSection = name => userEvent.click(within(document.querySelector("nav")).getByRole("button", { name: new RegExp(`^${name}`) }));

describe("ecosystem panels placement", () => {
  it("shows ecosystem status and integration events under Integrations & connectors, not under Backup & recovery", async () => {
    await signIn(["ops:ecosystem:read", "integration:event:read", "ops:backup:read", "register:integration:read"]);
    await openSection("Integrations & connectors");
    expect(await screen.findByRole("region", { name: "Ecosystem services" })).toBeInTheDocument();
    expect(await screen.findByText("jarvis.task.completed")).toBeInTheDocument();
    await openSection("Backup & recovery");
    expect(await screen.findByText("Latest backup")).toBeInTheDocument();
    expect(screen.queryByLabelText("Ecosystem status")).toBeNull();
    expect(screen.queryByLabelText("Integration events")).toBeNull();
  });

  it("keeps permission gating: neither panel appears or fetches without its permission", async () => {
    const calls = await signIn(["register:integration:read"]);
    await openSection("Integrations & connectors");
    await screen.findByRole("heading", { name: /Integration/i, level: 2 });
    expect(screen.queryByLabelText("Ecosystem status")).toBeNull();
    expect(screen.queryByLabelText("Integration events")).toBeNull();
    expect(calls.some(c => c.path === "/api/v1/operations/ecosystem" || c.path === "/api/v1/integration/events")).toBe(false);
  });

  it("gates each panel independently", async () => {
    await signIn(["ops:ecosystem:read", "register:integration:read"]);
    await openSection("Integrations & connectors");
    expect(await screen.findByLabelText("Ecosystem status")).toBeInTheDocument();
    expect(screen.queryByLabelText("Integration events")).toBeNull();
  });
});
