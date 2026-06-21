export const FPS = 30;

export type SlideKind =
  | "title"
  | "statement"
  | "rows"
  | "insight"
  | "gate"
  | "pills"
  | "close";

export interface Slide {
  dur: number;
  eyebrow: string;
  kind: SlideKind;
  title: string[];
  accentLast?: boolean;
  lead?: string;
  rows?: string[];
  pills?: string[];
  verdict?: string[];
  sub?: string;
}

export const SLIDES: Slide[] = [
  {
    dur: 150,
    eyebrow: "GitLab Transcend - Orbit",
    kind: "title",
    title: ["Merge requests", "that break", "together"],
    accentLast: true,
    lead: "Keystone - the first merge gate for AI coding agents, on the GitLab Orbit graph.",
  },
  {
    dur: 210,
    eyebrow: "The problem",
    kind: "statement",
    title: ["Two safe merge requests.", "One broken production."],
    lead: "Different files. Both pass review. No Git conflict. They still break together - because one changes a function the other depends on.",
  },
  {
    dur: 210,
    eyebrow: "Why review misses it",
    kind: "rows",
    title: ["Git compares files.", "The break lives in the graph."],
    rows: [
      "Git diff and merge trains - no textual overlap, so no conflict.",
      "CODEOWNERS - each MR looks fine to its own owners.",
      "The call graph sees the shared dependents. Nothing else does.",
    ],
  },
  {
    dur: 240,
    eyebrow: "The insight",
    kind: "insight",
    title: ["Orbit sees the", "transitive intersection."],
  },
  {
    dur: 180,
    eyebrow: "What Keystone does",
    kind: "gate",
    title: ["A deterministic gate.", "No model decides."],
    verdict: ["ALLOW", "HOLD", "BLOCK"],
    sub: "Blast radius to policy tier to required approvers, recorded in a tamper-evident ledger. Zero LLM on the verdict.",
  },
  {
    dur: 180,
    eyebrow: "The new capability",
    kind: "statement",
    title: ["It holds AI coding", "agents accountable."],
    lead: "An agent cannot self-approve. A recorded rejection of a blast signature blocks re-approval by any party.",
  },
  {
    dur: 210,
    eyebrow: "Real, three ways",
    kind: "rows",
    title: ["The same Orbit SQL,", "three independent runs."],
    rows: [
      "Server-side on the deployed engine, ring-1 = 12",
      "duckdb-wasm in your browser - same query, same 12",
      "The test suite recomputes it - they all converge",
    ],
  },
  {
    dur: 180,
    eyebrow: "Any repo, zero setup",
    kind: "pills",
    title: ["Not just Orbit-Local orgs.", "Any repo. Any CI."],
    lead: "scan-repo owner/repo builds the Orbit graph on the fly and gates it - no pre-indexing.",
    pills: ["124 tests pass", "No LLM verdict", "Live backend", "Tamper-evident"],
  },
  {
    dur: 240,
    eyebrow: "Keystone",
    kind: "close",
    title: ["Git sees files.", "Orbit sees relationships.", "Keystone sees consequences."],
    lead: "Now, the live product. A real repo. A real collision. Blocked before merge.",
  },
];
