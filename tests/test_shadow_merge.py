"""Tests for the Shadow Merge Firewall + Memory Gate skill commands.

These drive run_review.main() over the committed real Orbit self-index, so they prove the
deterministic cross-MR collision detection and the AI-approval override end to end.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "keystone"))
import run_review  # noqa: E402


def test_shadow_merge_risky_collides_and_gates(tmp_path):
    out = tmp_path / "shadow.md"
    rc = run_review.main(["shadow-merge", "--out", str(out)])
    assert rc == 2, "a real cross-MR collision must exit non-zero (CI gate)"
    md = out.read_text(encoding="utf-8")
    assert "Git result: NONE" in md, "the packet must state Git sees no conflict"
    assert "Orbit evidence" in md
    assert ("HOLD" in md or "BLOCK" in md)
    assert (tmp_path / "shadow.json").exists(), "machine-readable packet must be written"


def test_shadow_merge_safe_allows(tmp_path):
    out = tmp_path / "safe.md"
    rc = run_review.main(["shadow-merge", "--safe", "--out", str(out)])
    assert rc == 0, "a non-colliding cross-file pair must be ALLOW / exit 0"
    md = out.read_text(encoding="utf-8")
    assert "Verdict: ALLOW" in md


def test_memory_gate_overrides_agent_approval(tmp_path, monkeypatch):
    # fresh seeded ledger so the precedent contradiction is deterministic, not suite-order dependent
    monkeypatch.setenv("KEYSTONE_LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    out = tmp_path / "mg.md"
    rc = run_review.main(["memory-gate", "compute_blast_radius", "--out", str(out)])
    assert rc == 2, "agent APPROVE contradicting precedent must be overruled to BLOCK"
    md = out.read_text(encoding="utf-8")
    assert "OVERRIDES the agent" in md
    assert "REJECTED" in md


def test_memory_gate_allows_clean_symbol(tmp_path, monkeypatch):
    monkeypatch.setenv("KEYSTONE_LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    out = tmp_path / "mg2.md"
    rc = run_review.main(["memory-gate", "append", "--out", str(out)])
    assert rc == 0, "a symbol with no contradicting precedent must be ALLOW / exit 0"
