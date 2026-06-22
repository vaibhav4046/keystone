# Keystone - Video Final-Ready (QA'd)

Timing QA: all screen actions match the verified live product; every terminal command works from a
clean clone (`pip install -r requirements.txt` then the commands below). One timing risk found:
`pytest` takes ~15s live - do NOT run it live inside the 1:52-2:18 slot. Run it BEFORE recording and
show the final `the full suite passes` line, or just say "the full passing suite" over the `demo` output. Script fits
2:30 with that adjustment.

- Upload title: Keystone - GitLab Orbit Merge Governance for Silent Collision Detection
- Thumbnail text: Git sees files. Orbit sees relationships.
- Open (0:00): "Git review sees files. Production breaks through relationships. Keystone uses GitLab Orbit to catch merge collisions reviewers cannot see."
- End (2:30): "Git sees files. Orbit sees relationships. Keystone sees consequences."

## Final 2:30 script (timed)
| Time | Screen / action | Voiceover |
|---|---|---|
| 0:00-0:12 | live site hero, proof badges, one CTA | open line above |
| 0:12-0:28 | click Try the live demo → silent collision | "Two changes that look safe in Git, different files - Orbit shows they share runtime dependents." (compute_blast_radius × verify · 5 shared · blast 12 · real Orbit badge) |
| 0:28-0:50 | Reviewer Cockpit graph | "Keystone reads the Orbit graph, computes blast radius, shows where they break together. No LLM decides this - the graph decides." |
| 0:50-1:10 | merge verdict + safe order | "Blocked before it lands. And a safe order - not just a red light, a path forward." |
| 1:10-1:32 | Audit Ledger → Simulate tamper → restore | "Every decision is tamper-evident. Edit the record and the chain breaks. Restore and it verifies again." |
| 1:32-1:52 | pallets/click proof | "Not tuned only to Keystone - same engine on pallets/click, 1,841 definitions, real collisions there too." |
| 1:52-2:18 | terminal: `python skills/keystone/run_review.py demo` (pre-run pytest, flash `the full suite passes`) | "One command reproduces the whole story: collision blocked, safe alternative allowed, AI approval overruled by memory, ledger tamper detected. the full passing suite." |
| 2:18-2:30 | landing | "AI agents make code faster → more parallel merges. Orbit exposes the relationship graph. Keystone turns it into a deterministic pre-merge gate." + end line |

## 60-second emergency version
| Time | Screen | Voiceover |
|---|---|---|
| 0:00-0:10 | hero | "Git review sees files. Production breaks through relationships. Keystone uses GitLab Orbit to catch merge collisions reviewers cannot see." |
| 0:10-0:25 | Try the live demo → silent collision | "Two safe-looking changes, different files, no Git conflict - Orbit shows they share 5 runtime dependents." |
| 0:25-0:40 | Cockpit graph + verdict | "Keystone blocks the merge from the call graph - deterministic, no LLM - and gives a safe order." |
| 0:40-0:52 | Audit Ledger → tamper → restore | "Every decision is tamper-evident: edit a record, the chain breaks; restore, it verifies." |
| 0:52-1:00 | landing | "Same engine finds real collisions on pallets/click. Git sees files. Orbit sees relationships. Keystone sees consequences." |

## Exact terminal commands (verified)
```
python -m pytest -q                                  # the full suite passes (2 skipped)  (run BEFORE recording)
python skills/keystone/run_review.py demo            # the 6-beat story, exit 0
```

## Exact browser clicks
live URL → Try the live demo → (rail) Reviewer Cockpit → (rail) Audit Ledger → Simulate tamper → Restore/Verify chain → back to Home → pallets/click link.

## Final checklist before recording
- [ ] 1080p · browser 100% zoom · notifications + personal tabs hidden · large terminal font · no secrets
- [ ] Pre-run `pytest` so the `the full suite passes` line is visible without a 15s wait
- [ ] Render free instance may be asleep - hit https://keystone-zt6c.onrender.com once ~60s before recording to wake it (only if filming the backend; the static site needs no warm-up)
- [ ] ≤ 2:30 · upload Unlisted · paste URL back to wire into all docs

---

## 2026-06-21 note - new beats worth filming

- Open on "Watch it run": the AUTO-DEMO caption HUD now narrates each step on
  screen, so the hands-free tour reads as a guided product demo.
- Point the camera at the landing proof row: the green "Live backend verified"
  badge proves the deployed engine answers (hover shows source mode + 262 defs).
- In the Engineering Harness, scroll to the Agent fix plan card after the BLOCK
  verdict: it shows the deterministic remediation, then the ADVISORY chip.

---

## 2026-06-21 - AUTOMATED VIDEO ASSET GENERATED

An automated, self-narrated demo video now exists in the repo:

- Asset: `SUBMISSION/keystone-demo.mp4` (H.264, 1280x800, ~97s, ~2 MB)
- Generator: `scripts/record_demo_video.mjs` (headless Chrome over CDP + ffmpeg;
  re-run any time with `node scripts/record_demo_video.mjs`)
- Narration: on-screen caption overlay burned into each beat (no voice needed)
- Beats verified frame-by-frame: landing hook, "try the live demo", silent
  collision, Reviewer Cockpit blast graph, Audit Ledger, tamper -> CHAIN BROKEN,
  restore, Engineering Harness BLOCK + Agent fix plan, pallets/click external
  proof (1,841 defs), close on the landing with the live backend badge and the
  "Git sees files. Orbit sees relationships. Keystone sees consequences." line.

### Upload (user, needs login)
1. Open YouTube Studio, Create -> Upload video, select `SUBMISSION/keystone-demo.mp4`.
2. Visibility: Unlisted. Title: "Keystone - merge requests that break together".
3. Copy the watch URL into the Devpost video field (replaces VIDEO_URL_PENDING).

This is under the 3-minute hard cap and judged-ready as-is. The user may instead
record a voiced screen capture using the same storyboard if preferred; the script
asset guarantees a working video exists regardless.
