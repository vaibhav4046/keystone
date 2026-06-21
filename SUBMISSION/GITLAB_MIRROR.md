# GitLab Mirror Setup (REQUIRED for submission)

The Devpost rules require: "Link to your provisioned open source (MIT Licensed) **GitLab project**"

Your repo is currently on GitHub only. You MUST create a GitLab mirror before submitting.

## Option 1: Create a GitLab mirror (recommended, 5 minutes)

1. **Sign up / log in to GitLab**: https://gitlab.com/users/sign_up (free account is fine)

2. **Create a new project**:
   - Click the "+" icon → "New project"
   - Choose "Create blank project"
   - Name: `keystone`
   - Visibility: **Public**
   - DO NOT initialize with README (we'll push from GitHub)
   - Click "Create project"

3. **Add GitLab as a remote and push**:
   ```bash
   cd D:\project\keystone
   git remote add gitlab https://gitlab.com/YOUR_USERNAME/keystone.git
   git push gitlab main
   ```

4. **Verify**:
   - Go to https://gitlab.com/YOUR_USERNAME/keystone
   - Confirm the repo is public and the MIT license is visible in the About section
   - Copy the URL - this is what you'll paste into Devpost

## Option 2: Use GitLab's import feature (if you have a GitLab account)

1. Go to https://gitlab.com/projects/new#import-project
2. Choose "GitHub"
3. Authorize GitLab to access your GitHub account
4. Select `vaibhav4046/keystone`
5. Click "Import"

This creates a mirror that stays in sync with GitHub.

## After creating the mirror

Update SUBMISSION/DEVPOST.md line 6:
```
Repo: https://gitlab.com/YOUR_USERNAME/keystone
```

And add the GitHub link as a secondary reference:
```
GitHub mirror: https://github.com/vaibhav4046/keystone
```

## Why this matters

The judges are GitLab engineers. They will:
- Check that the repo is on GitLab (not just GitHub)
- Verify the MIT license is visible
- Test the code by cloning from GitLab
- Check the commit history for activity during the submission window

A GitHub-only submission risks disqualification or a lower score on "Does the artifact work as described?" because the judges may not test it.

## Estimated time: 5-10 minutes

This is a hard requirement. Do not skip it.
