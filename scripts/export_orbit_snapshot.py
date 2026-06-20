"""Export the REAL GitLab Orbit self-index (data/keystone_self_graph.duckdb) to
web/orbit_snapshot.json in the window.__ksScan shape the live UI consumes.

This is what lets the deployed site show ACTUAL Orbit graph data (gl_definition /
gl_edge CALLS traversal) instead of the in-browser GitHub-API stand-in. Re-run with:
    python scripts/export_orbit_snapshot.py
"""
import duckdb, json, collections, re

DB = "data/keystone_self_graph.duckdb"
OUT = "web/orbit_snapshot.json"
BAN = re.compile(r"^(__|self|cls|get|set|run|main|close|open|init|name|args|kwargs|test)", re.I)


def main():
    con = duckdb.connect(DB, read_only=True)
    defs = {}
    for i, name, fp, dt in con.execute(
        "select id, name, file_path, definition_type from gl_definition"
    ).fetchall():
        defs[i] = {"name": name, "file": fp or "", "kind": (dt or "definition")}

    # CALLS edge: source calls target -> source is a direct dependent of target.
    callers = collections.defaultdict(set)
    for s, t in con.execute(
        "select source_id, target_id from gl_edge where relationship_kind='CALLS'"
    ).fetchall():
        if s in defs and t in defs and s != t:
            callers[t].add(s)

    blast = {i: len(callers.get(i, ())) for i in defs}
    ranked = sorted(defs, key=lambda i: -blast[i])
    nm = lambda i: defs[i]["name"]
    fo = lambda i: defs[i]["file"]

    cand = [i for i in ranked if not BAN.match(nm(i)) and blast[i] > 2][:16]
    best, collisions, overlap = None, 0, collections.defaultdict(int)
    for x in range(len(cand)):
        for y in range(x + 1, len(cand)):
            a, b = cand[x], cand[y]
            if not fo(a) or not fo(b) or fo(a) == fo(b):
                continue
            sh = len(callers[a] & callers[b])
            if sh > 2:
                collisions += 1
                overlap[a] += sh
                overlap[b] += sh
                if best is None or sh > best["sh"]:
                    best = {"a": a, "b": b, "sh": sh}
    safe = sorted(cand, key=lambda i: overlap[i])[:4]

    mx = blast[ranked[0]] if ranked else 1
    lvl = lambda t: "High" if t >= mx * 0.5 else ("Medium" if t >= mx * 0.2 else "Low")
    top = [{"sym": nm(i), "file": fo(i), "kind": defs[i]["kind"], "blast": blast[i], "level": lvl(blast[i])} for i in ranked[:6]]
    chain = []
    if best:
        for s in list(callers[best["a"]])[:5]:
            chain.append({"sym": nm(s), "file": fo(s) or "core"})

    sh = best["sh"] if best else 0
    snap = {
        "repo": "GitLab Orbit · keystone self-index",
        "orbit": True,
        "defs": f"{len(defs):,}",
        "maxBlast": blast[ranked[0]] if ranked else 0,
        "maxSym": nm(ranked[0]) if ranked else "-",
        "a": nm(best["a"]) if best else (top[0]["sym"] if top else "-"),
        "b": nm(best["b"]) if best else (top[1]["sym"] if len(top) > 1 else "-"),
        "aFile": fo(best["a"]) if best else "", "bFile": fo(best["b"]) if best else "",
        "aBlast": blast[best["a"]] if best else (top[0]["blast"] if top else 0),
        "bBlast": blast[best["b"]] if best else 0,
        "shared": sh, "ring1": round(sh * 0.4), "ring2": sh - round(sh * 0.4),
        "collisions": collisions,
        "safeOrder": [nm(i) for i in safe],
        "spofPct": round(blast[ranked[0]] / len(defs) * 100) if defs else 0,
        "top": top, "chain": chain,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f)
    print("SNAP", snap["defs"], "defs", collisions, "collisions",
          snap["a"], "x", snap["b"], "shared", sh, "spof", snap["spofPct"])


if __name__ == "__main__":
    main()
