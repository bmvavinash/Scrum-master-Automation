# Bedrock Troubleshooting Guide

## ✅ What's Working

1. **Bedrock Authentication**: AWS credentials are properly configured
2. **Test Script**: `verify_bedrock.py` shows Bedrock is working correctly
3. **Code Improvements**: Enhanced logging and JSON extraction added

## ❌ Current Issue

The agentic API is still using the `fallback` provider instead of `bedrock`.

## 🔍 Root Cause

The server needs to be **fully restarted** to pick up all code changes. The `--reload` flag may not reload all modules properly.

## 🛠️ Solution

### Step 1: Fully Stop the Server
```powershell
# In the terminal where the server is running:
# Press Ctrl+C to stop it
# Or kill the process:
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*scrum_automation_env*" } | Stop-Process -Force
```

### Step 2: Restart the Server
```powershell
.\scrum_automation_env\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Step 3: Check Server Logs

When the server starts, you should see:
```
INFO - Bedrock client initialized with AWS credentials
```

If you see:
```
WARNING - Bedrock credentials not configured
```
Then there's a configuration issue.

### Step 4: Test Bedrock Directly

Run the verification script:
```powershell
$env:PYTHONIOENCODING='utf-8'
.\scrum_automation_env\Scripts\python.exe verify_bedrock.py
```

This should show:
```
✅ ALL TESTS PASSED! Bedrock is working correctly.
```

### Step 5: Test Agentic API

After server restart, test the agentic API:
```powershell
python -c "import requests, json; r = requests.post('http://127.0.0.1:8000/api/v1/agentic/process', json={'jira_key': 'SCRUM-38', 'config': {'generate_tests': False}}, timeout=120); d = r.json(); print('Provider:', d['steps']['code_generation'].get('provider'))"
```

Expected output:
```
Provider: bedrock
```

## 📋 Enhanced Logging

The code now includes detailed logging. When you run the agentic API, check the server logs for:

1. **Bedrock Initialization**:
   - `INFO - Bedrock client initialized with AWS credentials` ✅
   - `WARNING - Bedrock credentials not configured` ❌

2. **Code Generation**:
   - `INFO - Attempting code generation with bedrock`
   - `INFO - Using Bedrock for code generation`
   - `INFO - Invoking Bedrock API...`
   - `INFO - Bedrock returned response (length: X)`

3. **Response Parsing**:
   - `INFO - Successfully extracted JSON block` ✅
   - `WARNING - Failed to parse LLM response as JSON` ❌
   - `WARNING - LLM raw response (first 2000 chars): ...` (shows what Bedrock returned)

## 🔧 If Still Using Fallback

If the server is restarted but still using fallback, check the server logs for:

1. **Does Bedrock initialize?**
   - Look for "Bedrock client initialized" message

2. **Is Bedrock being called?**
   - Look for "Attempting code generation with bedrock" message
   - Look for "Invoking Bedrock API..." message

3. **What does Bedrock return?**
   - Look for "Bedrock returned response" message
   - Look for "LLM raw response" message (this shows what Bedrock actually returned)

4. **Why does parsing fail?**
   - Look for "Failed to parse LLM response" message
   - The response content will show what Bedrock returned vs what we expected

## 📝 Configuration Checklist

Ensure these are set in `.env`:

```env
# AWS Credentials (REQUIRED for Bedrock)
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1

# Bedrock Model
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Provider Priority
LLM_PROVIDER_PRIORITY=bedrock,cursor,amazon_q
```

## 💡 Common Issues

1. **"Bedrock credentials not configured"**
   - Check that `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set
   - Ensure no extra spaces or line breaks in `.env` file

2. **"Bedrock returned empty response"**
   - Check AWS account has Bedrock access enabled
   - Verify model ID is correct
   - Check AWS credentials have Bedrock permissions

3. **"Failed to parse LLM response"**
   - Bedrock is responding, but format is unexpected
   - Check server logs for actual response content
   - JSON extraction has been improved, but may need further tuning

4. **"All LLM providers failed"**
   - Bedrock client not initialized
   - All providers are failing
   - Check server logs for specific error messages

## 🎯 Next Steps

1. **Restart the server fully** (not just reload)
2. **Check server logs** for initialization messages
3. **Run verification script** to confirm Bedrock works
4. **Test agentic API** and check logs for detailed output
5. **If still failing**, check logs for actual Bedrock response content


