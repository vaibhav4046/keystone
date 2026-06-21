# Keystone presentation video (Remotion)

Renders Part 1 of the demo (the ~60-second presentation) as an MP4, in the same
black + pixel (HydraDB-style) aesthetic as the live site. Part 2 (the live product
walkthrough) is screen-recorded separately per `../SUBMISSION/VIDEO_PRESENTATION_SCRIPT.md`.

## Render

```
cd remotion
npm install
npm run render        # -> out/keystone-presentation.mp4  (1920x1080, 30fps, ~60s)
```

First render downloads a headless Chrome (one time). Output is gitignored; copy the file
to `../SUBMISSION/` when you want to ship it.

## Edit / preview

```
npm run studio        # Remotion Studio at http://localhost:3000 - scrub, tweak, hot-reload
```

All deck content is data-driven in `src/slides.ts` (one object per slide: eyebrow, title
lines, lead, rows, verdict, pills). Visuals and motion live in `src/KeystoneVideo.tsx`;
the animated blast graph is `src/Graph.tsx`. Fonts: Pixelify Sans (headlines), Inter
(body), JetBrains Mono (labels), via `@remotion/google-fonts`.

## Structure

| File | Purpose |
|------|---------|
| `src/Root.tsx` | registers the `Keystone` composition (duration = sum of slide durations) |
| `src/slides.ts` | the 9-slide script as data |
| `src/KeystoneVideo.tsx` | backdrop, per-slide reveal animation, HUD (wordmark, progress, counter) |
| `src/Graph.tsx` | animated radial call-graph with two pulsing collision nodes |
| `remotion.config.ts` | render config (jpeg frames, overwrite output) |
