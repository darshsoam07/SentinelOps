"""Create an Ed25519 pair in a new, private directory; never overwrite keys."""

import argparse
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / ".keys",
    )
    directory = parser.parse_args().directory
    directory.mkdir(mode=0o700, exist_ok=False)
    key = Ed25519PrivateKey.generate()
    for filename, pem in [
        (
            "private.pem",
            key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()),
        ),
        (
            "public.pem",
            key.public_key().public_bytes(
                Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
            ),
        ),
    ]:
        path = directory / filename
        path.write_bytes(pem)
        path.chmod(0o444)  # Non-root Compose UID reads its individually mounted file.
