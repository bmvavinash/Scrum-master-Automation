# Agentic Repository Setup - Hackathon Repository

## ✅ Configuration Complete

The agentic workflow is now configured to use the **Hackathon repository** (`avinash1bmv/Hackathon`) instead of the Scrum Automation Backend repository.

## 🔒 Security Features

### 1. **Backend Repository Protection**
- ✅ Agentic operations **cannot** use the current backend repository
- ✅ Safety checks prevent accidental use of backend directory
- ✅ Clear error messages if backend repository is attempted

### 2. **Repository Verification**
- ✅ Repository must match configured owner/name from `.env`
- ✅ Mismatched repositories are automatically removed
- ✅ Case-insensitive matching for owner/name

### 3. **Dedicated Directory**
- ✅ All agentic repositories stored in: `app/repos/{owner}_{name}/`
- ✅ Separate from backend repository
- ✅ Automatic cleanup of mismatched repositories

## 📋 Current Configuration

From `.env` file:
```env
GITHUB_REPO_OWNER=avinash1bmv
GITHUB_REPO_NAME=Hackathon
GITHUB_TOKEN=ghp_...
GITHUB_BASE_BRANCH=main
```

**Repository Path:** `app/repos/avinash1bmv_Hackathon/`

## 🔄 Workflow Process

1. **Repository Setup**
   - Checks for existing repository at `app/repos/avinash1bmv_Hackathon/`
   - Verifies repository matches `avinash1bmv/Hackathon`
   - Removes mismatched repositories automatically
   - Clones fresh if repository doesn't exist or doesn't match

2. **Branch Creation**
   - Creates branch from `main` (or configured base branch)
   - Branch name format: `feature/{JIRA_KEY}` (e.g., `feature/SCRUM-38`)

3. **Code Generation**
   - Generates code using LLM (Bedrock/Cursor/Amazon Q)
   - Applies code to Hackathon repository
   - Validates syntax and runs linters

4. **Commit & Push**
   - Commits changes to Hackathon repository
   - Pushes branch to `avinash1bmv/Hackathon` remote
   - Creates PR if configured

## ✅ Verification

To verify the configuration:
```bash
python -c "from app.config import settings; print('Owner:', settings.github_repo_owner); print('Name:', settings.github_repo_name)"
```

Expected output:
```
Owner: avinash1bmv
Name: Hackathon
```

## 🚀 Testing

Test the agentic workflow:
```bash
python test_agentic_api_complete.py SCRUM-38
```

The workflow will:
1. ✅ Use `avinash1bmv/Hackathon` repository
2. ✅ Store in `app/repos/avinash1bmv_Hackathon/`
3. ✅ Create branch `feature/SCRUM-38`
4. ✅ Generate and apply code
5. ✅ Commit and push to Hackathon repository
6. ❌ **Never** use the backend repository

## 🔧 Troubleshooting

### Issue: Repository mismatch
**Solution:** The code automatically removes mismatched repositories and clones the correct one.

### Issue: Access denied errors
**Solution:** Stop all Python/Git processes and restart the server:
```powershell
Get-Process python,git | Stop-Process -Force
.\start_server.ps1
```

### Issue: Using wrong repository
**Solution:** Verify `.env` file has correct values:
- `GITHUB_REPO_OWNER=avinash1bmv`
- `GITHUB_REPO_NAME=Hackathon`
- Restart server after changes

## 📝 Summary

- ✅ **Repository:** `avinash1bmv/Hackathon`
- ✅ **Local Path:** `app/repos/avinash1bmv_Hackathon/`
- ✅ **Backend Protection:** Enabled (cannot use backend repo)
- ✅ **Repository Verification:** Enabled (must match owner/name)
- ✅ **Auto Cleanup:** Enabled (removes mismatched repos)

The agentic workflow is now fully configured to use the Hackathon repository!

