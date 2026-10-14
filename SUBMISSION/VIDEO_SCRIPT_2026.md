# Video script - Life After Code, under 3 minutes

Judges are not required to watch past 3:00, so every differentiator has to land before 2:20.
The existing `SUBMISSION/keystone-demo.mp4` (2:50) is the spine. The three new stages have no
footage yet and they are the strongest material, so they take the 0:50-2:20 window.

Every command below is runnable as written and its output is deterministic, so the recording
reproduces exactly.

---

## 0:00 - 0:15  Hook

> "Your dependency scanner just told you `duckdb` has a critical vulnerability.
> It cannot tell you whether you actually use it.
> This can."

Screen: terminal, dark, large type. No chrome, no intro animation.

## 0:15 - 0:45  The graph is the point

> "This repo indexed to GitLab Orbit: 262 definitions, real import edges.
> Not a mock. The build fails continuous integration if it drifts."

Screen: the existing demo, Orbit graph, the `orbit sql` command and its count side by side.
This shot already exists in `keystone-demo.mp4`.

**Line to say on camera:** "every number on screen is traceable to a command you can rerun."

## 0:45 - 1:15  NEW - dependency-risk propagation

Terminal, real output, no cuts:

```
$ python scripts/dependency_risk.py

[CRITICAL] DEMO-0002    duckdb        locked=1.5.3      BLOCK
         2 importing file(s): core/fixtures.py, core/graph.py
           - core.fixtures.build_fixture_duckdb   ring1=5 total=6
           - core.fixtures.seed_ledger_rows       ring1=4 total=4
           - core.graph.Graph                     ring1=4 total=4
         owners: core(6)
```

Voiceover:

> "A CVE on `duckdb`. A scanner gives you a package name. Keystone gives you the two files
> that import it, the sixteen definitions inside them, which of those sixteen drag the most
> dependents with them, and which directory owns the risk. Remediation order by blast radius,
> never by advisory ID."

Then, fast, the contrast shot - scroll to:

```
[HIGH    ] DEMO-0004    starlette     locked=0.41.3     ALLOW
         vulnerable, but no definition imports it directly
```

> "A high-severity advisory on a package we never import. It is reported as zero exposure,
> not as a clean bill of health. Over-warning is a cost. Under-warning is a defect."

## 1:15 - 1:40  NEW - incident recall

```
$ python scripts/incident_recall.py

[PREDICTION_UNDERSTATED] INC-002  (change MR-118)
    predicted=1 observed=2 hit=1 missed=1 overpredicted=0
    precision=1.0 recall=0.5 f1=0.6667
[PREDICTION_HELD]        INC-001  (change MR-118)
    predicted=1 observed=1 hit=1 missed=0 overpredicted=0
```

> "Every gate can report a blast radius all day. Only an incident can tell you if the number
> was right. This scores the engine's own recall. The one that was understated is the useful
> one: something broke that nothing had predicted, and it comes back as a precedent update."

## 1:40 - 2:00  NEW - configuration drift

```
$ python scripts/config_drift.py

  rows=2  current=2  drift=0  unknown=0
  verdict: CURRENT
```

Then the point, spoken not shown:

> "Every decision in the ledger pins the policy hash it was made under. This reads those pins
> back. Edit the policy file and every prior approval is still recorded as valid, under rules
> that no longer exist. Drift is a fact about history, not an accusation, so the queue it
> produces is a re-review list, not a blame list."

## 2:00 - 2:35  The trust boundary (existing footage)

Screen: the existing collision demo, BLOCK verdict, then the ledger chain with tamper simulation.

> "The model proposes. The engine decides. The ledger remembers, and the chain is verifiable."

This shot already exists in `keystone-demo.mp4`.

## 2:35 - 2:50  Close

Screen: the CI pipeline, green, the 7 stages scrolling.

> "Seven stages. Eleven jobs. Every gate asserted in both directions, because a gate that only
> ever fails is not a gate."

## 2:50 - 3:00  End card

Repo URL, license, one line. No music swell, no claims not shown on screen.

---

## Recording checklist

- [ ] Terminal at 200% font, dark theme, large enough to read on a phone
- [ ] No typing animation on the real commands. They are fast enough already.
- [ ] Every command typed here must be run first and its output pasted, not retyped live
- [ ] Zero-job GitLab pipeline must be fixed first, because the close shot needs green stages
- [ ] Re-record the hook if the phrasing drifts; it is the only part a judge cannot rewind for

## What this deliberately does not claim

- No CVE numbers on screen. The advisories are synthetic and clearly labelled `DEMO-*`.
- No claim that the drift checker proves a decision was wrong. It cannot, and saying so on
  camera would undercut the whole system.
- No demo of a package that is vulnerable but unimported being called "safe".
