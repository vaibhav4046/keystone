# Keystone GitLab Mirror Setup Script
# This script creates a GitLab mirror of your Keystone repository
# 
# Prerequisites:
# 1. GitLab personal access token (set as $env:GITLAB_TOKEN)
# 2. GitHub repository (already cloned locally)
# 3. Git installed on your system
# 
# Instructions:
# 1. Set your GitLab token: `$env:GITLAB_TOKEN="your_token_here"`
# 2. Run this script: `.` create-gitlab-mirror.ps1
# 
# The script will:
# - Clone your GitHub repo to a temporary location
# - Create a new repository on GitLab
# - Push your code to GitLab
# - Clean up the temporary directory
# 
# After running, update SUBMISSION/DEVPOST.md with the GitLab URL

param(
    [string]$GitHubRepo = "vaibhav4046/keystone",
    [string]$GitLabRepoName = "keystone",
    [string]$GitLabToken = $env:GITLAB_TOKEN
)

if (-not $GitLabToken) {
    Write-Error "ERROR: GITLAB_TOKEN environment variable is not set."
    Write-Host "Please set it with: `$env:GITLAB_TOKEN=your_token_here`"
    exit 1
}

# Check if git is available
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "ERROR: Git is not available on this system."
    exit 1
}

# Create temporary directory for cloning
$tempDir = New-TemporaryDirectory
$repoPath = Join-Path $tempDir $GitLabRepoName

Write-Host "Cloning GitHub repository: $GitHubRepo..."

# Clone the GitHub repository
$cloneResult = git clone $GitHubRepo $repoPath

if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: Failed to clone GitHub repository."
    Remove-Item -Recurse -Force $tempDir
    exit 1
}

Write-Host "GitHub repository cloned successfully."

# Create GitLab repository
Write-Host "Creating GitLab repository..."

$createApiUrl = "https://gitlab.com/api/v4/projects"
$createBody = @{ name = $GitLabRepoName; visibility = "public" }

$createHeaders = @{
    "Authorization" = "Bearer $GitLabToken"
    "Content-Type" = "application/json"
}

try {
    $createResponse = Invoke-WebRequest -Uri $createApiUrl -Method Post -Headers $createHeaders -Body ($createBody | ConvertTo-Json -Depth 4) -ErrorAction SilentlyContinue
    
    if ($createResponse.StatusCode -ne 201) {
        Write-Error "ERROR: Failed to create GitLab repository."
        Write-Error "Response: $($createResponse.Content)"
        Remove-Item -Recurse -Force $tempDir
        exit 1
    }
    
    $gitLabRepo = $createResponse.Content | ConvertFrom-Json
    $gitLabRepoUrl = $gitLabRepo.http_url_to_repo
    Write-Host "GitLab repository created at: $gitLabRepoUrl"
}

catch {
    Write-Error "ERROR: Failed to create GitLab repository."
    Write-Error $_.Exception.Message
    Remove-Item -Recurse -Force $tempDir
    exit 1
}

# Push to GitLab
Write-Host "Pushing repository to GitLab..."
$pushResult = git push --mirror $gitLabRepoUrl

if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: Failed to push to GitLab."
    Remove-Item -Recurse -Force $tempDir
    exit 1
}

Write-Host "SUCCESS: GitLab mirror created successfully!"
Write-Host "Repository URL: $gitLabRepoUrl"
Write-Host "Update SUBMISSION/DEVPOST.md with this URL."

# Clean up
Remove-Item -Recurse -Force $tempDir
Write-Host "Temporary files cleaned up."
