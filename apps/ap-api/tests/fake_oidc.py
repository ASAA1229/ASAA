"""A local fake OpenID Connect provider (authorization code + PKCE S256, RS256, JWKS with rotation, optional MFA claims).

For tests and E2E only. It is NOT a real provider and says nothing about any vendor's behaviour or configuration.
"""
import base64
import hashlib
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeOidc:
    def __init__(self, client_id="asaa-portal", audience="asaa-api", mfa=True, permissions=None, org_id="org-a", subject="user-1"):
        self.client_id, self.audience, self.mfa, self.org_id, self.subject = client_id, audience, mfa, org_id, subject
        self.permissions = permissions if permissions is not None else ["supplier:read"]
        self.keys: dict[str, rsa.RSAPrivateKey] = {}
        self.active_kid = ""
        self.codes: dict[str, dict] = {}
        self.add_key()
        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.issuer = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    # --- keys ----------------------------------------------------------------
    def add_key(self) -> str:
        kid = "key-" + secrets.token_hex(4)
        self.keys[kid] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.active_kid = kid
        return kid

    def rotate(self, retire_old: bool = False) -> str:
        old = list(self.keys)
        kid = self.add_key()
        if retire_old:
            for k in old:
                self.keys.pop(k)
        return kid

    def jwks(self) -> dict:
        keys = []
        for kid, key in self.keys.items():
            numbers = key.public_key().public_numbers()
            keys.append({"kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
                         "n": b64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")), "e": b64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big"))})
        return {"keys": keys}

    def public_pem(self, kid=None) -> str:
        return self.keys[kid or self.active_kid].public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    # --- tokens --------------------------------------------------------------------
    def access_token(self, expires_in=300, **overrides) -> str:
        now = int(time.time())
        claims = {"sub": self.subject, "org_id": self.org_id, "iss": self.issuer, "aud": self.audience, "iat": now, "exp": now + expires_in, "permissions": self.permissions}
        if self.mfa:
            claims.update({"acr": "urn:asaa:loa:2", "amr": ["pwd", "otp"]})
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, self.keys[self.active_kid], algorithm="RS256", headers={"kid": self.active_kid})

    def id_token(self, nonce: str) -> str:
        now = int(time.time())
        claims = {"sub": self.subject, "iss": self.issuer, "aud": self.client_id, "iat": now, "exp": now + 300, "nonce": nonce}
        return jwt.encode(claims, self.keys[self.active_kid], algorithm="RS256", headers={"kid": self.active_kid})

    # --- HTTP -------------------------------------------------------------------------
    def discovery(self) -> dict:
        return {"issuer": self.issuer, "authorization_endpoint": self.issuer + "/authorize", "token_endpoint": self.issuer + "/token", "jwks_uri": self.issuer + "/jwks",
                "response_types_supported": ["code"], "code_challenge_methods_supported": ["S256"], "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": ["openid", "profile", "email"]}

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, status, body, headers=None):
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(payload)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()

            def do_GET(self):
                url = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                if url.path == "/.well-known/openid-configuration":
                    return self._json(200, fake.discovery())
                if url.path == "/jwks":
                    return self._json(200, fake.jwks())
                if url.path == "/authorize":
                    if q.get("client_id") != fake.client_id or q.get("response_type") != "code" or q.get("code_challenge_method") != "S256" or not q.get("code_challenge") or not q.get("redirect_uri"):
                        return self._json(400, {"error": "invalid_request"})
                    code = secrets.token_urlsafe(16)
                    with fake.lock:
                        fake.codes[code] = {"challenge": q["code_challenge"], "redirect_uri": q["redirect_uri"], "nonce": q.get("nonce", ""), "used": False}
                    self.send_response(302)
                    self.send_header("Location", q["redirect_uri"] + ("&" if "?" in q["redirect_uri"] else "?") + urlencode({"code": code, "state": q.get("state", "")}))
                    self.end_headers()
                    return
                self._json(404, {"error": "not_found"})

            def do_POST(self):
                if urlparse(self.path).path != "/token":
                    return self._json(404, {"error": "not_found"})
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()).items()}
                with fake.lock:
                    entry = fake.codes.get(form.get("code", ""))
                    if not entry or entry["used"]:
                        return self._json(400, {"error": "invalid_grant"})
                    entry["used"] = True  # authorization codes are single use
                if form.get("client_id") != fake.client_id or form.get("redirect_uri") != entry["redirect_uri"] or form.get("grant_type") != "authorization_code":
                    return self._json(400, {"error": "invalid_grant"})
                verifier = form.get("code_verifier", "")
                if b64url(hashlib.sha256(verifier.encode()).digest()) != entry["challenge"]:
                    return self._json(400, {"error": "invalid_grant", "error_description": "PKCE verification failed"})
                self._json(200, {"access_token": fake.access_token(), "token_type": "Bearer", "expires_in": 300, "id_token": fake.id_token(entry["nonce"])})

        return Handler
