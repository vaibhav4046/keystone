# Video automation status

Status: **Completed (asset generated)**. Upload itself is Waiting for user login.

## What was attempted and succeeded

The environment has Chrome + ffmpeg 8.1.1 + Node 24, so an automated demo video
was generated end to end (not deferred):

- `scripts/record_demo_video.mjs` drives the live site in headless Chrome over
  CDP, burns a timed caption overlay into the page for narration, captures JPEG
  frames at 10 fps, and assembles them into H.264 MP4 with ffmpeg.
- Output: `SUBMISSION/keystone-demo.mp4` (1280x800, ~97s, ~2 MB).
- Verified frame-by-frame against the storyboard (landing, live demo, cockpit
  blast graph, ledger tamper/restore, harness BLOCK + agent fix plan, pallets/click
  external proof, live-backend close).

## Tooling found

| Tool | Present | Used for |
|------|---------|----------|
| Chrome (headless) | yes | drive + capture frames over CDP |
| ffmpeg 8.1.1 | yes | assemble frames to MP4 (libx264, yuv420p, faststart) |
| Node 24 | yes | run the recorder (global fetch + WebSocket) |
| Puppeteer/Playwright | no | not needed; raw CDP used instead |

## What is still blocked (Waiting for user login or approval)

- Uploading the MP4 to YouTube/Vimeo unlisted and pasting the URL into Devpost.
  Both need the user's account login; the asset and exact steps are ready in
  `VIDEO_FINAL_READY.md`.

## Re-generate any time

```
node scripts/record_demo_video.mjs            # records the live site
KS_URL=http://127.0.0.1:8899/index.html node scripts/record_demo_video.mjs
```
