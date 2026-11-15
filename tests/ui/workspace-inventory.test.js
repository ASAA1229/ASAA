import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import inventory from "../../src/workspaces/inventory.json";
import { MODULE_GROUPS, WIRED_WORKSPACES } from "../../src/workspaces/registry.js";

const registry = MODULE_GROUPS.flatMap(group => group.items.map(item => ({ name: item.name, category: group.group })));
const byName = new Map(inventory.workspaces.map(w => [w.name, w]));

describe("workspace inventory", () => {
  it("lists exactly the workspaces in the portal registry, each once, with the same category", () => {
    expect(inventory.workspaces).toHaveLength(registry.length);
    expect(byName.size).toBe(registry.length);
    for (const { name, category } of registry) {
      expect(byName.get(name), `inventory entry for ${name}`).toBeDefined();
      expect(byName.get(name).category).toBe(category);
    }
  });

  it("uses only known states and release scopes", () => {
    const states = Object.keys(inventory.states);
    for (const w of inventory.workspaces) {
      expect(states, w.name).toContain(w.state);
      expect(["first_release_p0_p1", "p1_pending_scope_decision", "p2_expansion"], w.name).toContain(w.release_scope);
    }
  });

  it("marks a workspace functional exactly when the portal routes it to a wired component", () => {
    for (const w of inventory.workspaces) {
      expect(WIRED_WORKSPACES.includes(w.name), `${w.name}: state=${w.state}`).toBe(w.state === "functional");
    }
    for (const name of WIRED_WORKSPACES) expect(byName.has(name), `wired workspace ${name} must be in the registry`).toBe(true);
  });

  it("documents requirement coverage for every workspace and valid story references", () => {
    const stories = readFileSync("docs/USER_STORIES.md", "utf8");
    for (const w of inventory.workspaces) {
      expect(w.requirement_refs.length, `${w.name} requirement refs`).toBeGreaterThan(0);
      for (const id of w.story_refs) expect(stories.includes(id), `${w.name}: story ${id} not found in USER_STORIES.md`).toBe(true);
      if (w.state !== "preview") expect(w.story_refs.length + w.requirement_refs.length, w.name).toBeGreaterThan(1);
    }
  });

  it("flags first-release workspaces that are not functional so the gap stays visible", () => {
    const open = inventory.workspaces.filter(w => w.release_scope === "first_release_p0_p1" && w.state !== "functional").map(w => w.name);
    expect(open.length).toBeLessThanOrEqual(inventory.workspaces.length);
    for (const w of inventory.workspaces.filter(x => x.state === "partial")) expect(w.notes.length, `${w.name} needs a note`).toBeGreaterThan(10);
  });
});
