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

test.describe("governed registers (live API)", () => {
  test("policy: maker drafts and submits, a different reviewer approves, the maker cannot", async ({ page }) => {
    const code = "POL-" + unique();
    await signIn(page, "admin");
    await openNav(page, "Policies & procedures");
    await page.getByRole("button", { name: /New policy or procedure/i }).click();
    const form = page.getByRole("form", { name: /New Policy or procedure/ });
    await form.getByLabel("Code").fill(code);
    await form.getByLabel("Title").fill("Acceptable use " + code);
    await form.getByLabel("Document type").selectOption("Policy");
    await expectAccessible(page, "register create form");
    await form.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByRole("status").filter({ hasText: "created as Draft" })).toBeVisible();
    await page.getByRole("button", { name: new RegExp(`Open ${code}`) }).click();
    await page.getByRole("button", { name: "Submit for review" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Submitted for independent review" })).toBeVisible();
    await expectAccessible(page, "register detail");
    // the maker holds no review permission in the UI at all
    await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);

    await signIn(page, "reviewer");
    await openNav(page, "Policies & procedures");
    await page.getByRole("button", { name: new RegExp(`Open ${code}`) }).click();
    await page.getByLabel("Review reason").fill("Reviewed against standard");
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Approved." })).toBeVisible();
    await expect(page.getByRole("row", { name: new RegExp(code) }).getByText("Approved")).toBeVisible();
  });

  test("risk and control tabs, filters and empty states work and are accessible", async ({ page }) => {
    await signIn(page, "admin");
    await openNav(page, "Risk & internal controls");
    await expect(page.getByRole("tab", { name: "Risks" })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Internal controls" }).click();
    await expect(page.getByText(/No internal controls found/)).toBeVisible();
    await page.getByLabel("Search").fill("zzz-nothing");
    await expectAccessible(page, "controls tab");
  });

  test("workflow definition: an invalid graph is refused by the API and the message is shown", async ({ page }) => {
    await signIn(page, "admin");
    await openNav(page, "Workflow & approvals");
    await page.getByRole("button", { name: /New workflow definition/i }).click();
    const form = page.getByRole("form", { name: /New Workflow definition/ });
    await form.getByLabel("Code").fill("WF-" + unique());
    await form.getByLabel("Title").fill("Broken workflow");
    await form.getByLabel("Initial state").fill("Draft");
    await form.getByLabel("States").fill("Draft, Review, Orphan");
    await form.getByLabel(/Transitions/).fill('[{"from":"Draft","to":"Review","action":"submit"}]');
    await form.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByRole("alert")).toContainText(/unreachable states: Orphan/);
  });

  test("a read-only session sees no create or review controls", async ({ page }) => {
    await signIn(page, "reader");
    await openNav(page, "Policies & procedures");
    await expect(page.getByText("Access not granted")).toBeVisible();
    await expect(page.getByRole("button", { name: /New policy/i })).toHaveCount(0);
  });

  test("document metadata and a record-keeping register (recruitment) can be created through the UI", async ({ page }) => {
    await signIn(page, "admin");
    await openNav(page, "Documents & records");
    await page.getByRole("button", { name: /New document record/i }).click();
    let form = page.getByRole("form", { name: /New Document record/ });
    const code = "DOC-" + unique();
    await form.getByLabel("Code").fill(code);
    await form.getByLabel("Title").fill("Signed supplier agreement");
    await form.getByLabel("Document type").fill("Agreement");
    await form.getByLabel("Classification").selectOption("Confidential");
    await form.getByLabel(/Storage reference/).fill("vault:docs/" + code.toLowerCase());
    await form.getByLabel("Legal hold").check();
    await form.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByRole("row", { name: new RegExp(code) })).toBeVisible();
    await expectAccessible(page, "documents register");
    // a credential-looking value is refused by the API (references are names, never secrets)
    await page.getByRole("button", { name: /New document record/i }).click();
    form = page.getByRole("form", { name: /New Document record/ });
    await form.getByLabel("Code").fill("DOC-" + unique());
    await form.getByLabel("Title").fill("Bad reference");
    await form.getByLabel("Document type").fill("Agreement");
    await form.getByLabel("Classification").selectOption("Internal");
    await form.getByLabel(/Storage reference/).fill("password=hunter2 secret");
    await form.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByRole("alert")).toContainText(/reference name/);

    await openNav(page, "Recruitment");
    await page.getByRole("button", { name: /New vacancy/i }).click();
    form = page.getByRole("form", { name: /New Vacancy/ });
    const vcode = "VAC-" + unique();
    await form.getByLabel("Code").fill(vcode);
    await form.getByLabel("Title").fill("Support engineer");
    await form.getByLabel("Headcount").fill("2");
    await form.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByRole("row", { name: new RegExp(vcode) })).toBeVisible();
    await expectAccessible(page, "recruitment register");
  });
});
