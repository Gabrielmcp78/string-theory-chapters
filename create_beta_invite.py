#!/usr/bin/env python3
"""create_beta_invite.py — Create a Firestore beta-reader invite and QR code.

Usage:
  uv run --with google-cloud-firestore --with 'qrcode[pil]' \\
    python3 create_beta_invite.py "Beth" --out /path/to/beth-qr.png
"""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path

import qrcode
from google.cloud import firestore

PROJECT_ID = "string-theory-reader"
BASE_URL = "https://gabrielmcp78.github.io/string-theory-chapters/index.html"


def create_invite(name: str, out_path: Path, code: str | None = None) -> tuple[str, str]:
    """Create an active beta-reader invite in Firestore and write its QR code PNG."""
    slug = "".join(c.lower() for c in name if c.isalnum())[:12] or "reader"
    invite_code = code or f"{slug}-{secrets.token_urlsafe(8)}"
    client = firestore.Client(project=PROJECT_ID)
    client.collection("invites").document(invite_code).set(
        {
            "name": name,
            "role": "beta-reader",
            "active": True,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )
    url = f"{BASE_URL}?invite={invite_code}"
    img = qrcode.make(url)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return invite_code, url


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("name", help="Reader display name (e.g. Beth)")
    ap.add_argument("--code", default=None, help="Optional explicit invite code")
    ap.add_argument("--out", required=True, help="Output PNG path for the QR code")
    args = ap.parse_args()
    code, url = create_invite(args.name, Path(args.out), code=args.code)
    print(f"Created invite for {args.name}")
    print(f"Code: {code}")
    print(f"URL:  {url}")
    print(f"QR:   {args.out}")


if __name__ == "__main__":
    main()
