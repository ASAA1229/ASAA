import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const API = "http://127.0.0.1:8765";
const tokens = () => JSON.parse(readFileSync(".e2e/tokens.json", "utf8"));
const unique = () => Math.random().toString(36).slice(2, 8).toUpperCase();

async function signIn(page, who) {
  await page.goto("/");
  await page.getByPlaceholder("https://api.your-domain.com").fill(API);
  await page.getByPlaceholder("Paste a development access token").fill(tokens()[who]);
  await page.getByRole("button", { name: /Connect with development token/ }).click();
  await expect(page.getByText("API connected")).toBeVisible();
}
const openNav = (page, name) => page.locator("nav").getByRole("button", { name: new RegExp(`^${name}`) }).click();
async function expectAccessible(page, label) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]).analyze();
  expect(results.violations.map(v => `${v.id}: ${[...new Set(v.nodes.map(n => n.target.join(" ")))].slice(0, 5).join(" | ")}`), `axe on ${label}`).toEqual([]);
}

test.describe("shared platform workspaces (live API)", () => {
  test("audit trail shows a freshly written event, filters it and expands details", async ({ page, request }) => {
    const code = "AUD-" + unique();
    const created = await request.post(`${API}/api/v1/registers/policy`, {
      headers: { Authorization: `Bearer ${tokens().admin}` }, data: { code, title: "Audit probe", data: { document_type: "Policy" } } });
    expect(created.status()).toBe(201);
    await signIn(page, "admin");
    await openNav(page, "Audit trail");
    await page.getByLabel("Action starts with").fill("register_record.created");
    const row = page.getByRole("row").filter({ hasText: "register_record.created" }).first();
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: /Details for register_record.created/ }).click();
    await expect(page.getByText(code).first()).toBeVisible();
    await page.getByLabel("Actor").fill("nobody-at-all");
    await expect(page.getByText("No audit events match")).toBeVisible();
    await expectAccessible(page, "audit trail");
  });

  test("audit trail is refused without audit:read", async ({ page }) => {
    await signIn(page, "reader");
    await openNav(page, "Audit trail");
    await expect(page.getByText("Access not granted")).toBeVisible();
  });

  test("reports show per-currency, permission-filtered sections with lineage", async ({ page }) => {
    await signIn(page, "admin");
    await openNav(page, "Reports & dashboards");
    await expect(page.getByRole("region", { name: "Receivables" })).toContainText("ar_invoices");
    await expect(page.getByText(/never converted/).first()).toBeVisible();
    await expect(page.getByText(/salary|gross/i)).toHaveCount(0);
    await expectAccessible(page, "reports");
    await openNav(page, "Financial reporting");
    await expect(page.getByRole("region", { name: "Suppliers" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Workforce" })).toHaveCount(0);
  });

  test("notifications: create a template, see it listed, toggle a personal preference", async ({ page }) => {
    const code = "tpl." + unique().toLowerCase();
    await signIn(page, "admin");
    await openNav(page, "Notifications & reminders");
    await page.getByRole("tab", { name: "Templates" }).click();
    await page.getByRole("button", { name: "New template" }).click();
    const form = page.getByRole("form", { name: "New notification template" });
    await form.getByLabel("Code").fill(code);
    await form.getByLabel("Subject template").fill("Action needed: {{item}}");
    await form.getByLabel("Body template").fill("Please review {{item}}.");
    await form.getByLabel(/Allowed variables/).fill("item");
    await form.getByRole("button", { name: "Save template" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Template created" })).toBeVisible();
    await expect(page.getByRole("cell", { name: code })).toBeVisible();
    await expectAccessible(page, "notification templates");
    // sensitive variables are refused by the API and the reason is shown
    await page.getByRole("button", { name: "New template" }).click();
    const bad = page.getByRole("form", { name: "New notification template" });
    await bad.getByLabel("Code").fill("bad." + unique().toLowerCase());
    await bad.getByLabel("Subject template").fill("Pay {{salary}}");
    await bad.getByLabel("Body template").fill("x");
    await bad.getByLabel(/Allowed variables/).fill("salary");
    await bad.getByRole("button", { name: "Save template" }).click();
    await expect(page.getByRole("alert")).toContainText(/sensitive/);
    await page.getByRole("tab", { name: "My preferences" }).click();
    await page.getByLabel("sms").click();
    await expect(page.getByRole("status").filter({ hasText: "Preference for sms saved" })).toBeVisible();
    await expect(page.getByLabel("sms")).not.toBeChecked();
    await page.getByRole("tab", { name: "Outbox" }).click();
    await expect(page.getByText("No messages")).toBeVisible();
  });

  test("governance: maker proposes a delegation, a different approver approves it", async ({ page }) => {
    const scope = "scope." + unique().toLowerCase();
    await signIn(page, "admin");
    await openNav(page, "Governance");
    await page.getByRole("button", { name: "New delegation" }).click();
    const form = page.getByRole("form", { name: "New delegation" });
    await form.getByLabel("delegator subject").fill("alice");
    await form.getByLabel("delegate subject").fill("bob");
    await form.getByLabel("scope code").fill(scope);
    await form.getByLabel("action code").fill("approve.expense");
    await form.getByLabel("effective from").fill("2026-12-01T09:00");
    await form.getByLabel("effective to").fill("2026-12-31T18:00");
    await form.getByLabel("reason").fill("Annual leave cover");
    await form.getByRole("button", { name: "Save" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Created for independent review" })).toBeVisible();
    await expect(page.getByRole("cell", { name: scope })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Approve / })).toHaveCount(0); // maker has no approve permission
    await expectAccessible(page, "governance");
    await signIn(page, "reviewer");
    await openNav(page, "Governance");
    await page.getByRole("row", { name: new RegExp(scope) }).getByRole("button", { name: /^Approve / }).click();
    await expect(page.getByRole("status").filter({ hasText: "Approved." })).toBeVisible();
    await expect(page.getByRole("row", { name: new RegExp(scope) })).toContainText("Approved");
  });
});
