import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import inventory from "../../src/workspaces/inventory.json";
import { MODULE_GROUPS, REGISTER_WORKSPACES, ROUTED_WORKSPACES, WIRED_WORKSPACES } from "../../src/workspaces/registry.js";

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

  it("marks a workspace functional exactly when it is wired, and preview exactly when it is not routed at all", () => {
    for (const w of inventory.workspaces) {
      const routed = ROUTED_WORKSPACES.includes(w.name);
      expect(routed, `${w.name}: state=${w.state}`).toBe(w.state !== "preview");
      const functional = WIRED_WORKSPACES.includes(w.name);
      expect(functional, `${w.name}: state=${w.state}`).toBe(w.state === "functional");
    }
    for (const name of ROUTED_WORKSPACES) expect(byName.has(name), `routed workspace ${name} must be in the registry`).toBe(true);
  });

  it("keeps every register-backed workspace on a register type that exists in the API catalogue", () => {
    const catalogue = readFileSync("apps/ap-api/src/asaa_registers/catalog.py", "utf8");
    const keys = [...catalogue.matchAll(/RegisterType\("([a-z_]+)"/g)].map(m => m[1]);
    for (const [workspace, types] of Object.entries(REGISTER_WORKSPACES)) {
      for (const type of types) expect(keys, `${workspace} -> ${type}`).toContain(type);
    }
  });

  it("never reports a partial workspace without explaining what is missing", () => {
    for (const w of inventory.workspaces.filter(x => x.state === "partial")) expect(w.notes, w.name).toMatch(/NOT implemented|not implemented|no UI|generic|incomplete/i);
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
