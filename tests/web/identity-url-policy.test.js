import test from "node:test";
import assert from "node:assert/strict";

import { assertHttps } from "../../src/identity/urlPolicy.js";

test("accepts HTTPS identity endpoints", () => {
  assert.doesNotThrow(() => assertHttps("https://identity.example/keys", "OIDC JWKS endpoint"));
});

test("allows HTTP only for local development endpoints", () => {
  assert.doesNotThrow(() => assertHttps("http://localhost:8080/keys", "OIDC JWKS endpoint"));
  assert.doesNotThrow(() => assertHttps("http://127.0.0.1:8080/keys", "OIDC JWKS endpoint"));
});

test("rejects remote HTTP identity endpoints", () => {
  assert.throws(
    () => assertHttps("http://identity.example/keys", "OIDC JWKS endpoint"),
    /must use HTTPS/
  );
});

test("rejects non-HTTP schemes for remote identity endpoints", () => {
  assert.throws(
    () => assertHttps("ftp://identity.example/keys", "OIDC JWKS endpoint"),
    /must use HTTPS/
  );
});

test("allows the local Keycloak realm over loopback HTTP but not the same path on another host", () => {
  assert.doesNotThrow(() => assertHttps("http://127.0.0.1:8280/realms/asaa", "OIDC authority"));
  assert.doesNotThrow(() => assertHttps("http://127.0.0.1:8280/realms/asaa/protocol/openid-connect/certs", "OIDC JWKS endpoint"));
  assert.throws(() => assertHttps("http://keycloak.example:8280/realms/asaa", "OIDC authority"), /must use HTTPS/);
  assert.throws(() => assertHttps("http://127.0.0.1.evil.example/realms/asaa", "OIDC authority"), /must use HTTPS/);
});

test("allows IPv6 loopback over HTTP, including the Keycloak realm paths", () => {
  assert.doesNotThrow(() => assertHttps("http://[::1]:8280/realms/asaa", "OIDC authority"));
  assert.doesNotThrow(() => assertHttps("http://[::1]/keys", "OIDC JWKS endpoint"));
  assert.doesNotThrow(() => assertHttps("http://[0:0:0:0:0:0:0:1]:8280/keys", "OIDC JWKS endpoint"));
});

test("rejects other IPv6 addresses and loopback lookalikes over HTTP", () => {
  for (const url of ["http://[::2]/keys", "http://[2001:db8::1]/keys", "http://[::ffff:8.8.8.8]/keys", "http://::1.evil.example/keys",
    "http://localhost.evil.example/keys", "http://127.0.0.1.evil.example/keys", "http://127.0.0.2/keys", "http://user@evil.example/keys"]) {
    assert.throws(() => assertHttps(url, "OIDC authority"), /must use HTTPS|Invalid URL/, url);
  }
});
