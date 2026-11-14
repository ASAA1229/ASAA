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
