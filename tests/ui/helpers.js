import axe from "axe-core";

/** Build an unsigned JWT-shaped token; the portal only decodes claims for display/permission gating. */
export function makeToken(claims) {
  const b64 = value => btoa(JSON.stringify(value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `${b64({ alg: "none" })}.${b64(claims)}.sig`;
}

/** Install a fetch mock routing by path. Handlers return a body or {status, body}. */
export function mockApi(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    const path = new URL(url).pathname;
    const method = (options.method || "GET").toUpperCase();
    calls.push({ path, method, body: options.body ? JSON.parse(options.body) : undefined, headers: options.headers });
    const handler = routes[`${method} ${path}`];
    if (handler === undefined) return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    const result = typeof handler === "function" ? handler(options) : handler;
    const { status = 200, body = result } = result && result.__response ? result : {};
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  };
  return calls;
}

export const respond = (status, body) => ({ __response: true, status, body });

/** Run axe against a DOM node. Color contrast needs real layout/rendering, so it is not evaluated in jsdom. */
export async function axeViolations(node) {
  const results = await axe.run(node, {
    rules: { "color-contrast": { enabled: false } },
    resultTypes: ["violations"],
  });
  return results.violations.map(v => `${v.id} (${v.impact}): ${v.nodes.map(n => n.target.join(" ")).join(" | ")}`);
}
