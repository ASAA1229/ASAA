const AUTHORITY = (import.meta.env.VITE_OIDC_AUTHORITY || "").replace(/\/$/, "");
const CLIENT_ID = import.meta.env.VITE_OIDC_CLIENT_ID || "";
const REDIRECT_URI = import.meta.env.VITE_OIDC_REDIRECT_URI || window.location.origin;
const SCOPE = import.meta.env.VITE_OIDC_SCOPES || "openid profile email";

const TRANSACTION_KEY = "asaa.oidc.transaction.v1";

function decodeBase64Url(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(normalized + "=".repeat((4 - normalized.length % 4) % 4)), char => char.charCodeAt(0));
}
function decodeJsonPart(value) { return JSON.parse(new TextDecoder().decode(decodeBase64Url(value))); }
function assertHttps(url, label) {
  const parsed = new URL(url);
  if (parsed.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(parsed.hostname)) throw new Error(label + " must use HTTPS.");
}
async function verifyIdToken(idToken, transaction) {
  if (!idToken || !transaction.jwksUri) throw new Error("The identity provider did not return a verifiable ID token.");
  const parts = idToken.split(".");
  if (parts.length !== 3) throw new Error("The identity provider returned a malformed ID token.");
  const header = decodeJsonPart(parts[0]); const claims = decodeJsonPart(parts[1]);
  if (header.alg !== "RS256" || !header.kid) throw new Error("The ID token signing algorithm or key identifier is unsupported.");
  const response = await fetch(transaction.jwksUri); if (!response.ok) throw new Error("The identity provider signing keys could not be loaded.");
  const jwks = await response.json();
  const jwk = (jwks.keys || []).find(key => key.kid === header.kid && key.kty === "RSA" && (!key.use || key.use === "sig") && (!key.alg || key.alg === "RS256"));
  if (!jwk) throw new Error("The ID token signing key was not found in the provider JWKS.");
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, decodeBase64Url(parts[2]), new TextEncoder().encode(parts[0] + "." + parts[1]));
  const now = Math.floor(Date.now() / 1000); const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!valid || claims.iss !== transaction.issuer || !audiences.includes(CLIENT_ID) || !Number.isFinite(claims.exp) || claims.exp <= now || !Number.isFinite(claims.iat) || claims.iat > now + 60 || claims.nonce !== transaction.nonce || !claims.sub) throw new Error("The identity provider ID token failed signature, issuer, audience, time or nonce validation.");
}


function randomString(bytes = 32) {
  const value = new Uint8Array(bytes);
  crypto.getRandomValues(value);
  return btoa(String.fromCharCode(...value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function challenge(verifier) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return btoa(String.fromCharCode(...new Uint8Array(digest))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function discovery() {
  if (!AUTHORITY || !CLIENT_ID) throw new Error("SSO is not configured. Set the OIDC authority and public client ID.");
  assertHttps(AUTHORITY, "OIDC authority");
  const response = await fetch(AUTHORITY + "/.well-known/openid-configuration");
  if (!response.ok) throw new Error("The identity provider discovery endpoint is unavailable.");
  const metadata = await response.json();
  if (!metadata.authorization_endpoint || !metadata.token_endpoint || !metadata.jwks_uri || metadata.issuer !== AUTHORITY) throw new Error("The identity provider metadata is incomplete or its issuer does not match the configured authority.");
  assertHttps(metadata.authorization_endpoint, "OIDC authorization endpoint");
  assertHttps(metadata.token_endpoint, "OIDC token endpoint");
  assertHttps(metadata.jwks_uri, "OIDC JWKS endpoint");
  return metadata;
}

export const isSsoConfigured = Boolean(AUTHORITY && CLIENT_ID);

export async function startSsoSignIn() {
  const metadata = await discovery();
  const state = randomString();
  const nonce = randomString();
  const verifier = randomString(48);
  const codeChallenge = await challenge(verifier);
  sessionStorage.setItem(TRANSACTION_KEY, JSON.stringify({
    state, nonce, verifier, tokenEndpoint: metadata.token_endpoint, jwksUri: metadata.jwks_uri,
    issuer: metadata.issuer, redirectUri: REDIRECT_URI, createdAt: Date.now()
  }));
  const url = new URL(metadata.authorization_endpoint);
  url.searchParams.set("client_id", CLIENT_ID);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("redirect_uri", REDIRECT_URI);
  url.searchParams.set("scope", SCOPE);
  url.searchParams.set("state", state);
  url.searchParams.set("nonce", nonce);
  url.searchParams.set("code_challenge", codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  window.location.assign(url.toString());
}

export async function completeSsoSignIn() {
  const current = new URL(window.location.href);
  const code = current.searchParams.get("code");
  const returnedState = current.searchParams.get("state");
  const providerError = current.searchParams.get("error");
  if (!code && !providerError) return null;
  window.history.replaceState({}, document.title, current.pathname + current.hash);
  const raw = sessionStorage.getItem(TRANSACTION_KEY);
  sessionStorage.removeItem(TRANSACTION_KEY);
  if (providerError) throw new Error(current.searchParams.get("error_description") || providerError);
  if (!raw) throw new Error("The sign-in transaction is missing or expired. Start sign-in again.");
  const transaction = JSON.parse(raw);
  if (!returnedState || returnedState !== transaction.state || Date.now() - transaction.createdAt > 10 * 60 * 1000) {
    throw new Error("The sign-in state is invalid or expired. Start sign-in again.");
  }
  const body = new URLSearchParams({
    grant_type: "authorization_code", client_id: CLIENT_ID, code,
    redirect_uri: transaction.redirectUri, code_verifier: transaction.verifier
  });
  const response = await fetch(transaction.tokenEndpoint, {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body
  });
  if (!response.ok) throw new Error("The identity provider rejected the authorization-code exchange.");
  const result = await response.json();
  if (!result.access_token || result.token_type?.toLowerCase() !== "bearer") throw new Error("The identity provider did not return a bearer access token.");
  await verifyIdToken(result.id_token, transaction);
  return result.access_token;
}
