import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const API = "http://127.0.0.1:8765";
const tokens = () => JSON.parse(readFileSync(".e2e/tokens.json", "utf8"));
const unique = () => Math.random().toString(36).slice(2, 8);

async function signIn(page, who = "admin") {
  await page.goto("/");
  await page.getByPlaceholder("https://api.your-domain.com").fill(API);
  await page.getByPlaceholder("Paste a development access token").fill(tokens()[who]);
  await page.getByRole("button", { name: /Connect with development token/ }).click();
  await expect(page.getByText("API connected")).toBeVisible();
}

const openNav = (page, name) => page.locator("nav").getByRole("button", { name: new RegExp(`^${name}`) }).click();

/** WCAG 2.x A/AA automated scan in a real browser (includes colour contrast). */
async function expectNoA11yViolations(page, label) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]).analyze();
  const detail = n => {
    const d = n.any?.[0]?.data;
    return d && d.contrastRatio ? `${n.target.join(" ")} (${d.fgColor} on ${d.bgColor}, ${d.contrastRatio}:1)` : n.target.join(" ");
  };
  const summary = results.violations.map(v => `${v.id} [${v.impact}] x${v.nodes.length}: ${[...new Set(v.nodes.map(detail))].slice(0, 12).join(" | ")}`);
  expect(summary, `axe violations on ${label}`).toEqual([]);
}

test.describe("sign-in", () => {
  test("sign-in screen has no accessibility violations", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
    await expectNoA11yViolations(page, "sign-in");
  });

  test("an invalid token is refused by the real API and the user stays on sign-in", async ({ page }) => {
    await page.goto("/");
    await page.getByPlaceholder("https://api.your-domain.com").fill(API);
    await page.getByPlaceholder("Paste a development access token").fill("not.a.jwt");
    await page.getByRole("button", { name: /Connect with development token/ }).click();
    await expect(page.getByRole("button", { name: /Connect with development token/ })).toBeVisible();
    await expect(page.getByText("API connected")).toHaveCount(0);
  });

  test("a valid token signs in and a read-only token only sees what it may read", async ({ page }) => {
    await signIn(page, "reader");
    await openNav(page, "AP");
    await expect(page.getByRole("button", { name: /Add supplier/ })).toHaveCount(0);
    await openNav(page, "Compensation & payroll");
    await expect(page.getByText(/payroll/i).first()).toBeVisible();
  });
});

