# GitLab Mirror Setup Instructions

## Overview
This repository needs a GitLab mirror for the GitLab Transcend hackathon submission. The GitLab mirror is a required component that judges will check to verify the entry is properly hosted.

## What You Need

### 1. GitLab Personal Access Token
- Go to: https://gitlab.com/profile/account
- Scroll down to "Personal Access Tokens"
- Click "Create new token"
- Name it: "Hackathon Submission"
- Scopes: "api" (and optionally "read_repository")
- Copy the token (long string of characters)

### 2. Environment Variable
Set your GitLab token as an environment variable:

**Windows PowerShell:**
```powershell
$env:GITLAB_TOKEN = "your_token_here"
```

**macOS/Linux:**
```bash
export GITLAB_TOKEN="your_token_here"
```

### 3. GitLab Account
You need a GitLab account. If you don't have one:
- Sign up at: https://gitlab.com/users/sign_up

## Step-by-Step Instructions

### Option 1: Use the PowerShell Script
1. Save the `create-gitlab-mirror.ps1` script from this repository
2. Run it in PowerShell:

```powershell
.
create-gitlab-mirror.ps1
```

**Note:** You'll need to set `$env:GITLAB_TOKEN` before running the script.

### Option 2: Manual Steps
1. **Create GitLab Repository**
   - Log in to GitLab
   - Click "New project" → "Create blank project"
   - Name: `keystone`
   - Visibility: "Public"
   - Do NOT initialize with README
   - Click "Create project"

2. **Push GitHub to GitLab**
   ```bash
   cd D:/project/keystone
   git remote add gitlab https://gitlab.com/YOUR_USERNAME/keystone.git
   git push gitlab main
   ```

   **Replace `YOUR_USERNAME` with your GitLab username**

## After Creating the Mirror

### Update Devpost Submission
Update `SUBMISSION/DEVPOST.md` line 6:

```
Repo: https://gitlab.com/YOUR_USERNAME/keystone
```

Also add a reference to GitHub:
```
GitHub mirror: https://github.com/vaibhav4046/keystone
```

## Important Notes

- The GitLab mirror must be public
- The repository should be MIT licensed (already is)
- Judges will check the GitLab URL in the Devpost submission
- Do this step **before** submitting to Devpost
- The GitLab mirror is a hard requirement for the hackathon

## Time Estimate

This should take about 5-10 minutes total.

## What If You Can't Create a GitLab Mirror?

Unfortunately, the GitLab mirror is a hard requirement for this hackathon. If you cannot create one:

1. Contact the hackathon organizers to request an exception
2. Consider using a GitHub Pages alternative if available
3. Ask for clarification on alternative submission methods

## Troubleshooting

**Error: "Repository already exists"**
- You may have already created the mirror. Check your GitLab profile.

**Error: "Permission denied"**
- Ensure your GitLab account has the necessary permissions
- Make sure the repository is public

**Error: "Authentication failed"**
- Check that your GITLAB_TOKEN is correct and not expired
- Ensure the token has the required scopes

## Verification

After creating the mirror, verify:
1. The GitLab repository is public
2. The MIT license is visible in the About section
3. The repository contains the same commits as GitHub

## Need Help?

If you encounter any issues, you can ask for help. The GitLab mirror is a critical component of your submission, so please take the time to set it up correctly.
