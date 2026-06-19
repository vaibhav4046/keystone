# Deploy Keystone with live GitHub sign-in (~10 min)

The static GitHub Pages site already works: public repos, the demo, the analyzer, the
collision finder — all in the browser. This guide adds the one thing the browser can't do
alone: **real GitHub OAuth**, so signing in auto-loads your repositories (including private).

The serverless function that does the token exchange is already in the repo:
`web/api/github-oauth.js`. You just deploy it and register an OAuth App.

---

## 1. Register a GitHub OAuth App (2 min)

1. Go to https://github.com/settings/developers → **New OAuth App**.
2. **Application name:** `Keystone`
3. **Homepage URL:** `https://YOUR-DEPLOY-URL` (you can put a placeholder and fix it in step 4)
4. **Authorization callback URL:** `https://YOUR-DEPLOY-URL/`
5. Click **Register application**.
6. Copy the **Client ID**. Click **Generate a new client secret** and copy the **Client Secret**.
   (The secret is shown once — keep it safe. It never goes in the repo.)

## 2. Deploy `web/` to Vercel (3 min)

Using the dashboard:
1. https://vercel.com/new → **Import** the `keystone` repo.
2. **Root Directory** → `web`
3. **Framework Preset** → Other.
4. **Environment Variables** — add both:
   - `GITHUB_CLIENT_ID` = *(client id from step 1)*
   - `GITHUB_CLIENT_SECRET` = *(client secret from step 1)*
5. **Deploy.** Note the URL (e.g. `keystone-xxx.vercel.app`).

Or with the CLI from the repo root:
```bash
cd web
vercel --prod
# then add the two env vars in the Vercel project settings and redeploy
```

## 3. Tell the page its Client ID (1 min)

In `web/index.html`, add this line in `<head>` (before the app scripts):
```html
<script>window.KS_GH_CLIENT_ID = "YOUR_CLIENT_ID";</script>
```
Commit and push — Vercel auto-redeploys.

## 4. Point the OAuth App at the real URL

Back in the GitHub OAuth App settings, set **Homepage URL** and **Authorization callback URL**
to your real Vercel URL (e.g. `https://keystone-xxx.vercel.app/`). Save.

---

## Done

"Sign in with GitHub" now runs the real flow:

```
authorize on github.com
  -> redirect back with ?code
  -> /api/github-oauth exchanges the code for a token  (secret stays server-side)
  -> GET /user with the token  -> your login + repos load
```

- The **client secret never reaches the browser** — it lives only in Vercel env vars.
- The **static GitHub Pages** deploy keeps working unchanged as the public/demo fallback.
- Want private repos in the picker too? The token is stored in `sessionStorage` as
  `ks-gh-token`; point the repo lister at `https://api.github.com/user/repos` with
  `Authorization: token <that>` (a small follow-up in `repo-analyzer.js`).

## Security notes

- Never commit the client secret. Only `GITHUB_CLIENT_ID` is public (it's fine in the page).
- Rotate the secret if it ever leaks (GitHub OAuth App settings -> reset).
- Scopes requested are minimal: `read:user public_repo` (widen to `repo` only if you want private).
