"""Print throw-away rehearsal credentials as JSON: {"public_key": PEM, "token": JWT}. Nothing is persisted."""
import json
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
now = datetime.now(timezone.utc)
token = jwt.encode({"sub": "rehearsal-admin", "org_id": "rehearsal-org", "iss": "https://rehearsal.invalid", "aud": "asaa-rehearsal",
                    "iat": now, "exp": now + timedelta(minutes=45),
                    "permissions": ["supplier:read", "supplier:write"]}, key, algorithm="RS256")
public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
print(json.dumps({"public_key": public, "token": token}))
