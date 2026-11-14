import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "../../src/App.jsx";
import { axeViolations, mockApi } from "./helpers.js";

// Launch-scope workspaces called out in the release plan.
const LAUNCH_SCREENS = [
  "AR", "AP", "Procurement", "Timesheets", "Expenses", "People directory", "Employment lifecycle", "Onboarding",
  "Offboarding", "Leave management", "Compensation & payroll", "Organization & entities", "Departments & teams",
  "Master data", "Identity & access", "Access reviews", "Settings",
];

describe("unauthenticated preview", () => {
  it("shows no live records, makes no API calls and states that it is a preview", async () => {
    const calls = mockApi({});
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Explore all module UIs/ }));
    expect(await screen.findByText(/UI preview mode/)).toBeInTheDocument();
    expect(screen.getByText("Not connected")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });

  it("every launch workspace renders without error, makes no API call and passes axe", async () => {
    const calls = mockApi({});
    const { container } = render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Explore all module UIs/ }));
    const violations = [];
    for (const name of LAUNCH_SCREENS) {
      const button = within(container.querySelector("nav")).getAllByRole("button").find(b => b.textContent.startsWith(name));
      expect(button, `nav entry for ${name}`).toBeDefined();
      await userEvent.click(button);
      violations.push(...(await axeViolations(container)).map(v => `${name}: ${v}`));
    }
    expect(violations).toEqual([]);
    expect(calls).toHaveLength(0);
  }, 120000);

  it("module search filters the navigation and can be cleared", async () => {
    mockApi({});
    const { container } = render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Explore all module UIs/ }));
    const input = screen.getByPlaceholderText(/Find a module/);
    await userEvent.type(input, "payroll");
    const nav = container.querySelector("nav");
    expect(within(nav).getAllByRole("button").length).toBeLessThan(5);
    await userEvent.click(screen.getByRole("button", { name: "Clear module search" }));
    expect(within(nav).getAllByRole("button").length).toBeGreaterThan(20);
  });

  it("mobile navigation buttons are exposed to assistive technology with names", async () => {
    mockApi({});
    render(<App />);
    expect(screen.getByRole("button", { name: "Open navigation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close navigation" })).toBeInTheDocument();
  });
});
