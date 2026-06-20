"""Content-addressed precedent identity (priority F).

The id-based blast signature keys on DuckDB row ids, which are assigned at index time and
change on a re-index / different machine -- so an id-only precedent key silently misses after
the graph is rebuilt, which is a cheap evasion. `signature_fqn` keys on the change's real
semantic footprint (epicenter FQN + sorted affected FQNs), so the precedent survives a
re-index and ties the decision to *what the change touches*.

Honest limit (also documented in core/impact.blast_radius_signature_fqn): a change that
renames the epicenter AND restructures its entire dependent set can still alter the content
key; content-addressing reduces casual id-churn / rename evasion, it is not a cryptographic
identity of intent.
"""
from core.audit import Ledger
from core.impact import blast_radius_signature, blast_radius_signature_fqn


def test_signature_fqn_is_order_independent_and_distinguishes_changes():
    base = blast_radius_signature_fqn(["pkg.mod.b", "pkg.mod.c"], "pkg.mod.a")
    # set semantics: dependent order does not change the key
    assert base == blast_radius_signature_fqn(["pkg.mod.c", "pkg.mod.b"], "pkg.mod.a")
    # a different epicenter is a different change
    assert base != blast_radius_signature_fqn(["pkg.mod.b", "pkg.mod.c"], "pkg.mod.z")
    # a different dependent footprint is a different change
    assert base != blast_radius_signature_fqn(["pkg.mod.b"], "pkg.mod.a")


def test_signature_fqn_is_reindex_stable_where_id_signature_is_not():
    # Same FQN footprint, but a re-index assigned completely different row ids.
    fqn_before = blast_radius_signature_fqn(["pkg.b", "pkg.c"], "pkg.a")
    fqn_after = blast_radius_signature_fqn(["pkg.b", "pkg.c"], "pkg.a")
    assert fqn_before == fqn_after, "content key must be identical across a re-index"
    # the id-based key changes when the ids change (the evasion the FQN key closes)
    assert blast_radius_signature([2, 3], 1) != blast_radius_signature([20, 30], 10)


def test_precedent_matches_via_signature_fqn_after_reindex(tmp_path):
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    # A prior REJECT recorded before a re-index: old id-signature + the content key.
    led.append(actor="staff-eng", change_id="MR-PRIOR", target_symbols=["compute_blast_radius"],
               blast_radius_set=[2, 3, 4], signature="ID_SIG_OLD",
               signature_fqn="CONTENT_FOOTPRINT", decision="reject",
               rationale="too large to change without a migration")
    # After a re-index the id-based signature is different, but the FQN footprint is identical.
    prec = led.precedent(target_symbols=["compute_blast_radius"], signature="ID_SIG_NEW",
                         signature_fqn="CONTENT_FOOTPRINT")
    assert prec["contradiction"] is not None, "the prior reject must still be recalled after re-index"
    assert prec["contradiction_strength"] == "identical"
    assert prec["contradiction_matched_by"] == "signature_fqn"
    assert prec["matched_by"]["signature_fqn"] == 1


def test_unrelated_change_does_not_falsely_match(tmp_path):
    led = Ledger(str(tmp_path / "ledger.jsonl"))
    led.append(actor="staff-eng", change_id="MR-PRIOR", target_symbols=["foo"],
               blast_radius_set=[2, 3], signature="ID_A", signature_fqn="FOOTPRINT_A",
               decision="reject", rationale="no")
    prec = led.precedent(target_symbols=["bar"], signature="ID_B", signature_fqn="FOOTPRINT_B")
    assert prec["contradiction"] is None, "a different footprint must not produce a phantom contradiction"
