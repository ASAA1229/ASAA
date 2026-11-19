import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const API = "http://127.0.0.1:8765";
const tokens = () => JSON.parse(readFileSync(".e2e/tokens.json", "utf8"));

async function signIn(page) {
  await page.goto("/");
  await page.getByPlaceholder("https://api.your-domain.com").fill(API);
  await page.getByPlaceholder("Paste a development access token").fill(tokens().admin);
  await page.getByRole("button", { name: /Connect with development token/ }).click();
  await expect(page.getByText("API connected")).toBeVisible();
}

const horizontalOverflow = page => page.evaluate(() => ({
  doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  body: document.body.scrollWidth - document.documentElement.clientWidth,
}));

async function openNav(page, name) {
  const menu = page.getByRole("button", { name: "Open navigation" });
  if (await menu.isVisible()) await menu.click();
  await page.locator("nav").getByRole("button", { name: new RegExp(`^${name}`) }).click();
}

async function expectAccessible(page, label) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]).analyze();
  expect(results.violations.map(v => `${v.id}: ${[...new Set(v.nodes.map(n => n.target.join(" ")))].slice(0, 5).join(" | ")}`), `axe on ${label}`).toEqual([]);
}

// WCAG 1.4.10 Reflow: content at 320 CSS px wide must not require horizontal scrolling of the page.
// WCAG 1.4.4 / 1.4.4-equivalent: browser zoom of 200% on a 1280 px window leaves a 640 CSS px viewport;
// Playwright cannot drive native browser zoom, so the equivalent viewport width is used.
const SIZES = [
  { label: "320px reflow", width: 320, height: 640 },
  { label: "200% zoom equivalent (640 CSS px)", width: 640, height: 512 },
];

for (const size of SIZES) {
  test.describe(size.label, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    test("sign-in screen fits without horizontal scrolling and stays accessible", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
      const overflow = await horizontalOverflow(page);
      expect(overflow.doc, "document horizontal overflow (px)").toBeLessThanOrEqual(1);
      expect(overflow.body).toBeLessThanOrEqual(1);
      await page.getByRole("button", { name: /Connect with development token/ }).scrollIntoViewIfNeeded();
      await expect(page.getByRole("button", { name: /Connect with development token/ })).toBeVisible();
      await expectAccessible(page, `sign-in @ ${size.width}px`);
    });

    for (const screen of ["Overview", "AR", "People directory", "Timesheets"]) {
      test(`authenticated ${screen} reflows without page-level horizontal scrolling`, async ({ page }) => {
        await signIn(page);
        await openNav(page, screen);
        await expect(page.locator(".crumb strong")).toContainText(screen === "AR" ? "AR" : screen.split(" ")[0]);
        const overflow = await horizontalOverflow(page);
        expect(overflow.doc, `${screen} horizontal overflow (px)`).toBeLessThanOrEqual(1);
        await expectAccessible(page, `${screen} @ ${size.width}px`);
      });
    }

    test("the navigation menu can be opened and used", async ({ page }) => {
      await signIn(page);
      const menu = page.getByRole("button", { name: "Open navigation" });
      if (size.width < 900) {
        await expect(menu).toBeVisible();
        await menu.click();
      }
      await page.locator("nav").getByRole("button", { name: /^People directory/ }).click();
      await expect(page.locator(".crumb strong")).toContainText("People");
    });
  });
}

test.describe("mobile devices", () => {
  test.skip(({ isMobile }) => !isMobile, "touch-device checks run only in the mobile projects");
  test("sign in, open the menu and reach a workspace on a touch device without page-level horizontal scrolling", async ({ page }) => {
    await signIn(page);
    expect((await horizontalOverflow(page)).doc).toBeLessThanOrEqual(1);
    await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
    await openNav(page, "AR");
    await expect(page.locator(".crumb strong")).toContainText("AR");
    expect((await horizontalOverflow(page)).doc).toBeLessThanOrEqual(1);
    await expectAccessible(page, "AR on mobile device");
  });

  test("touch targets of primary controls are at least 24x24 CSS px (WCAG 2.2 target size minimum)", async ({ page }) => {
    await signIn(page);
    const small = await page.evaluate(() => [...document.querySelectorAll("button, a[href], input, select, textarea")]
      .filter(el => el.offsetParent !== null && !el.closest("nav"))
      .map(el => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 0 && (r.width < 24 || r.height < 24))
      .map(({ el, r }) => `${Math.round(r.width)}x${Math.round(r.height)} ${el.outerHTML.slice(0, 70)}`));
    expect(small).toEqual([]);
  });
});
