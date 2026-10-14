"""Dependency-risk propagation (priority G).

`core/advisory.py` joins a package advisory to the Orbit code graph so a CVE
answer becomes an engineering answer: which definitions import the vulnerable
package, how far the damage travels from each, and which directory owns the
blast. Everything is computed from real graph rows and a real lockfile.

The tests below pin the behaviours that matter for a gate decision:

  * version matching never guesses (absent pin, unsupported operator, exact-pin)
  * import resolution is prefix-based, as Python imports actually resolve
  * propagation ranks by real blast radius, not by name or file order
  * the same inputs always produce the same output (determinism is the engine's
    core contract; a gate that flips between runs is worse than no gate)

Honest limit, also stated in the module docstring: propagation is file-scoped.
Import edges and call edges are different relations, so every definition in an
importing file is treated as a candidate entry point. That over-approximates
relative to a per-definition import map, and `Exposure.scope == "file"` is what
tells a reader which mode produced the number.
"""
import json

import pytest

from core import advisory as A
from core.graph import Graph

REAL_GRAPH = r"data/keystone_self_graph.duckdb"


# --------------------------------------------------------------- normalisation

def test_normalize_package_folds_pep503_equivalent_spellings():
    # An advisory feed saying "Flask_Login" and a lockfile saying "flask-login"
    # are the same package. Without folding, the match silently misses.
    assert A.normalize_package("Flask_Login") == A.normalize_package("flask-login")
    assert A.normalize_package("zope.interface") == "zope-interface"
    assert A.normalize_package("  FastAPI  ") == "fastapi"


# --------------------------------------------------------------- lockfile

