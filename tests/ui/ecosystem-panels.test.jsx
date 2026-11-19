import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EcosystemStatusPanel, IntegrationEventsPanel } from "../../src/PlatformWorkspaces.jsx";
import { axeViolations } from "./helpers.js";

const claims = (...p) => ({ permissions: p });
const router = routes => vi.fn(async (path, options = {}) => {
  const key = Object.keys(routes).find(k => `${options.method || "GET"} ${path}`.startsWith(k));
  if (!key) throw new Error(`unexpected ${options.method || "GET"} ${path}`);
  const r = routes[key];
  return typeof r === "function" ? r(options) : r;
});

const status = {
  checkedAt: "2026-11-18T10:00:00.000Z", registry: { loaded: true, orgId: "asaa" },
  services: [
    { service: "asaa-api", project: "ASAA", status: "ok", version: "0.4.0", commit: null, checkedAt: "2026-11-18T10:00:00.000Z" },
    { service: "jarvis", project: "JARVIS", status: "unreachable", version: null, commit: null, checkedAt: "2026-11-18T10:00:00.000Z", detail: "no response" },
    { service: "templates-api", project: "TEMPLATES", status: "degraded", version: "1.2.3", commit: "abcdef1", checkedAt: "2026-11-18T10:00:00.000Z" },
    { service: "templates-web", project: "TEMPLATES", status: "not-probed", version: null, commit: null, checkedAt: "2026-11-18T10:00:00.000Z" },
  ],
};

describe("EcosystemStatusPanel", () => {
  it("renders nothing and makes no request without ops:ecosystem:read or without a session", () => {
    const api = router({ "GET /api/v1/operations/ecosystem": status });
    const { container, rerender } = render(<EcosystemStatusPanel api={api} claims={claims("audit:read")} connected />);
    expect(container).toBeEmptyDOMElement();
    rerender(<EcosystemStatusPanel api={api} claims={claims("ops:ecosystem:read")} connected={false} />);
    expect(container).toBeEmptyDOMElement();
    expect(api).not.toHaveBeenCalled();
  });

  it("lists every service with its state, shows offline siblings without an error and has no axe violations", async () => {
    const api = router({ "GET /api/v1/operations/ecosystem": status });
    const { container } = render(<EcosystemStatusPanel api={api} claims={claims("ops:ecosystem:read")} connected />);
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(5);
    expect(within(rows[2]).getByText(/Unreachable/)).toBeInTheDocument();
    expect(within(rows[2]).getByText(/no response/)).toBeInTheDocument();
    expect(within(rows[3]).getByText("abcdef1")).toBeInTheDocument();
    expect(within(rows[4]).getByText("Not monitored")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("explains a missing registry and surfaces load errors", async () => {
    const missing = router({ "GET /api/v1/operations/ecosystem": { checkedAt: "2026-11-18T10:00:00Z", registry: { loaded: false, reason: "registry file not found" }, services: [] } });
    const { unmount } = render(<EcosystemStatusPanel api={missing} claims={claims("ops:ecosystem:read")} connected />);
    expect(await screen.findByText("Ecosystem registry not available")).toBeInTheDocument();
    unmount();
    const failing = vi.fn(async () => { throw new Error("boom"); });
    render(<EcosystemStatusPanel api={failing} claims={claims("ops:ecosystem:read")} connected />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });
});

describe("IntegrationEventsPanel", () => {
  const event = { id: "e1", occurred_at: "2026-11-18T10:00:00Z", source: "templates-api", type: "templates.generation.completed", project: "TEMPLATES", severity: "info", subject: "generation/abc", data: { payloadMarker: "zz-payload-marker" } };

  it("is hidden without integration:event:read", () => {
    const api = router({ "GET /api/v1/integration/events": [event] });
    const { container } = render(<IntegrationEventsPanel api={api} claims={claims("ops:ecosystem:read")} connected />);
    expect(container).toBeEmptyDOMElement();
    expect(api).not.toHaveBeenCalled();
  });

  it("lists events without payloads, passes filters and pagination to the API and has no axe violations", async () => {
    const api = router({ "GET /api/v1/integration/events": [event] });
    const { container } = render(<IntegrationEventsPanel api={api} claims={claims("integration:event:read")} connected />);
    expect(await screen.findByText("templates.generation.completed")).toBeInTheDocument();
    expect(screen.getByText("generation/abc")).toBeInTheDocument();
    expect(screen.queryByText(/zz-payload-marker/)).toBeNull();
    await userEvent.type(screen.getByLabelText("Source"), "jarvis");
    await userEvent.selectOptions(screen.getByLabelText("Severity"), "critical");
    await waitFor(() => expect(api.mock.calls.some(([p]) => p.includes("source=jarvis") && p.includes("severity=critical") && p.includes("offset=0"))).toBe(true));
    expect(await axeViolations(container)).toEqual([]);
  });

  it("shows the empty state and errors", async () => {
    const empty = router({ "GET /api/v1/integration/events": [] });
    const { unmount } = render(<IntegrationEventsPanel api={empty} claims={claims("integration:event:read")} connected />);
    expect(await screen.findByText("No integration events match")).toBeInTheDocument();
    unmount();
    const failing = vi.fn(async () => { throw new Error("denied"); });
    render(<IntegrationEventsPanel api={failing} claims={claims("integration:event:read")} connected />);
    expect(await screen.findByRole("alert")).toHaveTextContent("denied");
  });
});
