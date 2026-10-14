"""Incident feedback: scoring the engine's own recall (priority H).

`core/incident.py` closes the loop the rest of the engine leaves open. A gate can
report a blast radius all day; only an incident can tell you whether that number
was right.

The tests pin the behaviours that make the report trustworthy rather than
flattering:

  * a missing baseline is NO_BASELINE, never a clean bill of health
  * the missed set is computed as observed-minus-predicted, so an understated
    prediction can never be scored as "held"
  * a set that is entirely over-predicted is OVERSTATED, not HELD, so a gate that
    warns about everything cannot accumulate credit
  * `summarise` averages only over incidents that had a baseline, because folding
    in untagged ones would report a number that mostly measures tagging hygiene
  * `feedback` deduplicates missed symbols across incidents

Honest limit, also stated in the module docstring: this is set coverage, not
causality. A symbol appearing in the prediction does not prove the prediction
"caught" it.
"""
import json

from core.audit import Ledger
from core.incident import (HELD, NO_BASELINE, OVERSTATED, UNDERSTATED,
                           Incident, feedback, score, score_all, summarise)


def _ledger(tmp_path, rows):
    p = tmp_path / "ledger.jsonl"
    for r in rows:
        p.open("a", encoding="utf-8").write(json.dumps(r) + "\n")
    return Ledger(str(p))


APPROVED = {
    "change_id": "MR-101",
    "decision": "APPROVE",
    "target_symbols": ["parse", "tokenize", "lex"],
    "actor": "reviewer",
}


def test_prediction_held_when_the_recorded_set_covered_the_outcome(tmp_path):
    led = _ledger(tmp_path, [APPROVED])
    inc = Incident(id="INC-1", change_id="MR-101", observed=["parse", "tokenize"])
    r = score(led, inc)
    assert r.verdict == HELD
    assert r.hit == ["parse", "tokenize"]
    assert r.missed == []
    assert r.recall == 1.0


def test_a_missed_symbol_forces_understated_not_held(tmp_path):
    led = _ledger(tmp_path, [APPROVED])
    inc = Incident(id="INC-2", change_id="MR-101", observed=["parse", "exec_sql"])
    r = score(led, inc)
    # 'exec_sql' broke and nothing predicted it. That is the safety finding and it
    # must outrank the two symbols that were correctly covered.
    assert r.verdict == UNDERSTATED
    assert r.missed == ["exec_sql"]
    assert r.hit == ["parse"]
    assert r.recall == 0.5


def test_missing_baseline_is_never_reported_as_safe(tmp_path):
    led = _ledger(tmp_path, [])          # no decisions recorded at all
    r = score(led, Incident(id="INC-3", observed=["parse"]))
    assert r.verdict == NO_BASELINE
    # "we could not check" must not look like "we checked and were fine"
    assert r.verdict != HELD
    assert r.missed == ["parse"]


def test_a_fully_overpredicted_set_is_overstated_not_held(tmp_path):
    led = _ledger(tmp_path, [APPROVED])
    inc = Incident(id="INC-4", change_id="MR-101", observed=["something_else"])
    r = score(led, inc)
    # warned about three symbols, none of which broke, and the one that broke was
    # never predicted: that is an over-statement, not a success
    assert r.verdict == UNDERSTATED
    assert r.overpredicted == ["lex", "parse", "tokenize"]


def test_precision_and_recall_are_computed_from_the_sets_not_hardcoded(tmp_path):
    led = _ledger(tmp_path, [APPROVED])          # predicted 3
    r = score(led, Incident(id="INC-5", change_id="MR-101", observed=["parse"]))
    assert r.precision == 1 / 3                 # 1 of 3 predicted actually broke
    assert r.recall == 1.0                      # 1 of 1 observed was predicted
    assert 0 < r.f1 < 1


def test_find_baseline_falls_back_to_the_covering_approval(tmp_path):
    led = _ledger(tmp_path, [dict(APPROVED, change_id="MR-OLD")])
    inc = Incident(id="INC-6", observed=["parse"])   # no change_id supplied
    r = score(led, inc)
    assert r.change_id == "MR-OLD"
    assert r.verdict == HELD


def test_legacy_rows_still_yield_a_baseline(tmp_path):
    # The blast set has lived under several field names. A scorer that returned an
    # empty set for an older row would report NO_BASELINE and hide a real gap.
    led = _ledger(tmp_path, [{"change_id": "MR-OLD", "decision": "APPROVE",
                              "blast_radius_set": '["parse", "lex"]'}])
    r = score(led, Incident(id="INC-7", change_id="MR-OLD", observed=["lex"]))
    assert r.predicted == ["lex", "parse"]
    assert r.verdict == HELD


def test_score_all_orders_understated_first(tmp_path):
    led = _ledger(tmp_path, [APPROVED, dict(APPROVED, change_id="MR-OTHER")])
    incs = [
        Incident(id="A", change_id="MR-101", observed=["parse"]),        # held
        Incident(id="B", change_id="MR-101", observed=["parse", "zzz"]),  # understated
    ]
    out = score_all(led, incs)
    assert out[0].incident_id == "B"
    assert out[0].verdict == UNDERSTATED
    assert out[1].verdict == HELD


def test_summarise_excludes_no_baseline_from_the_mean(tmp_path):
    led = _ledger(tmp_path, [APPROVED])
    out = score_all(led, [
        Incident(id="A", change_id="MR-101", observed=["parse"]),   # recall 1.0
        Incident(id="B", observed=["nothing_recorded"]),            # NO_BASELINE
    ])
    s = summarise(out)
    assert s["incidents"] == 2
    assert s["scored"] == 1
    assert s["no_baseline"] == 1
    # averaging in the unscored one would report 0.5 for an engine that was
    # actually perfect on everything it could be scored against
    assert s["mean_recall"] == 1.0


def test_feedback_deduplicates_missed_symbols_across_incidents(tmp_path):
    led = _ledger(tmp_path, [APPROVED])
    out = score_all(led, [
        Incident(id="A", change_id="MR-101", observed=["parse", "ghost"]),
        Incident(id="B", change_id="MR-101", observed=["ghost"]),
    ])
    fb = feedback(out)
    symbols = [f["symbol"] for f in fb]
    assert symbols == sorted(set(symbols)), "no duplicate feedback rows"
    ghost = next(f for f in fb if f["symbol"] == "ghost")
    assert ghost["incidents"] == ["A", "B"]
    assert "precedent" in ghost["recommend"]


def test_reports_serialise_for_a_ci_artifact(tmp_path):
    led = _ledger(tmp_path, [APPROVED])
    r = score(led, Incident(id="INC-8", change_id="MR-101", observed=["parse", "nope"]))
    d = r.to_dict()
    json.dumps(d)                       # must not raise
    assert d["counts"]["missed"] == 1
    assert d["verdict"] == UNDERSTATED
    assert set(("precision", "recall", "f1")) <= set(d)
