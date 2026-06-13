"""Append-only sha256 hash-chained audit ledger, plus deterministic precedent.

The ledger IS Keystone's memory (master-prompt Section N). Each gate decision
appends one row whose row_hash binds the payload to the previous row's hash, so a
single edit anywhere breaks the chain and verify() reports the first broken index.
Nothing here learns; precedent() is deterministic recall and counting over rows
that already exist. No LLM, no web imports, standard library only.

Row shape:
  {seq, ts, actor, change_id, target_symbols[], blast_radius_set[], signature,
   decision ('approve'|'reject'), rationale, prev_hash, row_hash}
row_hash = sha256(prev_hash + canonical_json(payload_without_row_hash))
genesis prev_hash = 64 zeros.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from typing import Optional

GENESIS_PREV = "0" * 64

# Integrity key. When a key is available the chain is HMAC-keyed, so a party that
# can append rows still cannot forge a valid tail without the key (plain sha256
# would let anyone recompute the chain). The key is taken from KEYSTONE_LEDGER_KEY
# if set, otherwise a random key is generated once and persisted OUTSIDE the repo
# at ~/.keystone/ledger.key, so it is never committed and a repo-only attacker
# cannot forge appends. Identity of the reviewer is a separate concern (see the
# README integrity note and the optional approve token in the backend).
_KEY_LOCK = threading.Lock()
_CACHED_KEY: Optional[bytes] = None


def _ledger_key() -> bytes:
    global _CACHED_KEY
    if _CACHED_KEY is not None:
        return _CACHED_KEY
    with _KEY_LOCK:
        if _CACHED_KEY is not None:
            return _CACHED_KEY
        env = os.environ.get("KEYSTONE_LEDGER_KEY")
        if env:
            _CACHED_KEY = env.encode("utf-8")
            return _CACHED_KEY
        key_dir = os.path.join(os.path.expanduser("~"), ".keystone")
        key_path = os.path.join(key_dir, "ledger.key")
        try:
            if os.path.exists(key_path):
                with open(key_path, "rb") as f:
                    _CACHED_KEY = f.read().strip()
            if not _CACHED_KEY:
                os.makedirs(key_dir, exist_ok=True)
                _CACHED_KEY = os.urandom(32).hex().encode("utf-8")
                with open(key_path, "wb") as f:
                    f.write(_CACHED_KEY)
        except OSError:
            # Last resort: a process-local key. Chain still verifies within the
            # process; persistence across restarts needs a writable home or env key.
            _CACHED_KEY = os.urandom(32).hex().encode("utf-8")
        return _CACHED_KEY


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _row_hash(prev_hash: str, payload: dict) -> str:
    return hmac.new(_ledger_key(), (prev_hash + _canonical(payload)).encode("utf-8"),
                    hashlib.sha256).hexdigest()


# Serialises append's read-prev-hash-then-write across threads in one process, so
# two concurrent POST /api/approve calls cannot share a prev_hash and break the
# chain. Multi-worker/multi-host deployments need an external mutex or a DB-backed
# ledger (documented in the README integrity note).
_APPEND_LOCK = threading.Lock()


class Ledger:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def _read_raw(self) -> list:
        if not os.path.exists(self.path):
            return []
        rows = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def rows(self) -> list:
        """Newest-first for display."""
        return list(reversed(self._read_raw()))

    def append(self, *, actor: str, change_id: str, target_symbols, blast_radius_set,
               signature: str, decision: str, rationale: str, ts: Optional[str] = None) -> dict:
        if decision not in ("approve", "reject"):
            raise ValueError("decision must be approve or reject")
        with _APPEND_LOCK:
            existing = self._read_raw()
            prev_hash = existing[-1]["row_hash"] if existing else GENESIS_PREV
            seq = len(existing)
            payload = {
                "seq": seq,
                "ts": ts or _fixed_ts(seq),
                "actor": actor,
                "change_id": change_id,
                "target_symbols": list(target_symbols),
                "blast_radius_set": sorted(int(x) for x in blast_radius_set),
                "signature": signature,
                "decision": decision,
                "rationale": rationale,
                "prev_hash": prev_hash,
            }
            payload["row_hash"] = _row_hash(prev_hash, payload)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(_canonical(payload) + "\n")
        return payload

    def verify(self) -> dict:
        """Recompute the whole chain. Returns {ok, count, broken_index|None}."""
        rows = self._read_raw()
        prev = GENESIS_PREV
        for idx, row in enumerate(rows):
            stored = row.get("row_hash")
            payload = {k: v for k, v in row.items() if k != "row_hash"}
            if payload.get("prev_hash") != prev:
                return {"ok": False, "count": len(rows), "broken_index": idx}
            if _row_hash(prev, payload) != stored:
                return {"ok": False, "count": len(rows), "broken_index": idx}
            prev = stored
        return {"ok": True, "count": len(rows), "broken_index": None}

    def precedent(self, *, target_symbols=None, signature: str = None, owner: str = None) -> dict:
        """Deterministic recall: prior rows matching the current change by exact
        symbol overlap OR same blast-radius signature OR same owner. Counts
        approvals/rejections, returns the most recent matching rationale, and
        flags a contradiction (a prior REJECT on the same signature)."""
        target_symbols = set(target_symbols or [])
        rows = self._read_raw()
        matches = []
        for row in rows:
            hit = False
            if signature and row.get("signature") == signature:
                hit = True
            if target_symbols and target_symbols.intersection(set(row.get("target_symbols", []))):
                hit = True
            if owner and owner == row.get("owner"):
                hit = True
            if hit:
                matches.append(row)
        approvals = [r for r in matches if r["decision"] == "approve"]
        rejections = [r for r in matches if r["decision"] == "reject"]
        most_recent = matches[-1] if matches else None
        # A contradiction is a prior REJECTION of a matching change (same symbol or
        # same blast signature). It is the load-bearing "you are about to approve
        # something that was rejected before" beat. The strongest form is a
        # signature-identical rejection.
        contradiction = rejections[-1] if rejections else None
        contradiction_same_signature = bool(
            contradiction and signature and contradiction.get("signature") == signature
        )
        # Strength: an identical blast signature is the strong "you are about to
        # approve the exact thing that was rejected" beat; a same-symbol match with
        # a DIFFERENT blast radius is a weaker advisory (the symbol was rejected
        # before, but for a different impact), which the UI shows as a warning, not
        # a full contradiction. Prevents phantom contradictions on unrelated changes.
        if contradiction is None:
            contradiction_strength = None
        elif contradiction_same_signature:
            contradiction_strength = "identical"
        else:
            contradiction_strength = "symbol"
        return {
            "match_count": len(matches),
            "approved": len(approvals),
            "rejected": len(rejections),
            "most_recent": most_recent,
            "contradiction": contradiction,
            "contradiction_same_signature": contradiction_same_signature,
            "contradiction_strength": contradiction_strength,
            "matched_rows": [{"seq": m["seq"], "row_hash": m["row_hash"],
                              "decision": m["decision"], "actor": m["actor"],
                              "rationale": m["rationale"]} for m in matches],
        }


def _fixed_ts(seq: int) -> str:
    """Deterministic timestamp for reproducible fixtures and tests."""
    return f"2026-06-{10 + (seq % 14):02d}T10:{(seq * 7) % 60:02d}:00Z"
