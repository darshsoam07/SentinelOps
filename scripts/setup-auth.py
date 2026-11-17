"""Provision a private local operator configuration without printing credentials."""

import getpass
import os
from pathlib import Path
import secrets
import shlex
from pwdlib import PasswordHash

path = Path(__file__).resolve().parents[1] / ".env.auth"
if path.exists():
    raise SystemExit("Existing .env.auth preserved.")
password = getpass.getpass("Choose operator password (12+ characters): ")
if len(password) < 12 or password != getpass.getpass("Confirm password: "):
    raise SystemExit("Password length or confirmation failed.")
values = {
    "SENTINELOPS_OPERATOR": "operator",
    "SENTINELOPS_PASSWORD_HASH": PasswordHash.recommended().hash(password),
    "SENTINELOPS_JWT_SECRET": secrets.token_hex(32),
}
with os.fdopen(
    os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
) as output:
    for name, value in values.items():
        print(f"export {name}={shlex.quote(value)}", file=output)
