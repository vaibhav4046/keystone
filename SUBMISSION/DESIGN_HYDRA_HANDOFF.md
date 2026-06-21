# HydraDB design language -> Keystone re-skin + Remotion (handoff)

Captured live from https://hydradb.com (2026-06). Built with Framer. Keystone is already
in the same family (dark + orange + pixel graph), so this is a tightening, not a rebuild.

## HydraDB design tokens (observed)
- Background: pure black `#000000`. Text: white `#fff`, dim grey for secondary.
- Accent: orange -> amber, expressed as a PIXELATED / dot-matrix graph artifact glowing on
  black (a branching tree of orange-amber square cells). Same idea as Keystone's blast graph.
- Type: Aeonik (Aeonik Medium headings, Aeonik Regular body) - a premium geometric sans.
  Aeonik is paid (no free CDN). Closest free swaps: Geist, General Sans, or Space Grotesk
  (Keystone already loads Space Grotesk). The HUGE headline is rendered with a pixel /
  dot-matrix texture.
- Faint vertical grid lines down the full background.
- Nav: wordmark + hex icon left, centered links, dark "Log In" + white "Sign Up" right.
- Motion: Framer Motion - smooth opacity+translate reveals on scroll, the dot-matrix graph
  animates cell by cell. Headline "The Graph Behind Your Agents." (near-identical to our pitch).

## Keystone re-skin plan (small, safe slices - do in order, verify each)
1. Background: shift `--bg` from #0a0706 to pure `#000` (or keep a hair of warmth). One token.
2. Vertical grid lines: add a fixed background layer of faint vertical rules (1px, ~6% white,
   every ~80px) behind the hero. Pure CSS, ~6 lines.
3. Headline pixel treatment: render the hero H1 with a dot-matrix mask/texture (CSS
   background-clip + a small pixel pattern, or an SVG/canvas pass). The blast-art canvas
   already proves the pixel aesthetic - reuse that look on the H1.
4. Type: keep Space Grotesk / Bodoni (already premium); optionally swap body to a geometric
   sans (Geist via self-host). Do NOT pull Aeonik (paid).
5. Motion polish: add Framer-Motion-style reveals. The dc-runtime is React-like; the simplest
   safe path is IntersectionObserver + the existing keyframes (riseIn/nodeIn), not a new dep.
   If a real framer-motion build is wanted, it needs a bundler (the landing is currently
   dependency-free), which is a larger change - decide explicitly.

## Remotion (remotion.dev) plan - it is a SEPARATE video project, not part of the site
Remotion renders videos programmatically with React (-> MP4). Use it to generate the demo
video in this aesthetic, replacing/upgrading scripts/record_demo_video.mjs.
1. `npm create video@latest` in a new `remotion/` folder (its own package.json - keep it out
   of the Pages build).
2. Build compositions matching web/present.html slides (black bg, pixel headline, dot-matrix
   graph, orange accents), one Sequence per beat, with the VIDEO_PRESENTATION_SCRIPT.md timing.
3. Optionally embed real product screen-captures (the existing CDP harness frames) as stills
   between animated slides.
4. `npx remotion render` -> SUBMISSION/keystone-demo.mp4 (replaces the current asset).
Cost note: Remotion adds a node toolchain + render time; it does not deploy to GitHub Pages.

## Why this is a fresh-session job
A full re-skin + a Remotion project is multi-hour. It was NOT started here to avoid a
half-done, build-breaking edit at context limit. Each slice above is independently shippable
and verifiable (break-test must stay 0 console errors / no overflow 320-1440). Start with
slices 1-3 (pure CSS, highest visual payoff, lowest risk), verify live, then decide on
framer-motion (needs a bundler) and Remotion (separate project).