def test_parse_requirements_takes_pins_only_and_ignores_ranges(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(
        "\n".join([
            "duckdb==1.5.3",
            "fastapi>=0.110,<0.116",
            "pydantic >=2.0",
            "# a comment duckdb==9.9.9",
            "-e .",
            "cryptography>=42.0   # inline comment",
        ]),
        encoding="utf-8",
    )
    got = A.parse_requirements(str(req))
    # Only the `==` line is a fact about what is installed. A range tells us
    # nothing concrete, so inventing a version there would be a confident lie.
    assert got == {"duckdb": "1.5.3"}


def test_parse_requirements_missing_file_is_empty_not_an_error(tmp_path):
    assert A.parse_requirements(str(tmp_path / "nope.txt")) == {}


# --------------------------------------------------------------- version match

@pytest.mark.parametrize("version,spec,expected", [
    ("1.5.3", "<1.5.4", True),
    ("1.5.3", "<=1.5.3", True),
    ("1.5.4", "<1.5.4", False),
    ("1.5.3", "==1.5.3", True),
    ("1.5.3", "==1.5.4", False),
    ("1.5.3", ">=1.5.0", True),
    ("2.13.4", "==2.13.0", False),
    ("0.115.6", "<0.116.0", True),
])
def test_matches_spec_handles_the_operators_real_feeds_use(version, spec, expected):
    hit, reason = A.matches_spec(version, spec)
    assert hit is expected
    assert reason and version in reason


def test_matches_spec_refuses_unsupported_operator_rather_than_guessing():
    # A caret range we do not implement must be reported as unsupported, not
    # silently treated as a match or a non-match.
    hit, reason = A.matches_spec("1.2.3", "^1.2.0")
    assert hit is False
    assert "unsupported" in reason


def test_matches_spec_without_a_version_is_not_a_match():
    hit, _ = A.matches_spec("", "<1.0.0")
    assert hit is False


# --------------------------------------------------------------- advisories

def test_load_advisories_accepts_bare_list_and_wrapped_form(tmp_path):
    bare = tmp_path / "a.json"
    bare.write_text(json.dumps([
        {"id": "X-1", "package": "DuckDB", "affected": "<2", "severity": "high"},
    ]), encoding="utf-8")
    wrapped = tmp_path / "b.json"
    wrapped.write_text(json.dumps({"advisories": [
        {"id": "X-1", "package": "DuckDB", "affected": "<2", "severity": "high"},
    ]}), encoding="utf-8")

    a = A.load_advisories(str(bare))
    b = A.load_advisories(str(wrapped))
    assert len(a) == 1 and a[0].severity == "HIGH"   # severity is normalised up
    assert a[0].norm_package == "duckdb"
    assert a == b


def test_load_advisories_missing_file_is_empty(tmp_path):
    assert A.load_advisories(str(tmp_path / "none.json")) == []
    assert A.load_advisories("") == []


# --------------------------------------------------------------- propagation

@pytest.fixture(scope="module")
def real_graph():
    g = Graph(path=REAL_GRAPH)
    yield g
    g.close()


def test_importing_files_matches_prefixes_as_python_imports_resolve(real_graph):
    # `import fastapi.responses` is an import of `fastapi`.
    files = A.importing_files(real_graph, "fastapi")
    assert "backend/app.py" in files
    assert A.importing_files(real_graph, "a-package-nobody-imports") == []


def test_propagate_blocks_a_real_vulnerable_dependency(real_graph):
    adv = A.Advisory(id="T-1", package="duckdb", affected="<1.5.4", severity="CRITICAL")
    ex = A.propagate(real_graph, adv, {"duckdb": "1.5.3"})

    assert ex.matched is True
    assert ex.advisory.severity == "CRITICAL"
    # real files, read from gl_imported_symbol -- not hardcoded
    assert set(ex.imported_files) == {"core/graph.py", "core/fixtures.py"}
    assert ex.entry_point_count > 0
    assert ex.max_affected > 0
    assert ex.verdict() == "BLOCK"
    # the owning directory is derived from the graph, not asserted by hand
    assert {o["dir"] for o in ex.owners} <= {"core", ""}


def test_propagate_ranks_entry_points_by_real_blast_radius(real_graph):
    adv = A.Advisory(id="T-2", package="duckdb", affected="<1.5.4", severity="HIGH")
    ex = A.propagate(real_graph, adv, {"duckdb": "1.5.3"})

    blasts = [e.total_affected for e in ex.entry_points]
    assert blasts == sorted(blasts, reverse=True), "must be ordered worst-first"
    # every entry point carries a signature so it can be tied to ledger precedent
    sigs = [e.blast.signature_fqn for e in ex.entry_points if e.blast]
    assert sigs and all(s for s in sigs)


def test_propagate_refuses_to_guess_when_the_package_is_not_pinned(real_graph):
    adv = A.Advisory(id="T-3", package="duckdb", affected="<1.5.4", severity="CRITICAL")
    ex = A.propagate(real_graph, adv, {})          # empty lockfile
    assert ex.matched is False
    assert "not pinned" in ex.match_reason
    assert ex.verdict() == "ALLOW"
    assert ex.entry_points == []


def test_propagate_is_not_matched_when_the_version_is_safe(real_graph):
    adv = A.Advisory(id="T-4", package="pydantic", affected="==2.13.0", severity="MEDIUM")
    ex = A.propagate(real_graph, adv, {"pydantic": "2.13.4"})
    assert ex.matched is False
    assert ex.entry_points == []


def test_a_vulnerable_package_that_nothing_imports_is_reported_honestly(real_graph):
    # starlette is a transitive dep of fastapi but is never imported directly
    # in this repo. Reporting "affected: 0" as a clean bill of health would be
    # the dangerous kind of wrong; the entry point list must simply be empty.
    adv = A.Advisory(id="T-5", package="starlette", affected="<0.42.0", severity="HIGH")
    ex = A.propagate(real_graph, adv, {"starlette": "0.41.3"})
    assert ex.matched is True
    assert ex.imported_files == []
    assert ex.entry_point_count == 0


def test_propagation_is_deterministic(real_graph):
    adv = A.Advisory(id="T-6", package="duckdb", affected="<1.5.4", severity="HIGH")
    locked = {"duckdb": "1.5.3"}
    a = A.propagate(real_graph, adv, locked).to_dict()
    b = A.propagate(real_graph, adv, locked).to_dict()
    assert a == b, "a gate that flips between identical runs is worse than no gate"


def test_propagate_all_orders_by_severity_then_damage(real_graph):
    advs = [
        A.Advisory(id="LOW-1", package="duckdb", affected="<1.5.4", severity="LOW"),
        A.Advisory(id="CRIT-1", package="fastapi", affected="<0.116.0", severity="CRITICAL"),
        A.Advisory(id="MED-1", package="pydantic", affected="<3", severity="MEDIUM"),
    ]
    out = A.propagate_all(real_graph, advs, {"duckdb": "1.5.3", "fastapi": "0.115.6", "pydantic": "2.13.4"})
    sev = [e.advisory.severity for e in out]
    assert sev == ["CRITICAL", "MEDIUM", "LOW"]


def test_to_dict_is_json_serialisable_and_carries_the_scope(real_graph):
    adv = A.Advisory(id="T-7", package="duckdb", affected="<1.5.4", severity="HIGH")
    d = A.propagate(real_graph, adv, {"duckdb": "1.5.3"}).to_dict()
    json.dumps(d)  # must not raise
    assert d["scope"] == "file", "the file-scoped approximation must be visible in the output"
    assert d["advisory"]["package"] == "duckdb"
    assert "max_affected" in d and "owners" in d


def test_verdict_holds_when_affected_but_below_the_block_threshold(real_graph):
    adv = A.Advisory(id="T-8", package="fastapi", affected="<0.116.0", severity="HIGH")
    ex = A.propagate(real_graph, adv, {"fastapi": "0.115.6"})
    # Raising the threshold above every entry point's blast must soften the
    # decision, which proves the verdict is computed from the number and not
    # hardcoded off severity.
    assert ex.max_affected <= 100
    assert ex.verdict(block_above=10_000) == "HOLD"