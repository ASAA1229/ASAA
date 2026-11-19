import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RegisterWorkspace from "../../src/RegisterWorkspace.jsx";
import { axeViolations } from "./helpers.js";

const catalogue = [{ key: "policy", workspace: "Policies & procedures", label: "Policy or procedure", plural: "Policies and procedures", fields: [
  { name: "document_type", kind: "enum", label: "Document type", required: true, choices: ["Policy", "Procedure"] },
  { name: "acknowledgement_required", kind: "bool", label: "Acknowledgement required", required: false, choices: [] }] }];
const record = { id: "r1", register_type: "policy", code: "POL-001", revision: 1, title: "Acceptable use", summary: "Rules", owner_subject: "alice", status: "Draft",
  review_due: null, data: { document_type: "Policy" }, version: 1, created_by: "alice", reviewed_by: null, effective_from: null, effective_to: null };
const zero = { Draft: 0, "In Review": 0, Approved: 0, Retired: 0 };

function makeApi(handlers) {
  const calls = [];
  const api = vi.fn(async (path, options = {}) => {
    const method = options.method || "GET";
    calls.push({ path, method, body: options.body ? JSON.parse(options.body) : undefined });
    const key = Object.keys(handlers).find(k => `${method} ${path}`.startsWith(k));
    if (!key) throw new Error("unexpected " + method + " " + path);
    const h = handlers[key];
    return typeof h === "function" ? h(options) : h;
  });
  return { api, calls };
}
const claimsFor = (...p) => ({ permissions: p });
const baseHandlers = (records = [record], summary = { register_type: "policy", by_status: { ...zero, Draft: records.length }, review_overdue: 0 }) => ({
  "GET /api/v1/registers/types": catalogue, "GET /api/v1/registers/policy/summary": summary, "GET /api/v1/registers/policy": records });

describe("RegisterWorkspace", () => {
  it("shows a preview message when not connected and an access message without read permission", async () => {
    const { api } = makeApi({});
    const { rerender } = render(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={api} claims={{}} connected={false} />);
    expect(screen.getByText(/Connect an authorized identity session/)).toBeInTheDocument();
    rerender(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={api} claims={claimsFor("supplier:read")} connected />);
    expect(screen.getByText("Access not granted")).toBeInTheDocument();
    expect(api).not.toHaveBeenCalled();
  });

  it("shows loading then records with status summary, and is accessible", async () => {
    const { api } = makeApi(baseHandlers());
    const { container } = render(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={api} claims={claimsFor("register:policy:read")} connected />);
    expect(screen.getByText("Loading records...")).toBeInTheDocument();
    expect(await screen.findByText("POL-001")).toBeInTheDocument();
    expect(screen.getByLabelText("Status summary")).toHaveTextContent("1 Draft");
    expect(screen.queryByRole("button", { name: /New policy/i })).not.toBeInTheDocument(); // read-only session
    expect(await axeViolations(container)).toEqual([]);
  });

  it("shows an empty state and an error state", async () => {
    const { api } = makeApi(baseHandlers([]));
    const { unmount } = render(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={api} claims={claimsFor("register:policy:read")} connected />);
    expect(await screen.findByText(/No policies and procedures found/)).toBeInTheDocument();
    unmount();
    const failing = vi.fn(async () => { throw new Error("Server exploded"); });
    render(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={failing} claims={claimsFor("register:policy:read")} connected />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Server exploded");
  });

  it("creates a draft with the typed fields and refreshes", async () => {
    let created;
    const handlers = { ...baseHandlers([]), "POST /api/v1/registers/policy": o => { created = JSON.parse(o.body); return { ...record, id: "new" }; } };
    const { api } = makeApi(handlers);
    const { container } = render(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={api} claims={claimsFor("register:policy:read", "register:policy:write")} connected />);
    await userEvent.click(await screen.findByRole("button", { name: /New policy or procedure/i }));
    const form = screen.getByRole("form", { name: /New Policy or procedure/ });
    await userEvent.type(within(form).getByLabelText("Code"), "POL-002");
    await userEvent.type(within(form).getByLabelText("Title"), "Remote work");
    await userEvent.selectOptions(within(form).getByLabelText("Document type"), "Procedure");
    await userEvent.click(within(form).getByLabelText("Acknowledgement required"));
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(within(form).getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(created).toEqual({ code: "POL-002", title: "Remote work", summary: null, review_due: null, data: { document_type: "Procedure", acknowledgement_required: true } }));
    expect(await screen.findByRole("status")).toHaveTextContent(/created as Draft/);
  });

  it("offers review actions only to reviewers and requires a reason", async () => {
    const inReview = { ...record, status: "In Review", submitted_by: "alice" };
    let reviewed;
    const handlers = { ...baseHandlers([inReview]), "POST /api/v1/registers/policy/r1/review": o => { reviewed = JSON.parse(o.body); return { ...inReview, status: "Approved" }; } };
    const { api } = makeApi(handlers);
    const view = render(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={api} claims={claimsFor("register:policy:read", "register:policy:write")} connected />);
    await userEvent.click(await screen.findByRole("button", { name: /Open POL-001/ }));
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    view.unmount();
    render(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={api} claims={claimsFor("register:policy:read", "register:policy:review")} connected />);
    await userEvent.click(await screen.findByRole("button", { name: /Open POL-001/ }));
    const approve = screen.getByRole("button", { name: "Approve" });
    expect(approve).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Review reason"), "Looks right");
    await userEvent.click(approve);
    await waitFor(() => expect(reviewed).toEqual({ expected_version: 1, decision: "Approve", reason: "Looks right" }));
  });

  it("surfaces API refusals such as maker-checker without losing the record", async () => {
    const inReview = { ...record, status: "In Review" };
    const handlers = { ...baseHandlers([inReview]), "POST /api/v1/registers/policy/r1/review": () => { throw new Error("maker_cannot_review_own_record"); } };
    const { api } = makeApi(handlers);
    render(<RegisterWorkspace name="Policies & procedures" types={["policy"]} api={api} claims={claimsFor("register:policy:read", "register:policy:review")} connected />);
    await userEvent.click(await screen.findByRole("button", { name: /Open POL-001/ }));
    await userEvent.type(screen.getByLabelText("Review reason"), "self review");
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("maker_cannot_review_own_record");
    expect(screen.getByText("POL-001")).toBeInTheDocument();
  });
});
