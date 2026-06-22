"""Reviewer-side Ed25519 keygen + decision signing - the local action that makes a Keystone
approval cryptographically attributable, with NO external service or account.

A reviewer proves WHO approved by possession of a private key (the same model as a signed Git
commit or SSH key). They register the PUBLIC key once in .keystone/reviewers.json, then sign each
decision; the backend (POST /api/approve with an X-Keystone-Signature header) verifies the signature
against the registered public key and records the proof in the tamper-evident ledger.

Usage:
  python scripts/sign_decision.py keygen
      -> prints a fresh (private hex, public hex). Keep the private key secret; add the public key
         to .keystone/reviewers.json under your reviewer id.

  python scripts/sign_decision.py sign --reviewer alice --change-id MR-42 --decision approve \
      --symbol tokenize --private <PRIVATE_HEX>
      -> prints the signature hex to send as the X-Keystone-Signature header.

  python scripts/sign_decision.py demo
      -> signs a sample decision with the committed DEMO reviewer key (clearly non-production;
         the demo private key below is published on purpose so the live demo works out of the box).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import identity  # noqa: E402

# Published DEMO key (NOT a secret - the public half is in .keystone/reviewers.json under
# 'keystone-demo-reviewer', exactly like the published public-sample ledger key). Real reviewers
# generate their own with `keygen` and never publish the private half.
_DEMO_PRIVATE = "b2cada4ac7c260443cd4deb7b444072dd75ac288ec2eaaadeedbf53771dee27c"


def main() -> int:
    ap = argparse.ArgumentParser(description="Keystone reviewer Ed25519 keygen + decision signing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen")
    s = sub.add_parser("sign")
    s.add_argument("--reviewer", required=True)
    s.add_argument("--change-id", default="")
    s.add_argument("--decision", default="approve", choices=["approve", "reject"])
    s.add_argument("--symbol", action="append", default=[], required=True)
    s.add_argument("--private", required=True)
    sub.add_parser("demo")
    a = ap.parse_args()

    if a.cmd == "keygen":
        priv, pub = identity.generate_keypair()
        print("private (keep secret): " + priv)
        print("public  (register):    " + pub)
        return 0

    if a.cmd == "demo":
        payload = identity.signing_payload("keystone-demo-reviewer", "MR-1", "approve", ["tokenize"])
        sig = identity.sign_decision(_DEMO_PRIVATE, payload)
        print("reviewer:  keystone-demo-reviewer")
        print("payload:   " + str(payload))
        print("signature: " + sig)
        print("send header: X-Keystone-Signature: " + sig)
        return 0

    payload = identity.signing_payload(a.reviewer, a.change_id, a.decision, a.symbol)
    print(identity.sign_decision(a.private, payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
