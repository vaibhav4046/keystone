"""Configuration drift: were the recorded decisions made under the rules now in force?

`core/config_drift.py` reads back the policy hash that Keystone pins into every
ledger row. The pin has always been written; until this module, nothing checked
it, which meant an edited policy left every prior approval looking valid under
rules that no longer existed.

The tests pin the distinctions that keep this honest:

  * a row with no pinned hash is UNKNOWN, never CURRENT
  * an all-UNKNOWN ledger reports UNKNOWN overall, not a clean CURRENT
  * a drifted APPROVE outranks a drifted REJECT in the re-review queue
  * drift on a rejection is reported too, at lower risk

Honest limit, also in the module docstring: DRIFT means "re-review this", not
"this decision was wrong". The ledger stores the decision, not the policy
evaluation that produced it, so whether a drifted row would now decide
differently is not computable here.
"""
import json

from core.audit import Ledger
from core.config_drift import (CURRENT, DRIFT, UNKNOWN, audit, re_review_queue)
from core.policy import policy_hash


def _ledger(tmp_path, rows):
    p = tmp_path / "l.jsonl"
    for r in rows:
        p.open("a", encoding="utf-8").write(json.dumps(r) + "\n")
    return Ledger(str(p))


def test_a_row_recorded_under_the_current_policy_is_current(tmp_path):
    h = policy_hash()
    led = _ledger(tmp_path, [{"seq": 0, "change_id": "MR-1", "decision": "approve",
                              "policy_hash": h}])
    rep = audit(led)
    assert rep.verdict == CURRENT
    assert rep.drifted == []
    assert rep.rows[0].recorded_policy_hash == h


def test_a_row_with_no_pinned_hash_is_unknown_not_current(tmp_path):
    led = _ledger(tmp_path, [{"seq": 0, "change_id": "MR-1", "decision": "approve"}])
    rep = audit(led)
    # reporting this as CURRENT would produce a confident report that is really
    # just measuring which rows happen to carry a pin
    assert rep.rows[0].verdict == UNKNOWN
    assert rep.verdict == UNKNOWN
    assert rep.verdict != CURRENT


def test_editing_the_policy_drifts_the_older_rows(tmp_path):
    old = policy_hash({"tiers": {"LOCAL": 1}})
    led = _ledger(tmp_path, [
        {"seq": 0, "change_id": "MR-1", "decision": "approve", "policy_hash": old},
    ])
    rep = audit(led, policy={"tiers": {"LOCAL": 2}})   # the file was edited
    assert rep.verdict == DRIFT
    assert len(rep.drifted) == 1
    assert rep.drifted[0].recorded_policy_hash == old
    assert rep.drifted[0].current_policy_hash != old


def test_a_ledger_mixing_known_and_unknown_is_not_overstated(tmp_path):
    h = policy_hash()
    led = _ledger(tmp_path, [
        {"seq": 0, "change_id": "MR-1", "decision": "approve", "policy_hash": h},
        {"seq": 1, "change_id": "MR-2", "decision": "reject"},          # no pin
    ])
    rep = audit(led)
    assert rep.verdict == CURRENT          # nothing drifted
    assert len(rep.unknown) == 1           # but one row is still unchecked
    assert rep.to_dict()["counts"] == {"rows": 2, "current": 1, "drift": 0, "unknown": 1}


def test_drifted_approvals_are_queued_ahead_of_drifted_rejections(tmp_path):
    old = policy_hash({"v": 1})
    led = _ledger(tmp_path, [
        {"seq": 0, "change_id": "MR-REJ", "decision": "reject", "policy_hash": old},
        {"seq": 1, "change_id": "MR-APP", "decision": "approve", "policy_hash": old},
    ])
    rep = audit(led, policy={"v": 2})
    q = re_review_queue(rep)
    # an approval earned under a stricter policy is the dangerous one: a later
    # change to the same symbols will find that precedent and pass
    assert [e["change_id"] for e in q] == ["MR-APP", "MR-REJ"]
    assert q[0]["risk"] == "high"
    assert q[1]["risk"] == "low"
    assert all("re-review" in e["action"] for e in q)


def test_drift_is_reported_as_a_fact_not_an_accusation(tmp_path):
    old = policy_hash({"v": 1})
    led = _ledger(tmp_path, [{"seq": 0, "change_id": "MR-1",
                              "decision": "approve", "policy_hash": old}])
    rep = audit(led, policy={"v": 2})
    d = rep.to_dict()
    # the module must never claim a drifted decision was wrong
    assert d["verdict"] == DRIFT
    assert "wrong" not in json.dumps(d).lower()


def test_report_serialises_for_a_ci_artifact(tmp_path):
    h = policy_hash()
    led = _ledger(tmp_path, [{"seq": 0, "change_id": "MR-1",
                              "decision": "approve", "policy_hash": h}])
    d = audit(led).to_dict()
    json.dumps(d)
    assert set(d) == {"verdict", "current_policy_hash", "counts", "rows"}
