# Deploy the live backend on Render (the single biggest score lever left)

Every judge panel and the external audit agree on the #1 code-adjacent move: the public GitHub
Pages link is a static snapshot, so a judge who clicks it never hits the live tool-using agent,
the live `orbit sql` cross-check, or a fresh LLM brief. Standing up the backend makes the public
URL the real product. It is free, takes about five minutes, needs no credit card, and the
Blueprint is already committed (`render.yaml`). This is yours to do; here is the exact path.

## What you get

A live URL (for example `https://keystone.onrender.com`) that serves the same hero same-origin,
but now backed by the real engine: the status badge reads `LIVE` (not `SNAPSHOT`), the AI
assistant runs a fresh bounded tool-loop on demand, and the `orbit sql` cross-check runs live.
It runs over the committed real self-index (262 definitions) in LIVE mode, so every number stays
real and reproducible.

## Steps (about 5 minutes)

1. Go to https://render.com and sign up. The free "Hobby" tier needs no credit card. Sign in
   with your GitHub account so Render can see the repo.
2. Top right: **New +** then **Blueprint**.
3. Connect the repository **vaibhav4046/keystone**. Render reads the committed `render.yaml` and
   shows one service: a free Docker web service named `keystone`. Click **Apply** (or **Create
   Resources**).
4. Render builds the `Dockerfile` and deploys. First build is roughly 3 to 6 minutes. When the
   service shows **Live** with a green dot, click the URL at the top (the `*.onrender.com`
   address). That URL is now your live demo.
5. Confirm it is real: the status badge in the header should read **LIVE** (or `CLI+DuckDB` for
   the orbit access), and `https://<your-url>/api/health` returns `{"ok": true, ...}`.

## Optional but worth it: turn on the real LLM (2 more minutes)

Without a key the live demo runs the deterministic plan (still labeled honestly). With one free
key the AI brief and the agent run a real model on camera.

1. In the Render dashboard, open the `keystone` service, then **Environment**.
2. **Add Environment Variable**: key `OPENROUTER_API_KEY`, value your free OpenRouter key. Save.
   (Cerebras, Groq, or Gemini env vars work too; the ladder tries them in order.)
3. Render redeploys automatically. The AI ASSISTANT panel will now say `agent - openrouter`
   instead of `deterministic`.

Never paste the key anywhere it gets committed. It only lives in the Render dashboard.

## Then wire the live URL into the submission

- **Devpost:** put the `*.onrender.com` URL as the "Try it" link (and keep the GitHub Pages link
  too if you like; the live one is the one that scores).
- **README:** replace or add the live link near the top so a judge browsing the repo finds it.
- **Video:** record against the live URL so the badge reads LIVE and the agent runs fresh on
  camera. That directly answers the judges' "I only saw a static snapshot" objection.

## Two honesty notes, so nothing surprises you or a judge

- The free tier **spins down after about 15 minutes of inactivity**, and the next request cold-
  starts in roughly 30 to 60 seconds. Before you record the video, and right before you submit,
  open the URL once to warm it so a judge does not hit a cold spinner. The status banner already
  says the deployment is in OPEN MODE.
- A public live backend runs in **OPEN MODE** (any caller can record a decision; identity is
  self-asserted, and the UI says so) and the per-instance ledger resets on each redeploy. If you
  want the gate write-protected for a public audience, add `KEYSTONE_APPROVE_TOKEN` (and
  optionally `KEYSTONE_OVERRIDE_TOKEN`) as environment variables; then `POST /api/approve`
  requires a matching header. For a demo you usually want it open so a judge can click through.

## If the build fails

The `Dockerfile` is `$PORT`-aware and self-contained; the most common cause is a transient Render
build hiccup. Open the service's **Logs** tab, read the last error, and click **Manual Deploy ->
Deploy latest commit** to retry. The same image runs unchanged on Fly.io (`fly launch --copy-config
--now`, uses the committed `fly.toml`) or any Docker host if you prefer.
