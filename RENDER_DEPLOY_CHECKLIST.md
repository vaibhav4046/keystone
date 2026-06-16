# Render Deployment Configuration and Checklist

## Overview
Deploy the Keystone live backend to Render.com for the hackathon submission. This gives judges a working live demo with the AI assistant and real Orbit cross-check.

## Prerequisites

### 1. Render Account
- Sign up at: https://render.com (free, no credit card required)
- Sign in with GitHub to connect the repository

### 2. OpenRouter API Key (Optional but Recommended)
- Get a free key at: https://openrouter.ai/keys
- This enables the real AI assistant in the live demo
- Without it, the demo runs in deterministic mode (still works, just labeled)

### 3. GitLab Mirror Created
- Complete the GitLab mirror setup first (see GITLAB_SETUP_GUIDE.md)
- Render can deploy from either GitHub or GitLab

## Deployment Methods

### Method 1: Render Blueprint (Recommended - One Click)

The `render.yaml` file is already committed in this repository.

1. Go to: https://dashboard.render.com
2. Click "New" → "Blueprint"
3. Connect your GitHub account (or GitLab if you mirrored there)
4. Select the `vaibhav4046/keystone` repository
5. Render reads `render.yaml` and creates the service
6. Click "Apply" or "Create Resources"

### Method 2: Manual Service Creation

If Blueprint doesn't work, create a web service manually:

1. Go to: https://dashboard.render.com
2. Click "New" → "Web Service"
3. Connect the repository
4. Configure:
   - **Name**: keystone
   - **Runtime**: Docker
   - **Dockerfile Path**: Dockerfile
   - **Plan**: Free
5. Click "Create Web Service"

## Environment Variables (Set in Render Dashboard)

### Required
```
# Nothing strictly required - the app runs in OPEN MODE with zero keys
```

### Optional (Highly Recommended for Demo)
```
OPENROUTER_API_KEY=your_openrouter_key_here
# Or alternatively:
# CEREBRAS_API_KEY=your_cerebras_key
# GROQ_API_KEY=your_groq_key
# GEMINI_API_KEY=your_gemini_key
```

### For Production/Restricted Access
```
KEYSTONE_APPROVE_TOKEN=your_secure_random_token
KEYSTONE_OVERRIDE_TOKEN=your_secure_random_token
```

## Verification Steps

### 1. Wait for Build
- First build takes 3-6 minutes
- Watch the logs for any errors
- Service shows "Live" with green dot when ready

### 2. Test the Live URL
Open the provided `*.onrender.com` URL and verify:

- [ ] Status badge reads "LIVE" (not "SNAPSHOT")
- [ ] `https://your-url.onrender.com/api/health` returns `{"ok": true, ...}`
- [ ] Select `compute_blast_radius` - shows impact rings
- [ ] Precedent panel shows BLOCK from MR-203
- [ ] Try to approve without override - should show GOVERNANCE_BLOCK
- [ ] Check override - approval should work with override
- [ ] AI Assistant panel shows "agent - openrouter" (if key set) or "deterministic"
- [ ] Audit ledger shows chain verified

### 3. Warm Up Before Recording/Submission
- Render free tier spins down after 15 minutes of inactivity
- Open the URL 2-3 minutes before recording
- Wait for cold start to complete (30-60 seconds)
- Then start your video recording

## Common Issues and Fixes

### Build Fails
- Check the "Logs" tab in Render dashboard
- Most common: transient build hiccup
- Fix: Click "Manual Deploy" → "Deploy latest commit"

### Service Won't Start
- Verify Dockerfile works locally: `docker build -t keystone .`
- Check `$PORT` environment variable is used (it is in Dockerfile)
- Ensure requirements.txt is present and correct

### API Key Not Working
- Verify key is set in Render Environment tab
- Restart service after adding key: "Manual Deploy" → "Deploy latest commit"
- Check logs for "OPENROUTER_API_KEY not set" or similar

### Cold Start Too Slow
- This is normal for Render free tier
- Just wait it out before recording
- Consider upgrading to paid plan if needed

## After Deployment

### Update Devpost Submission
Use the Render URL as your "Try it" link:
```
Live demo: https://your-app.onrender.com
```

### Update README.md
Add the live URL near the top of README.md

### Update Video Script
Record against the live URL so badge reads "LIVE"

## Quick Reference Commands

```bash
# Test locally with Docker
docker build -t keystone .
docker run -p 8787:8787 keystone

# Run with Orbit binary (for local live mode)
$env:KEYSTONE_ORBIT_BINARY = "$env:LOCALAPPDATA\glab-cli\bin\orbit.exe"
python -m uvicorn backend.app:app --port 8787

# Run tests
$env:KEYSTONE_LLM_DISABLED=1; $env:KEYSTONE_PREFER_LIVE=0; python -m pytest -q
```

## Support

If you encounter issues:
1. Check Render docs: https://render.com/docs
2. Check the build logs in dashboard
3. Try manual deploy retry
4. Verify Dockerfile works locally
