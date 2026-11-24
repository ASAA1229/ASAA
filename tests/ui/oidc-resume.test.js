import { afterEach, describe, expect, it } from "vitest";
import { clearSsoSession, completeSsoSignIn, shouldResumeSso } from "../../src/identity/oidc.js";

const TRANSACTION_KEY = "asaa.oidc.transaction.v1";
const HINT_KEY = "asaa.oidc.session.v1";

function visit(query) { window.history.replaceState({}, "", `/${query}`); }

describe("SSO session resume after a page reload (E3:D3.24)", () => {
  afterEach(() => { sessionStorage.clear(); visit(""); });

  it("never stores the access token in browser storage", async () => {
    sessionStorage.setItem(TRANSACTION_KEY, JSON.stringify({ state: "s1", silent: true, createdAt: Date.now() }));
    visit("?error=login_required&state=s1");
    await completeSsoSignIn();
    for (let i = 0; i < sessionStorage.length; i += 1) expect(sessionStorage.getItem(sessionStorage.key(i))).not.toMatch(/^ey/);
    for (let i = 0; i < localStorage.length; i += 1) expect(localStorage.getItem(localStorage.key(i))).not.toMatch(/^ey/);
  });

  it("falls back quietly to the sign-in screen when a silent resume finds no provider session", async () => {
    sessionStorage.setItem(TRANSACTION_KEY, JSON.stringify({ state: "s1", silent: true, createdAt: Date.now() }));
    visit("?error=login_required&state=s1");
    await expect(completeSsoSignIn()).resolves.toBeNull();
    expect(sessionStorage.getItem(TRANSACTION_KEY)).toBeNull();
    expect(window.location.search).toBe("");
  });

  it("still reports provider errors for an interactive sign-in", async () => {
    sessionStorage.setItem(TRANSACTION_KEY, JSON.stringify({ state: "s1", silent: false, createdAt: Date.now() }));
    visit("?error=access_denied&error_description=denied&state=s1");
    await expect(completeSsoSignIn()).rejects.toThrow("denied");
  });

  it("does not resume without a prior SSO session, on a callback URL, or after sign-out", () => {
    expect(shouldResumeSso()).toBe(false);
    sessionStorage.setItem(HINT_KEY, "1");
    visit("?code=abc&state=s1");
    expect(shouldResumeSso()).toBe(false);
    visit("");
    clearSsoSession();
    expect(sessionStorage.getItem(HINT_KEY)).toBeNull();
    expect(shouldResumeSso()).toBe(false);
  });
});
