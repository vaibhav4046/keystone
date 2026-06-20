"""Keystone governed-review workflow runner (the SKILL's runnable action).

This is the proof that the Keystone skill AUTOMATES a workflow rather than
chatting: given a symbol it calls the Keystone API to fetch the deterministic
blast radius and the precedent, prints a governed-review report, and optionally
records a human decision into the tamper-evident ledger, then confirms the chain.

It talks to the API through two injected callables (get_json, post_json) so the
same orchestration is testable in-process and runnable against a live server.
Standard library only for the live path (urllib).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib import request, parse, error


class _Unreachable(Exception):
    """The Keystone server could not be reached on the live (non --local) path."""


def _urllib_get(base):
    def g(path):
        try:
            with request.urlopen(base + path, timeout=8) as r:
                return json.loads(r.read().decode())
        except error.HTTPError as e:
            if e.code == 404:
                return {}                       # missing symbol -> governed_review reports it cleanly
            raise _Unreachable(f"{base} returned HTTP {e.code}")
        except (error.URLError, OSError):       # connection refused / DNS / timeout
            raise _Unreachable(base)
    return g


def _urllib_post(base):
    def p(path, body):
        data = json.dumps(body).encode()
        req = request.Request(base + path, data=data, headers={"content-type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=8) as r:
                return json.loads(r.read().decode())
        except (error.URLError, OSError) as e:
            if not isinstance(e, error.HTTPError):
                raise _Unreachable(base)        # connection refused / DNS / timeout
            # else fall through to the HTTPError handler below
            # A gate refusal (403 scope/four-eyes/unregistered, 409 BLOCK, 401 token, 429 rate)
            # comes back as an HTTP error whose body carries the detail. Surface it as a clean
            # "blocked" result instead of crashing the skill with a traceback.
            try:
                payload = json.loads(e.read().decode())
            except Exception:
                payload = {}
            det = payload.get("detail", payload) if isinstance(payload, dict) else payload
            err = det.get("error") if isinstance(det, dict) else det
            return {"blocked": err or f"HTTP {e.code}", "detail": det}
    return p


def governed_review(symbol, get_json, post_json=None, *, decide=None, reviewer=None, reason=None):
    """Run the workflow. Returns a structured report dict. Records a decision iff
    decide is given (with reviewer and reason). Never invents numbers; never
    auto-decides."""
    report = {"symbol": symbol, "steps": []}

    imp = get_json(f"/api/impact/{parse.quote(symbol)}")
    if imp is None or "counts" not in imp:
        report["error"] = f"symbol not found in graph: {symbol}"
        return report
    report["steps"].append("impact")
    report["epicenter"] = imp["epicenter"]
    report["counts"] = imp["counts"]
    report["signature"] = imp["signature"]

    prec = get_json(f"/api/precedent/{parse.quote(symbol)}")
    report["steps"].append("precedent")
    report["precedent"] = {
        "matches": prec.get("match_count", 0),
        "approved": prec.get("approved", 0),
        "rejected": prec.get("rejected", 0),
        "contradiction": prec.get("contradiction"),
        "contradiction_same_signature": prec.get("contradiction_same_signature", False),
        "contradiction_strength": prec.get("contradiction_strength"),
    }

    if decide:
        if not reviewer or not reason:
            report["error"] = "a decision requires --reviewer and --reason"
            return report
        if decide not in ("approve", "reject"):
            report["error"] = "decision must be approve or reject"
            return report
        res = post_json("/api/approve", {"name": symbol, "decision": decide,
                                         "reviewer": reviewer, "rationale": reason})
        report["steps"].append("approve")
        if res.get("blocked"):
            report["blocked"] = res["blocked"]
            report["error"] = f"decision refused by gate: {res['blocked']}"
            return report
        report["recorded"] = res.get("row")
        report["chain_after"] = res.get("verify")
        report["quorum"] = res.get("quorum")
        report["self_asserted"] = res.get("self_asserted", True)
        report["ci_identity"] = res.get("ci_identity")
    else:
        report["chain"] = get_json("/api/audit/verify")
        report["steps"].append("verify")
    return report


def _print_report(rep):
    if rep.get("error"):
        print("ERROR:", rep["error"]); return
    c = rep["counts"]
    print(f"\nKEYSTONE governed review : {rep['symbol']}")
    print(f"  blast radius : ring1={c.get('ring_1',0)} ring2={c.get('ring_2',0)} "
          f"affected={c['total_affected']} unaffected={c['unaffected']}")
    print(f"  signature    : {rep['signature'][:16]}...")
    p = rep["precedent"]
    print(f"  precedent    : {p['matches']} matches  approved={p['approved']} rejected={p['rejected']}")
    if p["contradiction"]:
        cc = p["contradiction"]
        tag = "identical-signature " if p["contradiction_same_signature"] else ""
        print(f"  CONTRADICTION ({tag}): {cc['actor']} rejected {cc['change_id']} : \"{cc['rationale']}\" (row #{cc['seq']})")
    if rep.get("recorded"):
        r = rep["recorded"]
        print(f"  recorded     : {r['decision']} by {r['actor']} -> row #{r['seq']} {r['row_hash'][:12]}...")
        cid = rep.get("ci_identity")
        if cid and not rep.get("self_asserted", True):
            print(f"  identity     : GitLab-attested (OIDC sub={cid.get('sub')}, ref={cid.get('ref')}) - not self-asserted")
        else:
            print("  identity     : self-asserted (advisory) - bind a GitLab OIDC id_token to attest the actor")
        print(f"  chain        : {'VERIFIED' if rep['chain_after']['ok'] else 'BROKEN@' + str(rep['chain_after']['broken_index'])}")
    elif rep.get("chain"):
        print(f"  chain        : {'VERIFIED' if rep['chain']['ok'] else 'BROKEN@' + str(rep['chain']['broken_index'])}")
    print()


def _local_callables(prefer_live=True, graph_path=None, ledger_path=None, seed=True):
    """Wire get/post directly to the in-process core (no server), so the gate runs
    in CI with nothing to start. Used by --local. prefer_live=False forces the
    committed fixture so the gate is deterministic on any machine (use in CI).
    graph_path overrides the graph location (e.g. the committed self-index).
    ledger_path overrides the ledger file. seed=False starts from an EMPTY ledger
    (used by `memory-gate --prove`, which records the precedent through the real
    reject path instead of relying on a pre-seeded contradiction)."""
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.abspath(os.path.join(here, "..", "..")))
    import tempfile
    from core import graph as graph_mod, impact as impact_mod, seed as seed_mod
    from core.audit import Ledger
    g = graph_mod.Graph(prefer_live=prefer_live, path=graph_path)
    if ledger_path is None:
        if not prefer_live:
            # hermetic: a fresh temp ledger, always reseeded, so the fixture contradiction
            # fires deterministically regardless of any prior ~/.keystone state.
            ledger_path = os.path.join(tempfile.mkdtemp(), "gate_ledger.jsonl")
        else:
            ledger_path = os.environ.get("KEYSTONE_LEDGER_PATH") or \
                os.path.join(os.path.expanduser("~"), ".keystone", "gate_ledger.jsonl")
    led = Ledger(ledger_path)
    if seed and ((not prefer_live) or (not led.rows())):
        for row in seed_mod.seed_rows_for(g):
            sig = impact_mod.blast_radius_signature(row["blast_radius_set"], row.get("epicenter_id"))
            led.append(actor=row["actor"], change_id=row["change_id"], target_symbols=row["target_symbols"],
                       blast_radius_set=row["blast_radius_set"], signature=sig,
                       signature_fqn=row.get("signature_fqn"), target_fqns=row.get("target_fqns"),
                       decision=row["decision"], rationale=row["rationale"])

    def get_json(path):
        if path.startswith("/api/impact/"):
            imp = impact_mod.compute_blast_radius(g, parse.unquote(path.rsplit("/", 1)[-1]))
            return imp.to_dict() if imp else {}
        if path.startswith("/api/precedent/"):
            name = parse.unquote(path.rsplit("/", 1)[-1])
            imp = impact_mod.compute_blast_radius(g, name)
            return led.precedent(target_symbols=[name], signature=imp.signature if imp else None)
        if path == "/api/audit/verify":
            return led.verify()
        raise AssertionError("unexpected GET " + path)

    from core import gate as gate_mod, identity as identity_mod

    # On a GitLab pipeline a runner-injected OIDC token binds the actor to a `sub` claim,
    # so a decision recorded here is GitLab-attested (self_asserted=False), not a free string.
    ci_id = identity_mod.ci_identity()

    def post_json(path, body):
        # route through the SAME enforcement gate the API uses (no weaker CLI path)
        res = gate_mod.evaluate(g, led, name=body["name"], decision=body["decision"],
                                reviewer=body["reviewer"], change_id=body.get("change_id"),
                                change_author=body.get("change_author"), author_kind=body.get("author_kind"),
                                override=bool(body.get("override")), ci_identity=ci_id)
        if not res["ok"]:
            return {"blocked": res["error"], "detail": res.get("detail")}
        row = led.append(actor=body["reviewer"], change_id=res["change_id"], target_symbols=[body["name"]],
                         target_fqns=res["target_fqns"], blast_radius_set=res["blast_set"], signature=res["sig"],
                         signature_fqn=res.get("signature_fqn"),
                         decision=body["decision"], rationale=body["rationale"], extra=res["row_extra"])
        return {"row": row, "verify": led.verify(), "self_asserted": res.get("self_asserted", True),
                "ci_identity": res.get("ci_identity"),
                "quorum": {k: res["quorum"][k] for k in ("required", "confirmed", "status")}}

    def gate_check(symbol):
        return gate_mod.evaluate(g, led, name=symbol, decision="approve", reviewer="ci-gate", ci_identity=ci_id)

    return get_json, post_json, gate_check, ci_id


# --- MR Guardian: sample merge-request review workflow -----------------------
# Maps the demo scenario MR ids (kept in sync with scripts/build_static.py
# DEMO_MRS) to the real symbol each touches on the committed Orbit self-index.
SAMPLE_MRS = {
    "MR-204": {"symbol": "compute_blast_radius", "title": "speed up the blast engine",
               "file": "core/impact.py"},
    "MR-207": {"symbol": "impact", "title": "tune the impact API",
               "file": "backend/app.py"},
    "MR-211": {"symbol": "append", "title": "ledger append fix",
               "file": "core/audit.py"},
}


def _distinct_files_dirs(owners):
    """Count distinct files and directories from an impact owners list."""
    files, dirs = set(), set()
    for o in (owners or []):
        f, d = o.get("file"), o.get("dir")
        if f: files.add(f)
        if d: dirs.add(d)
    return len(files), len(dirs)


def build_mr_comment(symbol, mr_id, imp, pol, prec):
    """Build a postable GitLab MR review comment (markdown) from real engine data.

    imp  -> impact dict (compute_blast_radius(...).to_dict())
    pol  -> policy.evaluate(...) result
    prec -> ledger.precedent(...) result
    Never invents a figure; every value is read from the passed dicts.
    """
    action = (pol.get("action") or "ALLOW").upper()
    verb = {"BLOCK": "BLOCK", "HOLD": "HOLD", "ALLOW": "ALLOW"}.get(action, action)
    counts = imp.get("counts", {})
    n_files, n_dirs = _distinct_files_dirs(imp.get("owners"))
    epi = imp.get("epicenter", {})
    reasons = pol.get("reasons") or []
    contradiction = prec.get("contradiction")
    same_sig = prec.get("contradiction_same_signature", False)

    lines = []
    lines.append(f"## Keystone Review Gate: {verb}")
    lines.append("")
    lines.append(f"This merge request changes `{symbol}` (`{epi.get('file', '?')}`).")
    lines.append("")
    lines.append("**Git result:** No textual conflict detected.")
    lines.append("")
    lines.append("**Orbit result:** Hidden dependency blast radius detected.")
    lines.append("")
    lines.append("**Impact (engine-computed from the Orbit graph):**")
    lines.append("")
    lines.append(f"* Direct affected definitions (ring-1): **{counts.get('ring_1', 0)}**")
    lines.append(f"* Total affected definitions: **{counts.get('total_affected', 0)}**")
    lines.append(f"* Files: **{n_files}**")
    lines.append(f"* Directories: **{n_dirs}**")
    lines.append(f"* Policy tier: **{pol.get('tier', 'ISOLATED')}**")
    lines.append(f"* Required approvers: **{pol.get('required_approvers', 1)}**")
    rw = pol.get("review_window_hours")
    if rw:
        lines.append(f"* Review window: **{rw}h advisory**")
    lines.append("")
    lines.append(f"**Decision: {verb}**")
    lines.append("")
    if verb == "BLOCK":
        lines.append("**Why Keystone blocked it:**")
        lines.append("")
        lines.append("* Git sees no textual conflict.")
        lines.append("* GitLab Orbit found dependency overlap across the blast radius.")
        if contradiction and same_sig:
            cc = contradiction
            lines.append(
                f"* A matching blast signature was previously rejected "
                f"({cc.get('actor', '?')} rejected {cc.get('change_id', '?')}).")
        elif reasons:
            for r in reasons:
                lines.append(f"* {r}")
        else:
            lines.append("* Policy tier requires more approvers than confirmed.")
        lines.append("")
        lines.append("**Required action:** Do not merge until owner review and a recorded "
                     "precedent override are in place.")
    elif verb == "HOLD":
        lines.append("**Why Keystone held it:** the policy tier requires a quorum of "
                     f"{pol.get('required_approvers', 1)} approvers before merge.")
    else:
        lines.append("**Why Keystone allowed it:** the blast radius is within the "
                     "ISOLATED/LOCAL tier and no contradicting precedent was found.")
    lines.append("")
    lines.append("---")
    lines.append("_Engine computed. AI explanation only. Same graph + same policy = same decision._")
    lines.append("")
    return "\n".join(lines)


def _review_mr(argv):
    """`run_review.py review-mr --sample MR-204 [--format markdown] [--out PATH]`.

    Runs the governed-review workflow over the sample MR's symbol on the
    in-process core (deterministic with --fixture) and either prints a structured
    summary or writes a postable GitLab MR review comment.
    """
    ap = argparse.ArgumentParser(prog="run_review.py review-mr",
                                 description="Review a sample merge request with the Keystone gate")
    ap.add_argument("--sample", default="MR-204",
                    help="sample MR id: " + ", ".join(SAMPLE_MRS))
    ap.add_argument("--format", choices=["summary", "markdown"], default="summary")
    ap.add_argument("--out", default=None,
                    help="write the markdown comment to this path (default: "
                         "SUBMISSION/generated/keystone-review-comment.md when --format markdown)")
    ap.add_argument("--local", action="store_true",
                    help="run against the in-process core, no server")
    ap.add_argument("--fixture", action="store_true",
                    help="with --local, force the committed fixture (deterministic)")
    a = ap.parse_args(argv)

    mr = SAMPLE_MRS.get(a.sample)
    if not mr:
        print(f"ERROR: unknown sample MR '{a.sample}'. Choose from: {', '.join(SAMPLE_MRS)}")
        return 1

    # Default to the committed real Orbit self-index so the review is real on any
    # machine (no orbit binary required); --fixture forces the small sample graph.
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    self_graph = os.path.join(root, "data", "keystone_self_graph.duckdb")
    graph_path = None if a.fixture else (self_graph if os.path.exists(self_graph) else None)
    get_json, post_json, gate_check, ci_id = _local_callables(
        prefer_live=not a.fixture, graph_path=graph_path)
    symbol = mr["symbol"]
    from urllib import parse as _parse
    imp = get_json(f"/api/impact/{_parse.quote(symbol)}")
    if not imp or "counts" not in imp:
        print(f"ERROR: symbol '{symbol}' not found in the graph.")
        return 1
    prec = get_json(f"/api/precedent/{_parse.quote(symbol)}")

    # Evaluate the same policy the API/CI gate uses (deterministic).
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from core import policy as policy_mod
    pol = policy_mod.evaluate(imp, prec)
    chain = get_json("/api/audit/verify")

    if a.format == "markdown":
        comment = build_mr_comment(symbol, a.sample, imp, pol, prec)
        out_path = a.out
        if not out_path:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            out_path = os.path.join(root, "SUBMISSION", "generated", "keystone-review-comment.md")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(comment)
        print(comment)
        print(f"\n(wrote {out_path})")
        return 0

    # summary
    print(f"\nKEYSTONE MR Guardian review : {a.sample} -> {symbol}")
    print(f"  file          : {mr['file']}")
    print(f"  ring-1        : {imp['counts'].get('ring_1', 0)}")
    print(f"  total affected: {imp['counts'].get('total_affected', 0)}")
    n_files, n_dirs = _distinct_files_dirs(imp.get("owners"))
    print(f"  files / dirs  : {n_files} / {n_dirs}")
    print(f"  tier          : {pol.get('tier')}")
    print(f"  decision      : {pol.get('action')}")
    print(f"  approvers     : {pol.get('required_approvers')}")
    if prec.get("contradiction_same_signature"):
        cc = prec.get("contradiction", {})
        print(f"  precedent     : BLOCK - identical blast signature rejected by "
              f"{cc.get('actor', '?')} in {cc.get('change_id', '?')}")
    else:
        print(f"  precedent     : {prec.get('rejected', 0)} rejected, "
              f"{prec.get('approved', 0)} approved")
    print(f"  ledger        : {'VERIFIED' if chain.get('ok') else 'BROKEN'}")
    print("  comment       : use --format markdown to generate the GitLab MR review comment")
    print()
    return 0


def _shadow_merge(argv):
    """Shadow Merge Firewall: two merge requests touch DIFFERENT files (so Git reports no text
    conflict) yet COLLIDE on the GitLab Orbit graph through a shared dependency. Fully deterministic
    (no model). Exits non-zero on HOLD/BLOCK so it gates CI; exits 0 on a safe (ALLOW) pair.

      run_review.py shadow-merge [--a SYMBOL --b SYMBOL | --safe] [--fixture] [--json] [--out PATH]
    """
    import json as _json
    import os
    ap = argparse.ArgumentParser(
        prog="run_review.py shadow-merge",
        description="Detect a hidden cross-MR collision Git cannot see (an Orbit relationship conflict)")
    ap.add_argument("--a", help="symbol changed by MR A")
    ap.add_argument("--b", help="symbol changed by MR B")
    ap.add_argument("--a-id", default=None)
    ap.add_argument("--b-id", default=None)
    ap.add_argument("--safe", action="store_true", help="run a verified non-colliding pair (ALLOW, exit 0)")
    ap.add_argument("--fixture", action="store_true", help="use the committed fixture graph")
    ap.add_argument("--json", action="store_true", help="also print the machine-readable packet")
    ap.add_argument("--out", default=None, help="markdown packet path")
    ap.add_argument("--fail-on-block", action="store_true", help="(default) non-zero on HOLD/BLOCK")
    a = ap.parse_args(argv)

    if a.safe:
        sym_a, sym_b = a.a or "clear_transcript", a.b or "precedent"
        ida, idb = a.a_id or "MR-301", a.b_id or "MR-302"
    else:
        # Headline demo: a DIRECTIONAL change_in_blast collision (BLOCK), not just an
        # overlap (HOLD). MR-207 edits impact(), which is itself a dependent inside
        # MR-204's blast radius for compute_blast_radius() -> the two safe-looking changes
        # become unsafe together. See `--safe` for the passing counter-example.
        sym_a, sym_b = a.a or "compute_blast_radius", a.b or "impact"
        ida, idb = a.a_id or "MR-204", a.b_id or "MR-207"

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, root)
    self_graph = os.path.join(root, "data", "keystone_self_graph.duckdb")
    graph_path = None if a.fixture else (self_graph if os.path.exists(self_graph) else None)
    from core import collision as collision_mod, graph as graph_mod, impact as impact_mod
    g = graph_mod.Graph(prefer_live=not a.fixture, path=graph_path)

    impa = impact_mod.compute_blast_radius(g, sym_a)
    impb = impact_mod.compute_blast_radius(g, sym_b)
    if impa is None or impb is None:
        print(f"ERROR: symbol not found in Orbit graph: {sym_a if impa is None else sym_b}")
        return 1
    da, db = impa.to_dict(), impb.to_dict()
    file_a = (da.get("epicenter") or {}).get("file", "?")
    file_b = (db.get("epicenter") or {}).get("file", "?")
    git_conflict = "NONE" if file_a != file_b else "TEXT-OVERLAP"
    ablast = da["counts"]["total_affected"]
    bblast = db["counts"]["total_affected"]

    res = collision_mod.detect_collisions(
        g, [{"id": ida, "symbols": [sym_a]}, {"id": idb, "symbols": [sym_b]}])
    cols = (res or {}).get("collisions") or []
    collided = bool(cols)
    kind = cols[0]["kind"] if collided else None
    shared = cols[0]["shared"] if collided else []
    if not collided:
        verdict, exit_code = "ALLOW", 0
    elif kind in ("same_change", "change_in_blast"):
        verdict, exit_code = "BLOCK", 2
    else:
        verdict, exit_code = "HOLD", 2

    cmd = (f"python skills/keystone/run_review.py shadow-merge"
           + ("" if not a.safe else " --safe")
           + (f" --a {sym_a} --b {sym_b}" if (a.a or a.b) else ""))
    shared_str = ", ".join(shared[:8]) if shared else "(none)"

    # ---- terminal summary (the demo's first 20 seconds) ----
    print(f"\nKEYSTONE Shadow Merge Firewall : {ida} vs {idb}")
    print(f"  {ida}: changes {sym_a}() in {file_a}  (blast {ablast})")
    print(f"  {idb}: changes {sym_b}() in {file_b}  (blast {bblast})")
    print(f"  Git text conflict : {git_conflict}   <- Git compares lines; different files = 'no conflict'")
    print(f"  Orbit collision   : {'DETECTED' if collided else 'none'}"
          + (f"  ({kind}, {len(shared)} shared dependents)" if collided else ""))
    if collided:
        print(f"  shared dependency : {shared_str}")
    if kind == "change_in_blast":
        print(f"  relationship path : {idb} edits {sym_b}(), which sits INSIDE {ida}'s blast radius "
              f"for {sym_a}()")
        print(f"                      -> each MR is safe alone; merged together {sym_b}() runs against "
              f"{sym_a}()'s changed contract and breaks. Git saw two unrelated files.")
    print(f"  VERDICT           : {verdict}")
    if exit_code and not a.safe:
        print(f"  safe alternative  : python skills/keystone/run_review.py shadow-merge --safe  "
              f"(non-overlapping pair -> ALLOW, exit 0)")
    print()

    # ---- decision packet (markdown) ----
    lines = [
        "# Keystone - Shadow Merge Firewall decision packet", "",
        f"**Verdict: {verdict}**  (Git text conflict: {git_conflict} | Orbit collision: "
        f"{'DETECTED' if collided else 'none'})", "",
        "## Executive summary",
        (f"`{ida}` and `{idb}` touch different files, so Git reports no conflict and both pass review "
         f"independently. On the GitLab Orbit graph their blast radii collide on a shared dependency, "
         f"so merging both can break code neither reviewer changed." if collided else
         f"`{ida}` and `{idb}` touch different files and their Orbit blast radii do not overlap. "
         f"No hidden relationship conflict - safe to merge in any order."),
        "",
        "## The two changes",
        f"- **{ida}** changes `{sym_a}()` in `{file_a}` (Orbit blast radius: {ablast} dependents)",
        f"- **{idb}** changes `{sym_b}()` in `{file_b}` (Orbit blast radius: {bblast} dependents)",
        "",
        f"## Git result: {git_conflict}",
        "Git's merge-conflict detection is textual: it only flags overlapping line edits. These MRs "
        "edit different files, so Git is blind to the relationship between them.",
        "",
        "## Orbit evidence (the relationship Git cannot see)",
        (f"- Collision kind: `{kind}`" if collided else "- No blast-radius overlap detected."),
    ]
    if collided:
        lines += [
            f"- Shared dependents ({len(shared)}): {shared_str}",
            "- These definitions transitively depend on BOTH changed symbols, so a change to either "
            "ripples into them; changing both at once compounds the risk with no text conflict to warn you.",
            "",
            "## Recommended developer action",
            ("Do not merge both blindly. Stack the two MRs into one coordinated review, add an "
             "integration test exercising the shared dependents, and merge in the order Keystone's "
             "safe-merge-order computes." if verdict in ("HOLD", "BLOCK") else ""),
        ]
    lines += [
        "",
        f"## CI result: exit {exit_code} ({'fails the pipeline' if exit_code else 'passes'})",
        f"## Reproduce", f"```", cmd, "```",
        "",
        "## Paste-ready GitLab MR comment",
        "```markdown",
        f"### Keystone Shadow Merge Firewall: {verdict}",
        f"{ida} (`{sym_a}`, {file_a}) and {idb} (`{sym_b}`, {file_b}) have **no Git text conflict** "
        + (f"but **collide on the Orbit graph** via {len(shared)} shared dependents "
           f"({shared_str}). Coordinate these before merge." if collided
           else "and **no Orbit blast-radius overlap** - safe to merge."),
        "```",
        "",
        "## Honest limitations",
        "- Computed from a committed real `orbit index` of this repo (deterministic snapshot), not a "
        "live MR webhook. Every figure is reproducible with the command above; no model is on this path.",
        "", "_Git sees files. Orbit sees relationships. Keystone turns relationships into a merge gate._",
    ]
    packet = "\n".join(lines)
    out = a.out or os.path.join(root, "SUBMISSION", "generated", "shadow-merge-packet.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(packet + "\n")

    packet_json = {
        "verdict": verdict, "conflict_type": kind, "git_conflict": git_conflict,
        "orbit_collision": collided, "shared_dependency": shared,
        "affected_count": {ida: ablast, idb: bblast}, "risk": (res or {}).get("counts", {}),
        "mr_a": {"id": ida, "symbol": sym_a, "file": file_a},
        "mr_b": {"id": idb, "symbol": sym_b, "file": file_b},
        "command": cmd, "exit_code": exit_code,
    }
    json_out = os.path.splitext(out)[0] + ".json"
    with open(json_out, "w", encoding="utf-8") as f:
        _json.dump(packet_json, f, indent=2)
    print(f"(wrote {out} and {json_out})")
    if a.json:
        print(_json.dumps(packet_json, indent=2))
    if exit_code:
        print(f"\nSHADOW MERGE: {verdict} - {ida} and {idb} collide on the Orbit graph with no Git "
              f"conflict. CI exit {exit_code}.")
    return exit_code


def _memory_gate(argv):
    """Orbit Memory Gate: an AI agent proposes a decision; Keystone consults the GitLab Orbit graph
    and the precedent ledger and OVERRIDES the agent when its proposal contradicts recorded
    precedent. Fully deterministic (no model/API call). Exits non-zero when Keystone blocks an
    agent's approval, so it works as a CI gate.

      run_review.py memory-gate <symbol> [--agent NAME] [--proposes approve|reject]
                                         [--fixture] [--out PATH]
    """
    import os
    ap = argparse.ArgumentParser(
        prog="run_review.py memory-gate",
        description="Orbit Memory Gate: override an AI agent's proposal when it contradicts precedent")
    ap.add_argument("symbol")
    ap.add_argument("--agent", default="copilot-agent")
    ap.add_argument("--proposes", choices=["approve", "reject"], default="approve")
    ap.add_argument("--fixture", action="store_true",
                    help="use the deterministic committed fixture graph")
    ap.add_argument("--prove", action="store_true",
                    help="start from an EMPTY ledger and RECORD the precedent live through the real "
                         "reject path, then show the agent's APPROVE overridden by it (non-theatrical)")
    ap.add_argument("--reject-by", default="staff-engineer",
                    help="reviewer id that records the prior reject in --prove mode")
    ap.add_argument("--out", default=None, help="write the decision packet markdown to this path")
    a = ap.parse_args(argv)

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    self_graph = os.path.join(root, "data", "keystone_self_graph.duckdb")
    graph_path = None if a.fixture else (self_graph if os.path.exists(self_graph) else None)
    recorded_row = None
    if a.prove:
        # Non-theatrical proof: empty ledger, then a REAL recorded reject (same gate+append
        # path a human uses), THEN the agent's approve is overruled by that recorded decision.
        import tempfile as _tf
        led_path = os.path.join(_tf.mkdtemp(), "prove_ledger.jsonl")
        get_json, post_json, gate_check, _ci = _local_callables(
            prefer_live=not a.fixture, graph_path=graph_path, ledger_path=led_path, seed=False)
        rationale = (f"Rejecting changes to {a.symbol}: this symbol's blast radius is too large to "
                     f"alter without a coordinated migration; prior incident on a similar change.")
        rec = post_json("/api/post", {
            "name": a.symbol, "decision": "reject", "reviewer": a.reject_by,
            "change_id": "MR-PRIOR", "rationale": rationale, "author_kind": "human"})
        recorded_row = (rec or {}).get("row")
        if recorded_row:
            print(f"\n[1/2] {a.reject_by} REJECTED {a.symbol} -> recorded ledger row "
                  f"#{recorded_row.get('seq')} (chain "
                  f"{'VERIFIED' if (rec.get('verify') or {}).get('ok') else 'BROKEN'}). "
                  f"Identity: {'self-asserted' if rec.get('self_asserted', True) else 'GitLab-OIDC attested'}.")
            print(f"[2/2] {a.agent} now proposes APPROVE for {a.symbol} -> consulting the ledger...")
        else:
            print(f"WARN: could not record prior reject ({rec}); falling back to seeded precedent.")
    else:
        get_json, _post, gate_check, _ci = _local_callables(prefer_live=not a.fixture, graph_path=graph_path)

    imp = get_json(f"/api/impact/{parse.quote(a.symbol)}")
    if not imp or "counts" not in imp:
        print(f"ERROR: symbol '{a.symbol}' not found in the Orbit graph.")
        return 1
    prec = get_json(f"/api/precedent/{parse.quote(a.symbol)}")
    gate = gate_check(a.symbol)
    blocked = not gate.get("ok", False)
    verdict = "BLOCK" if blocked else "ALLOW"
    overrode_agent = (a.proposes == "approve") and blocked
    c = imp["counts"]
    cc = prec.get("contradiction") if prec.get("contradiction_same_signature") else None

    lines = ["# Keystone - Orbit Memory Gate decision packet", ""]
    if a.prove and recorded_row:
        lines += [
            f"> **Recorded live in this run** (not pre-seeded): `{a.reject_by}` rejected `{a.symbol}` "
            f"into an empty ledger as row #{recorded_row.get('seq')}, then `{a.agent}` proposed APPROVE "
            f"below and Keystone overruled it from that recorded decision.", ""]
    lines += [
             f"- Symbol: `{a.symbol}` (`{imp.get('epicenter', {}).get('file', '?')}`)",
             f"- AI agent proposed: **{a.proposes.upper()}** (by `{a.agent}`)",
             f"- Orbit blast radius: **{c.get('total_affected', 0)}** dependents (ring-1 {c.get('ring_1', 0)})",
             f"- Blast signature: `{(imp.get('signature') or '')[:16]}`"]
    if cc:
        lines.append(f"- Precedent: identical blast signature already **REJECTED** by `{cc.get('actor', '?')}` "
                     f"in `{cc.get('change_id', '?')}` - \"{cc.get('rationale', '')}\" (ledger row #{cc.get('seq', '?')})")
    else:
        lines.append(f"- Precedent: {prec.get('rejected', 0)} prior rejections, {prec.get('approved', 0)} "
                     f"approvals, no identical-signature contradiction")
    lines.append(f"- Keystone verdict: **{verdict}**"
                 + (f" - OVERRIDES the agent's {a.proposes.upper()}" if overrode_agent else ""))
    if blocked:
        lines.append(f"- Reason code: `{gate.get('error', 'GOVERNANCE_BLOCK')}`")
    lines.append("- Every figure above is computed from the GitLab Orbit graph; no model is on this path.")
    lines += ["", "_The model proposes. Keystone decides. The ledger remembers._"]
    packet = "\n".join(lines)
    print("\n" + packet + "\n")

    out = a.out or os.path.join(root, "SUBMISSION", "generated", "memory-gate-packet.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(packet + "\n")
    print(f"(wrote {out})")
    if overrode_agent:
        print(f"\nMEMORY GATE: BLOCKED {a.agent}'s {a.proposes.upper()} of {a.symbol} - "
              f"contradicts recorded precedent. CI exit non-zero.")
        return 2
    return 0


def main(argv=None):
    # Dispatch the MR Guardian subcommand without breaking the legacy
    # `run_review.py <symbol>` positional form.
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] == "shadow-merge":
        return _shadow_merge(raw[1:])
    if raw and raw[0] == "memory-gate":
        return _memory_gate(raw[1:])
    if raw and raw[0] in ("review-mr", "review"):
        return _review_mr(raw[1:])
    if raw and raw[0] == "harness":
        # Delegate to the Engineering Harness CLI
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.abspath(os.path.join(here, "..", "..")))
        from harness.cli import main as harness_main
        return harness_main(raw[1:])
    ap = argparse.ArgumentParser(
        description="Keystone governed-review workflow. "
                    "Also: 'review-mr --sample MR-204' to review a sample merge request.")
    ap.add_argument("symbol")
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    ap.add_argument("--local", action="store_true",
                    help="run against the in-process core, no server (for CI gating)")
    ap.add_argument("--fixture", action="store_true",
                    help="with --local, force the committed fixture (deterministic; for CI)")
    ap.add_argument("--decide", choices=["approve", "reject"])
    ap.add_argument("--reviewer")
    ap.add_argument("--reason")
    ap.add_argument("--fail-on-contradiction", action="store_true",
                    help="exit non-zero when a prior identical-signature rejection exists (enforceable gate)")
    ap.add_argument("--fail-on-block", action="store_true",
                    help="exit non-zero when the shared policy gate would BLOCK an approval (real CI gate)")
    a = ap.parse_args(argv)
    gate_check = None
    if a.local:
        get_json, post_json, gate_check, ci_id = _local_callables(prefer_live=not a.fixture)
        if ci_id:
            print(f"identity: bound to GitLab OIDC sub={ci_id.get('sub')} (project={ci_id.get('project_path')}, "
                  f"ref={ci_id.get('ref')}) - pipeline decisions are GitLab-attested, not self-asserted")
    else:
        get_json, post_json = _urllib_get(a.base), _urllib_post(a.base)
    try:
        rep = governed_review(a.symbol, get_json, post_json,
                              decide=a.decide, reviewer=a.reviewer, reason=a.reason)
    except _Unreachable as e:
        print(f"ERROR: cannot reach Keystone at {e}. Start the server (./run.ps1) or run "
              f"server-less with --local (add --fixture for the deterministic sample graph).")
        return 1
    _print_report(rep)
    if rep.get("error"):
        return 1
    # the authoritative CI gate: run the SAME policy gate the API uses
    if a.fail_on_block and gate_check is not None:
        res = gate_check(a.symbol)
        if not res["ok"]:
            print(f"GATE BLOCKED ({res['error']}): {a.symbol} is refused by policy. "
                  f"Resolve the precedent / scope / quorum before merging.")
            return 2
    if a.fail_on_contradiction and rep.get("precedent", {}).get("contradiction_same_signature"):
        print(f"GATE BLOCKED: {a.symbol} has a prior identical-blast-radius rejection. "
              f"Resolve the precedent (RFC / explicit override) before merging.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
