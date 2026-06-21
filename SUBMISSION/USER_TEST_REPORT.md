# Keystone - User Test Report (simulated persona walkthroughs)

Method: SIMULATED persona walkthroughs of the live product (https://vaibhav4046.github.io/keystone/
+ backend https://keystone-zt6c.onrender.com), grounded in verified live behavior - not real-user
sessions. Each row records what the persona understands, where they hesitate, and the fix (if any).
Live behavior verified this pass: one CTA, deep-links to Cockpit/Ledger land, tamper→restore works,
cockpit graph 17/17, pallets/click loads 1,841 defs, no overflow at 320/375/390, zero console errors.

| User | Task | Observed issue | Severity | Fix made | Verification | Remaining risk |
|---|---|---|---|---|---|---|
| Tired judge, 90s | Understand + judge in 90s | None - hero wedge + one CTA + "judge demo" numbered panel carry it | - | already shipped: one CTA, judge-demo panel | break-test: oneCTA=1, judgeDemo panel present | none code-side |
| GitLab engineer | Is Orbit use real? | Wants real gl_definition/gl_edge | Low | already shipped: green "REAL GitLab Orbit graph" badge + README orbit-sql cross-check | live badge renders; /api/status orbit_access=DuckDB(LIVE) | wants live `orbit sql` on Render (external pref) |
| Orbit engineer | Generality | "Tuned only to your repo?" | Low | already shipped: "Not tuned to our own repo" panel + pallets/click load | clickDefs=1,841 on live | none |
| Security reviewer | Trust verdict + ledger | Could overclaim tamper-proof | Low | already shipped: FNV-vs-HMAC + self-asserted-vs-OIDC labels; "tamper-evident" not "tamper-proof" | ledger badge "DEMO HASH FNV-1a / prod HMAC-SHA256"; tamper→broken→restore | asymmetric ledger = roadmap (disclosed) |
| AI skeptic | "Is the verdict AI slop?" | Must see no-LLM clearly | Low | already shipped: "No LLM on the verdict" badge + verify panel | badge present; CLI `demo` deterministic | none |
| Product manager | What pain, who pays | Impact/TAM not obvious | Medium | copy: impact proof + agent-velocity thesis in FINAL_10_PACKET/STAGE1_ASSETS | docs carry the concrete scenario | TAM needs a real incident metric (external) |
| DevRel judge | Is the demo clean to show | Demo path must be obvious | Low | already shipped: numbered judge-demo panel + one-command `demo` | break-test deep-links land | needs the video (recording-blocked) |
| Beginner dev | Can I follow it | Jargon (blast radius, collision) | Low | already shipped: hero plain-language "two safe MRs break together"; tooltips | hero copy concise, 2 lines | none |

## Summary
- Issues that caused hesitation and were code/copy-fixable: all already fixed in prior passes (one CTA, judge-demo panel, verify panel, honesty labels, external-repo panel, concise hero). This pass found NO new fixable product/copy defect - re-verified live.
- Medium (Impact/TAM): mitigated in copy as far as honest; a real incident/partner metric is the only further lift and is external.
- Recording-blocked: the demo video (DevRel persona's one ask) - script ready, needs the owner's recording/upload.