test.describe("launch workflows (live API)", () => {
  test("organization admin: register the organization profile and a department", async ({ page }) => {
    await signIn(page);
    await openNav(page, "Organization & entities");
    await page.getByRole("button", { name: /register|edit|profile/i }).first().click();
    await page.getByLabel("Display name").fill("ASAA E2E Org");
    await expectNoA11yViolations(page, "organization profile form");
    await page.getByRole("button", { name: "Save profile" }).click();
    await expect(page.getByText("ASAA E2E Org").first()).toBeVisible();
    await openNav(page, "Departments & teams");
    await page.getByRole("button", { name: "Add unit" }).click();
    await page.getByLabel("Unique unit code").fill("fin-" + unique());
    await page.getByLabel("Name", { exact: true }).fill("Finance E2E");
    await page.getByRole("button", { name: /Create proposed/ }).click();
    await expect(page.getByText("Finance E2E").first()).toBeVisible();
    await expectNoA11yViolations(page, "organization structure");
  });

  test("people/HR: create an employee and see it in the directory", async ({ page }) => {
    await signIn(page);
    await openNav(page, "People directory");
    const code = "E2E-" + unique();
    await page.getByLabel("Employee code").fill(code);
    await page.getByLabel("First name").fill("Asha");
    await page.getByLabel("Last name").fill("Rao");
    await page.getByLabel("Employment type").selectOption("Employee");
    await page.getByRole("button", { name: /Add employee/ }).click();
    await expect(page.getByRole("cell", { name: new RegExp(code) })).toBeVisible();
    await expect(page.getByText("Asha Rao").first()).toBeVisible();
    await expectNoA11yViolations(page, "people directory");
  });

  test("AP: create a supplier through the form and see it listed as Draft", async ({ page }) => {
    await signIn(page);
    await openNav(page, "AP");
    await page.getByRole("button", { name: /Add supplier/ }).first().click();
    const name = "Globex " + unique();
    await page.getByLabel(/legal name/i).first().fill(name);
    await expectNoA11yViolations(page, "supplier form");
    await page.getByRole("button", { name: /Create supplier|Save/ }).first().click();
    await expect(page.getByText(name).first()).toBeVisible();
    await expect(page.getByText("Draft").first()).toBeVisible();
    await expectNoA11yViolations(page, "AP workspace");
  });

  test("AR: create a customer from the AR workspace dialog", async ({ page }) => {
    await signIn(page);
    await openNav(page, "AR");
    await page.getByRole("button", { name: "Customer", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Add customer" });
    await expect(dialog).toBeVisible();
    await expectNoA11yViolations(page, "add customer dialog");
    const name = "Initech " + unique();
    await dialog.getByLabel("Customer legal name").fill(name);
    await dialog.getByRole("button", { name: /Save|Create|Add/ }).click();
    await expect(dialog).toHaveCount(0);
    await expectNoA11yViolations(page, "AR workspace");
  });

  for (const screen of ["Leave management", "Compensation & payroll", "Timesheets", "Expenses", "Procurement", "Master data", "Identity & access", "Settings"]) {
    test(`screen renders with an authorized session and passes axe: ${screen}`, async ({ page }) => {
      await signIn(page);
      await openNav(page, screen);
      await expect(page.locator(".crumb strong")).toContainText(screen.split(" ")[0]);
      await expectNoA11yViolations(page, screen);
    });
  }

  test("timesheet: the create form opens, is accessible and can be closed", async ({ page }) => {
    await signIn(page);
    await openNav(page, "Timesheets");
    await page.getByRole("button", { name: /New timesheet/ }).click();
    await expect(page.getByRole("heading", { name: "Create timesheet" })).toBeVisible();
    await expectNoA11yViolations(page, "timesheet form");
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByRole("heading", { name: "Create timesheet" })).toHaveCount(0);
  });
});

test.describe("keyboard-only operation", () => {
  test("sign-in can be completed with the keyboard alone", async ({ page }) => {
    await page.goto("/");
    await page.getByPlaceholder("https://api.your-domain.com").focus();
    await page.keyboard.insertText(API);
    await page.keyboard.press("Tab");
    // skip optional controls until the token field is focused
    for (let i = 0; i < 4 && !(await page.evaluate(() => document.activeElement?.tagName === "TEXTAREA")); i++) await page.keyboard.press("Tab");
    expect(await page.evaluate(() => document.activeElement?.tagName)).toBe("TEXTAREA");
    await page.keyboard.insertText(tokens().admin);
    await page.keyboard.press("Tab");
    await page.keyboard.press("Enter");
    await expect(page.getByText("API connected")).toBeVisible();
  });

  test("skip link moves focus past the navigation to the main content", async ({ page, browserName }) => {
    // Safari/WebKit does not include links in Tab order by default (system "Press Tab to highlight each item" off).
    test.skip(browserName === "webkit", "WebKit does not Tab to links by default");
    await page.goto("/"); // fresh load: sequential focus starts at the top of the document
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: /skip to main content/i });
    await expect(skip).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-content")).toBeFocused();
  });

  test("navigation, dialog open, Escape close and focus return work by keyboard; focus is always visible", async ({ page }) => {
    await signIn(page);
    await page.locator("nav").getByRole("button", { name: /^AR/ }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".crumb strong")).toContainText("AR");
    const customerButton = page.getByRole("button", { name: "Customer", exact: true });
    await customerButton.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "Add customer" });
    await expect(dialog).toBeVisible();
    // focus moved into the dialog
    await expect.poll(() => page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true);
    // keyboard focus indicator is rendered (non-zero outline or box-shadow) on a focused control
    await page.keyboard.press("Tab");
    const indicator = await page.evaluate(() => {
      const s = getComputedStyle(document.activeElement);
      return { outline: s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0, shadow: s.boxShadow !== "none" };
    });
    expect(indicator.outline || indicator.shadow).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(customerButton).toBeFocused();
  });
});
