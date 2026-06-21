# GitHub sign-in: 3-minute setup (you do this once, I built the rest)

The full OAuth flow is already coded and deployed (server-side code exchange; the
client secret never touches the browser). It is dormant until you register a GitHub
OAuth App and set two env vars. Until then the "Sign in with GitHub" button safely
falls back to the public repo scanner, so nothing is broken.

## Step 1 - Register the OAuth App (GitHub, ~1 min)

Open: https://github.com/settings/applications/new

Fill exactly:

| Field | Value |
|-------|-------|
| Application name | `Keystone` |
| Homepage URL | `https://vaibhav4046.github.io/keystone/` |
| Authorization callback URL | `https://keystone-zt6c.onrender.com/api/auth/github/callback` |

Click **Register application**. Then click **Generate a new client secret** and copy
both the **Client ID** and the **Client secret** (the secret is shown once).

## Step 2 - Set the env vars on Render (~1 min)

Render dashboard -> the `keystone` service -> **Environment** -> add:

| Key | Value |
|-----|-------|
| `KEYSTONE_GH_CLIENT_ID` | (the Client ID from step 1) |
| `KEYSTONE_GH_CLIENT_SECRET` | (the Client secret from step 1) |

Optional (defaults are already correct for the current deploy, only set if you change hosts):

| Key | Default |
|-----|---------|
| `KEYSTONE_FRONTEND_URL` | `https://vaibhav4046.github.io/keystone/` |
| `KEYSTONE_OAUTH_CALLBACK` | `https://keystone-zt6c.onrender.com/api/auth/github/callback` |

Save -> Render redeploys automatically.

## Step 3 - Verify (~30s)

1. `curl https://keystone-zt6c.onrender.com/api/auth/status` should return
   `{"configured": true, ...}`.
2. On the live site, click **Sign in with GitHub** (top right) -> GitHub consent
   screen -> you are redirected back signed in; the scan modal now lists **your own
   Python repositories** as one-click targets.

## What it does (already built)

- `GET /api/auth/github/login` -> redirect to GitHub authorize (scope `read:user public_repo`, CSRF `state`).
- `GET /api/auth/github/callback` -> exchange the code for a token **server-side**, fetch your profile, create an in-memory session, redirect back to the site with only a random session id in the URL fragment (never the token).
- `GET /api/me?sid=...` -> your login + your Python repos (server uses the stored token).
- `POST /api/auth/logout?sid=...` -> drops the session.
- Frontend: a "Sign in with GitHub" button that checks `/api/auth/status` first (so it is never a dead button), handles the OAuth return, and surfaces your repos in the scanner.

## Honest limitations

- Sessions are in-memory (the free tier is single-process); a restart signs everyone
  out. A persistent store (Redis) is the production step.
- The session id is a bearer token in the URL fragment - fine for a demo, not a
  hardened production auth. Scope is read-only (`read:user public_repo`).
- Private-repo scanning would require routing the in-browser analyzer's GitHub
  fetches through an authenticated backend proxy; the current scanner reads public
  repos. Listing your repos and scanning your public ones works today.
