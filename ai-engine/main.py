import os
import re
import requests
import base64
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from groq import Groq
from typing import Optional

app = FastAPI(title="Minion SRE SaaS")

# --- 1. MODELS ---
class InvestigationRequest(BaseModel):
    error_log: str = Field(..., example="File 'app.py', line 15, in <module>...")
    repo_full_name: str = Field(..., example="username/repo-name")
    branch: Optional[str] = "main"

# --- 2. GITHUB SERVICE (USER-CENTRIC) ---
class GitHubService:
    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def fetch_context(self, repo: str, file_path: str):
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            return base64.b64decode(res.json()['content']).decode('utf-8')
        return "File content unavailable."

    def fetch_diff(self, repo: str):
        commits_url = f"https://api.github.com/repos/{repo}/commits"
        res = requests.get(commits_url, headers=self.headers)
        commits = res.json()
        if len(commits) < 2: return "No recent changes found."
        
        compare_url = f"https://api.github.com/repos/{repo}/compare/{commits[1]['sha']}...{commits[0]['sha']}"
        diff_data = requests.get(compare_url, headers=self.headers).json()
        return "\n".join([f"File: {f['filename']}\n{f.get('patch', '')}" for f in diff_data.get('files', [])])

    def create_pr(self, repo: str, file_path: str, new_content: str, fix_summary: str):
        # Professional Workflow: Create Branch -> Update File -> Create PR
        import time
        branch_name = f"minion-fix-{int(time.time())}"
        base_url = f"https://api.github.com/repos/{repo}"
        
        # 1. Get Main Branch SHA
        main_ref = requests.get(f"{base_url}/git/refs/heads/main", headers=self.headers).json()
        # 2. Create New Branch
        requests.post(f"{base_url}/git/refs", headers=self.headers, json={"ref": f"refs/heads/{branch_name}", "sha": main_ref['object']['sha']})
        # 3. Get File SHA for update
        file_meta = requests.get(f"{base_url}/contents/{file_path}", headers=self.headers).json()
        # 4. Update File
        requests.put(f"{base_url}/contents/{file_path}", headers=self.headers, json={
            "message": f"Minion Auto-Fix: {fix_summary}",
            "content": base64.b64encode(new_content.encode()).decode(),
            "sha": file_meta['sha'],
            "branch": branch_name
        })
        # 5. Open Pull Request
        pr_res = requests.post(f"{base_url}/pulls", headers=self.headers, json={
            "title": f"🛠️ Minion Fix: {fix_summary}",
            "head": branch_name,
            "base": "main",
            "body": f"I analyzed your logs and found the root cause. \n\n**Analysis:** {fix_summary}"
        })
        return pr_res.json().get("html_url")

# --- 3. LOG PARSER ---
def parse_error(log: str):
    pattern = r'File "([^"]+)", line (\d+)'
    match = re.search(pattern, log)
    return {"file": match.group(1), "line": match.group(2)} if match else None

# --- 4. SAAS ENDPOINT ---
@app.post("/api/v1/investigate-and-fix")
async def handle_incident(req: InvestigationRequest, x_github_token: str = Header(...)):
    gh = GitHubService(x_github_token)
    
    # Identify Issue
    loc = parse_error(req.error_log)
    if not loc: raise HTTPException(status_code=400, detail="Invalid log format")
    
    # Gather Intelligence
    diff = gh.fetch_diff(req.repo_full_name)
    code = gh.fetch_context(req.repo_full_name, loc['file'])

    # AI Reasoning (Groq)
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    prompt = f"System Context: Recent Changes:\n{diff}\n\nFile Content:\n{code}\n\nError Log:\n{req.error_log}\n\nReturn JSON: {{'analysis': '...', 'new_code': '...', 'summary': '...'}}"
    
    response = client.chat.completions.create(
        messages=[{"role": "system", "content": "You are an SRE bot. Output only valid JSON."}, 
                  {"role": "user", "content": prompt}],
        model="llama-3.3-70b-specdec",
        response_format={"type": "json_object"}
    )
    
    import json
    ai_data = json.loads(response.choices[0].message.content)
    
    # 5. Action: Automatic Pull Request
    pr_url = gh.create_pr(req.repo_full_name, loc['file'], ai_data['new_code'], ai_data['summary'])

    return {
        "status": "Incident Resolved",
        "root_cause": ai_data['analysis'],
        "pull_request": pr_url
    }