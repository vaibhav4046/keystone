"""Append-only sha256 hash-chained audit ledger, plus deterministic precedent.

The ledger IS Keystone's memory (master-prompt Section N). Each gate decision
appends one row whose row_hash binds the payload to the previous row's hash, so a
single edit anywhere breaks the chain and verify() reports the first broken index.
Nothing here learns; precedent() is deterministic recall and counting over rows
that already exist. No LLM, no web imports, standard library only.

Row shape:
  {seq, ts, actor, change_id, target_symbols[], blast_radius_set[], signature,
   decision ('approve'|'reject'), rationale, prev_hash, row_hash}
row_hash = HMAC-SHA256(ledger_key, prev_hash + canonical_json(payload_without_row_hash))
  (keyed, so a party that can append rows still cannot forge a valid tail without the key;
   see _row_hash and the key note below.)
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
            if len(env.strip()) < 16:
                # A short/low-entropy integrity key makes the HMAC chain trivially forgeable, which
                # defeats the whole tamper-evidence claim. Fail loud rather than accept a 1-byte key.
                raise ValueError("KEYSTONE_LEDGER_KEY is too short (< 16 bytes); the ledger integrity "
                                 "key must be high-entropy or the tamper-evidence is worthless")
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


# The published public sample key (used only by the static-bundle build); a real deployment must
# not be running on it. Exposed via the fingerprint below so a judge can confirm which key is live.
PUBLIC_SAMPLE_KEY = b"keystone-public-sample-v1"


def key_fingerprint() -> str:
    """A non-secret fingerprint of the integrity key, so a deployment can prove it is not using the
    published public sample key without revealing the secret. sha256(key) truncated."""
    return hashlib.sha256(_ledger_key()).hexdigest()[:12]


def using_public_sample_key() -> bool:
    """True when the live key is the published sample key (illustrative chain, not tamper-evident)."""
    return _ledger_key() == PUBLIC_SAMPLE_KEY


def _row_hash(prev_hash: str, payload: dict) -> str:
    return hmac.new(_ledger_key(), (prev_hash + _canonical(payload)).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _head_mac(count: int, last_hash: str) -> str:
    """HMAC over (row count, last row_hash). The per-row chain binds each row to the PREVIOUS one,
    so it catches edits and middle deletions - but NOT a tail truncation (dropping the most recent
    rows leaves every remaining link intact). A signed external HEAD anchor closes that: an attacker
    who truncates the ledger cannot forge a matching head without the key, and a stale head (old
    count) no longer matches the shortened ledger - so the removed decisions are detected."""
    return hmac.new(_ledger_key(), ("%d|%s" % (count, last_hash)).encode("utf-8"),
                    hashlib.sha256).hexdigest()


# Serialises append's read-prev-hash-then-write across threads in one process, so
# two concurrent POST /api/approve calls cannot share a prev_hash and break the
# chain. Multi-worker/multi-host deployments need an external mutex or a DB-backed
# ledger (documented in the README integrity note).
_APPEND_LOCK = threading.Lock()


class Ledger:
    def __init__(self, path: str):
        self.path = path
        self.head_path = path + ".head"   # signed external anchor: count + last row_hash (tail-truncation guard)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def _write_head(self, count: int, last_hash: str) -> None:
        """Persist a signed {count, last_row_hash} anchor atomically (temp + os.replace)."""
        data = {"count": count, "last_row_hash": last_hash, "mac": _head_mac(count, last_hash)}
        tmp = self.head_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(_canonical(data))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.head_path)
        except OSError:
            pass   # a read-only home degrades to no-anchor (verify reports tail_anchored=False)

    def _read_head(self):
        """Return the head dict if its MAC is valid, 'TAMPERED' if the head was forged/edited, or
        None when no anchor exists (then tail-truncation cannot be detected from the log alone)."""
        if not os.path.exists(self.head_path):
            return None
        try:
            with open(self.head_path, "r", encoding="utf-8") as f:
                d = json.loads(f.read())
        except (OSError, ValueError):
            return "TAMPERED"
        if not hmac.compare_digest(str(d.get("mac", "")), _head_mac(d.get("count", -1), d.get("last_row_hash", ""))):
            return "TAMPERED"
        return d

    def _read_raw(self) -> list:
        if not os.path.exists(self.path):
            self._corrupt_lines = 0
            return []
        rows = []
        corrupt = 0
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    corrupt += 1   # a partial/hand-edited line: skip so reads never crash; verify() flags the break
        self._corrupt_lines = corrupt
        return rows

    def rows(self) -> list:
        """Newest-first for display."""
        return list(reversed(self._read_raw()))

    def append(self, *, actor: str, change_id: str, target_symbols, blast_radius_set,
               signature: str, decision: str, rationale: str, ts: Optional[str] = None,
               target_fqns=None, signature_fqn: Optional[str] = None,
               extra: Optional[dict] = None) -> dict:
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
            # Fully-qualified names, when known, so precedent survives same-short-name
            # symbols in different namespaces (e.g. two parse functions). Only stored
            # when provided, so older rows are unaffected.
            if target_fqns:
                payload["target_fqns"] = [f for f in target_fqns if f]
            # Content-addressed blast signature (epicenter FQN + sorted affected FQNs). Stored
            # only when provided, so older rows and their chain hashes are unaffected. This is the
            # re-index-stable precedent key; the id-based `signature` stays for backward compat.
            if signature_fqn:
                payload["signature_fqn"] = signature_fqn
            # governance context (tier, policy hash, orbit snapshot, author kind) is
            # part of the signed payload, so the decision and the policy that judged
            # it are bound together and tamper-evident as one row.
            if extra:
                for k, v in extra.items():
                    if k not in payload:
                        payload[k] = v
            payload["row_hash"] = _row_hash(prev_hash, payload)
            # Append-only and byte-preserving. We DO NOT rewrite existing rows: rewriting from
            # the lossy _read_raw() would silently drop a corrupt/tampered line and erase the
            # evidence (a "self-healing" ledger is not tamper-evident). Instead, refuse to extend
            # a corrupt ledger so the tampering stays visible and blocks new rows until an operator
            # recovers it; a single append + fsync is O(1) and crash-durable.
            if getattr(self, "_corrupt_lines", 0):
                raise RuntimeError(
                    "refusing to append onto a corrupt ledger (%d unparseable line(s)); "
                    "the chain is broken and must be recovered before new decisions are recorded"
                    % self._corrupt_lines)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(_canonical(payload) + "\n")
                f.flush()
                os.fsync(f.fileno())
            # update the signed tail anchor INSIDE the append lock so it always reflects the row
            # just written (count = seq + 1, since seq is the 0-based index of this new row).
            self._write_head(seq + 1, payload["row_hash"])
        return payload

    def verify(self) -> dict:
        """Recompute the whole chain. Returns {ok, count, broken_index|None, tail_anchored}.

        The per-row HMAC links catch edits + middle deletions; the signed HEAD anchor additionally
        catches TAIL TRUNCATION (deleting the most recent rows). tail_anchored is False when no
        anchor file exists yet (then truncation is undetectable from the log alone - disclosed)."""
        rows = self._read_raw()
        if getattr(self, "_corrupt_lines", 0):
            return {"ok": False, "count": len(rows), "broken_index": None, "corrupt": True}
        prev = GENESIS_PREV
        for idx, row in enumerate(rows):
            stored = row.get("row_hash")
            payload = {k: v for k, v in row.items() if k != "row_hash"}
            if payload.get("prev_hash") != prev:
                return {"ok": False, "count": len(rows), "broken_index": idx}
            if _row_hash(prev, payload) != stored:
                return {"ok": False, "count": len(rows), "broken_index": idx}
            prev = stored
        # tail-truncation guard: the signed anchor must match the ledger's true length + last hash.
        head = self._read_head()
        if head == "TAMPERED":
            return {"ok": False, "count": len(rows), "broken_index": None, "head_tampered": True}
        if isinstance(head, dict):
            expected_last = rows[-1]["row_hash"] if rows else GENESIS_PREV
            if head.get("count") != len(rows) or head.get("last_row_hash") != expected_last:
                return {"ok": False, "count": len(rows), "broken_index": None, "truncated": True}
            return {"ok": True, "count": len(rows), "broken_index": None, "tail_anchored": True}
        return {"ok": True, "count": len(rows), "broken_index": None, "tail_anchored": False}

    def precedent(self, *, target_symbols=None, signature: str = None, target_fqns=None,
                  signature_fqn: str = None) -> dict:
        """Deterministic recall: prior rows matching the current change by content-addressed
        blast signature (epicenter FQN + affected FQN set), exact fully-qualified name, same
        id-based blast signature, OR exact short symbol overlap. Counts approvals/rejections,
        returns the most recent matching rationale, and flags a contradiction (a prior REJECT
        on a match). The content-addressed `signature_fqn` is preferred because it survives a
        re-index (volatile row ids change; FQNs do not) and a rename of the epicenter is still
        caught by the FQN-overlap match since the dependent set is unchanged."""
        target_symbols = set(target_symbols or [])
        target_fqns = set(target_fqns or [])
        rows = self._read_raw()
        matches = []
        for row in rows:
            row_fqns = set(row.get("target_fqns", []))
            matched_by = None
            if signature_fqn and row.get("signature_fqn") == signature_fqn:
                matched_by = "signature_fqn"
            elif signature and row.get("signature") == signature:
                matched_by = "signature"
            elif target_fqns and row_fqns and target_fqns & row_fqns:
                matched_by = "fqn"
            elif target_symbols and target_symbols & set(row.get("target_symbols", [])):
                # Trust a bare short-name match only when fqn disambiguation is NOT
                # available on both sides; otherwise two same-named symbols in
                # different namespaces would collide into a false contradiction.
                if not (target_fqns and row_fqns):
                    matched_by = "name"
            if matched_by:
                m = dict(row)
                m["_matched_by"] = matched_by
                matches.append(m)
        approvals = [r for r in matches if r["decision"] == "approve"]
        rejections = [r for r in matches if r["decision"] == "reject"]
        most_recent = matches[-1] if matches else None
        # A contradiction is a prior REJECTION of a matching change (same symbol or
        # same blast signature). It is the load-bearing "you are about to approve
        # something that was rejected before" beat. The strongest form is a
        # signature-identical rejection.
        # An identical-blast-signature rejection is the strong, BLOCK-forcing beat, so it must
        # win even when a MORE RECENT rejection of the same symbol carried a DIFFERENT signature
        # (a stale different-radius rejection must not mask the identical one and quietly downgrade
        # a BLOCK to a weak advisory). Prefer the most recent identical-signature rejection; fall
        # back to the most recent rejection of any matching kind.
        identical_rej = next((r for r in reversed(rejections)
                              if (signature and r.get("signature") == signature)
                              or (signature_fqn and r.get("signature_fqn") == signature_fqn)), None)
        contradiction = identical_rej or (rejections[-1] if rejections else None)
        contradiction_same_signature = identical_rej is not None
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
        by_match = {"signature_fqn": 0, "signature": 0, "fqn": 0, "name": 0}
        for m in matches:
            by_match[m.get("_matched_by", "name")] = by_match.get(m.get("_matched_by", "name"), 0) + 1
        return {
            "match_count": len(matches),
            "approved": len(approvals),
            "rejected": len(rejections),
            "matched_by": by_match,                              # signature/fqn/name counts
            "contradiction_matched_by": contradiction.get("_matched_by") if contradiction else None,
            "most_recent": most_recent,
            "contradiction": contradiction,
            "contradiction_same_signature": contradiction_same_signature,
            "contradiction_strength": contradiction_strength,
            "matched_rows": [{"seq": m["seq"], "row_hash": m["row_hash"], "matched_by": m.get("_matched_by"),
                              "decision": m["decision"], "actor": m["actor"],
                              "rationale": m["rationale"]} for m in matches],
        }


def _fixed_ts(seq: int) -> str:
    """Deterministic timestamp for reproducible fixtures and tests."""
    return f"2026-06-{10 + (seq % 14):02d}T10:{(seq * 7) % 60:02d}:00Z"
