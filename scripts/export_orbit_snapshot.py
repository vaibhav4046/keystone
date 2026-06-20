"""Export the REAL GitLab Orbit self-index (data/keystone_self_graph.duckdb) to
web/orbit_snapshot.json in the window.__ksScan shape the live UI consumes.

This is what lets the deployed site show ACTUAL Orbit graph data (gl_definition /
gl_edge CALLS traversal) instead of the in-browser GitHub-API stand-in. Re-run with:
    python scripts/export_orbit_snapshot.py

Every displayed number is computed from the graph here; nothing is a cosmetic
fraction. Headline symbols are scoped to real core Python source (no test files,
build scripts, or web JS) and to valid identifiers, so the demo never shows junk
symbols like "$" or "_parse_rows" in the blast radius or safe merge order.
"""
import collections
import json
import re

import duckdb

DB = "data/keystone_self_graph.duckdb"
OUT = "web/orbit_snapshot.json"

# Reject framework noise and accessor/lifecycle names that are not interesting blast targets.
BAN = re.compile(r"^(__|self|cls|get|set|run|main|close|open|init|name|args|kwargs|test)", re.I)
# A real, displayable symbol: a valid identifier, at least 3 chars, no leading underscore.
VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,}$")
# Path fragments that are not production source we want to headline.
EXCLUDE_FRAGMENTS = ("test", "/web/", "web/", "scripts/", "node_modules",
                     "conftest", ".spec", "setup.py", "__main__")


def ok_name(name: str) -> bool:
    return bool(VALID_NAME.match(name)) and not BAN.match(name)


def ok_file(fp: str) -> bool:
    if not fp or not fp.endswith(".py"):
        return False
    low = fp.lower()
    return not any(frag in low for frag in EXCLUDE_FRAGMENTS)


def main() -> None:
    con = duckdb.connect(DB, read_only=True)
    defs: dict[int, dict] = {}
    for i, name, fp, dt in con.execute(
        "select id, name, file_path, definition_type from gl_definition"
    ).fetchall():
        defs[i] = {"name": name, "file": fp or "", "kind": (dt or "definition")}

    # CALLS edge: source calls target -> source is a direct dependent of target.
    callers: dict[int, set] = collections.defaultdict(set)
    for s, t in con.execute(
        "select source_id, target_id from gl_edge where relationship_kind='CALLS'"
    ).fetchall():
        if s in defs and t in defs and s != t:
            callers[t].add(s)

    blast = {i: len(callers.get(i, ())) for i in defs}
    nm = lambda i: defs[i]["name"]
    fo = lambda i: defs[i]["file"]
    ok = lambda i: ok_name(nm(i)) and ok_file(fo(i))

    # All definitions ranked by blast; the headline set is the real-source subset.
    ranked = sorted(defs, key=lambda i: -blast[i])
    ranked_ok = [i for i in ranked if ok(i)]

    cand = [i for i in ranked_ok if blast[i] > 2][:16]
    best, collisions, overlap, pairs = None, 0, collections.defaultdict(int), []
    for x in range(len(cand)):
        for y in range(x + 1, len(cand)):
            a, b = cand[x], cand[y]
            if fo(a) == fo(b):  # require the two changes to live in different files
                continue
            sh = len(callers[a] & callers[b])
            if sh > 2:
                collisions += 1
                overlap[a] += sh
                overlap[b] += sh
                pairs.append({"a": nm(a), "b": nm(b), "aFile": fo(a),
                              "bFile": fo(b), "shared": sh})
                if best is None or sh > best["sh"]:
                    best = {"a": a, "b": b, "sh": sh}
    safe = sorted(cand, key=lambda i: overlap[i])[:6]
    collision_list = sorted(pairs, key=lambda p: -p["shared"])[:24]

    head = ranked_ok if ranked_ok else ranked
    mx = blast[head[0]] if head else 1
    lvl = lambda t: "High" if t >= mx * 0.5 else ("Medium" if t >= mx * 0.2 else "Low")
    top = [{"sym": nm(i), "file": fo(i), "kind": defs[i]["kind"],
            "blast": blast[i], "level": lvl(blast[i])} for i in head[:6]]

    chain = []
    if best:
        for s in [c for c in callers[best["a"]] if ok(c)][:5]:
            chain.append({"sym": nm(s), "file": fo(s)})

    # Real ring counts from the graph (no cosmetic fractions):
    #   ring1 = dependents that call BOTH changed symbols (the silent-collision set)
    #   ring2 = dependents that call EITHER but not both (the rest of the combined blast)
    if best:
        union = callers[best["a"]] | callers[best["b"]]
        sh = best["sh"]
        ring1 = sh
        ring2 = len(union) - sh
    else:
        sh = ring1 = ring2 = 0

    snap = {
        "repo": "GitLab Orbit · keystone self-index",
        "orbit": True,
        "defs": f"{len(defs):,}",
        "maxBlast": blast[head[0]] if head else 0,
        "maxSym": nm(head[0]) if head else "-",
        "a": nm(best["a"]) if best else (top[0]["sym"] if top else "-"),
        "b": nm(best["b"]) if best else (top[1]["sym"] if len(top) > 1 else "-"),
        "aFile": fo(best["a"]) if best else "", "bFile": fo(best["b"]) if best else "",
        "aBlast": blast[best["a"]] if best else (top[0]["blast"] if top else 0),
        "bBlast": blast[best["b"]] if best else 0,
        "shared": sh, "ring1": ring1, "ring2": ring2,
        "collisions": collisions,
        "collisionList": collision_list,
        "safeOrder": [nm(i) for i in safe],
        "spofPct": round(blast[head[0]] / len(defs) * 100) if defs and head else 0,
        "top": top, "chain": chain,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f)
    print("SNAP", snap["defs"], "defs", collisions, "collisions",
          snap["a"], "x", snap["b"], "shared", sh,
          "ring1", ring1, "ring2", ring2, "spof", snap["spofPct"])
    print("top:", [t["sym"] for t in top])
    print("safeOrder:", snap["safeOrder"])


if __name__ == "__main__":
    main()
