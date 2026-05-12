# AgnoHire GitHub Upload Script
# This script will upload the AgnoHire project to GitHub

Write-Host "🚀 AgnoHire GitHub Upload Script" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green

# Check if git is installed
try {
    git --version
} catch {
    Write-Host "❌ Git is not installed. Please install Git first." -ForegroundColor Red
    Write-Host "Download from: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Navigate to project directory
$projectPath = Get-Location
Write-Host "📁 Project Directory: $projectPath" -ForegroundColor Blue

# Check if this is a git repository
if (-not (Test-Path ".git")) {
    Write-Host "🔧 Initializing Git repository..." -ForegroundColor Yellow
    
    # Initialize git repository
    git init
    
    # Create .gitignore file
    $gitignoreContent = @"
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
venv/
env/
ENV/
.venv/

# Environment variables
.env
.env.local
.env.production

# Database
*.db
*.sqlite3
.data/

# Logs
*.log
logs/

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.temp
.cache/

# Audio/Video recordings
*.webm
*.wav
*.mp3
*.mp4

# Test files
test_*.py
*_test.py
tests/
"@
    
    Set-Content -Path ".gitignore" -Value $gitignoreContent -Encoding UTF8
    Write-Host "✅ .gitignore file created" -ForegroundColor Green
} else {
    Write-Host "✅ Git repository already exists" -ForegroundColor Green
}

# Add all files to git
Write-Host "📦 Adding all files to Git..." -ForegroundColor Yellow
git add .

# Check git status
Write-Host "📋 Git Status:" -ForegroundColor Blue
git status --porcelain

# Create initial commit
Write-Host "🎯 Creating initial commit..." -ForegroundColor Yellow
$commitMessage = "🎯 Initial commit: AgnoHire AI Interview System

🚀 Features:
- Voice Interview System with Whisper STT
- AI Proctoring with Face/Object Detection
- Real-time Speech Recognition and TTS
- AI-powered Answer Evaluation
- PDF Report Generation
- Multi-interview Modes (Domain/Resume/Company)

🏗️ Architecture:
- Frontend: HTML5/CSS3/JavaScript with WebRTC
- Backend: Flask + FastAPI + MongoDB
- AI Services: Whisper + Computer Vision
- Proctoring: Real-time monitoring and alerts

📚 Complete documentation and setup guide included."

git commit -m $commitMessage

# Check if remote exists
$remoteExists = git remote get-url origin 2>$null
if (-not $remoteExists) {
    Write-Host "🔗 Adding GitHub remote..." -ForegroundColor Yellow
    
    # Add GitHub remote
    $githubUrl = "https://github.com/abinayac24/AgnoHire-.git"
    git remote add origin $githubUrl
    
    Write-Host "✅ GitHub remote added: $githubUrl" -ForegroundColor Green
} else {
    Write-Host "✅ GitHub remote already exists" -ForegroundColor Green
    Write-Host "🔗 Remote URL: $remoteExists" -ForegroundColor Blue
}

# Push to GitHub
Write-Host "📤 Pushing to GitHub..." -ForegroundColor Yellow

# Set main branch if needed
$currentBranch = git branch --show-current
if ($currentBranch -ne "main") {
    git branch -M main
    Write-Host "🔄 Renamed branch to 'main'" -ForegroundColor Blue
}

# Push to GitHub
try {
    git push -u origin main
    Write-Host "✅ Successfully pushed to GitHub!" -ForegroundColor Green
    Write-Host "🌐 Repository URL: https://github.com/abinayac24/AgnoHire-" -ForegroundColor Blue
} catch {
    Write-Host "❌ Push failed. Please check your GitHub credentials." -ForegroundColor Red
    Write-Host "💡 You may need to:" -ForegroundColor Yellow
    Write-Host "   1. Set up GitHub Personal Access Token" -ForegroundColor Yellow
    Write-Host "   2. Configure git credentials" -ForegroundColor Yellow
    Write-Host "   3. Try manual push: git push -u origin main" -ForegroundColor Yellow
}

Write-Host "======================================" -ForegroundColor Green
Write-Host "🎯 AgnoHire GitHub Upload Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
