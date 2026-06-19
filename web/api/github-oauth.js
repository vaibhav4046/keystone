// Keystone — GitHub OAuth token exchange.
//
// This is the ONE step that cannot run in the browser: GitHub's token endpoint
// sends no CORS header, and the client secret must never ship to the client.
// Deploy the web/ directory to Vercel (or any Node host that serves /api/*),
// then:
//   1. Register a GitHub OAuth App; callback URL = https://YOUR-DEPLOY/ (the page).
//   2. Set env vars GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.
//   3. Set window.KS_GH_CLIENT_ID in the page to the same client id.
// "Sign in with GitHub" then completes real OAuth and private repos load.
//
// Until deployed, the static site falls back to the public-repo connect flow.

export default async function handler(req, res) {
  const code = (req.query && req.query.code) || "";
  if (!code) {
    res.status(400).json({ error: "missing ?code" });
    return;
  }
  const clientId = process.env.GITHUB_CLIENT_ID;
  const clientSecret = process.env.GITHUB_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    res.status(500).json({ error: "GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET not configured" });
    return;
  }
  try {
    const resp = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ client_id: clientId, client_secret: clientSecret, code }),
    });
    const data = await resp.json();
    if (data.error) {
      res.status(400).json({ error: data.error_description || data.error });
      return;
    }
    res.status(200).json({ access_token: data.access_token, scope: data.scope, token_type: data.token_type });
  } catch (err) {
    res.status(500).json({ error: String((err && err.message) || err) });
  }
}
