import os
import json
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from github import Github, GithubIntegration

app = FastAPI()

# CORS allow karna taaki Frontend/Node.js se connection ho sake
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clients Setup
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
APP_ID = os.environ.get("GITHUB_APP_ID")
PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY")

# --- AUTH LOGIC FOR GITHUB APP ---
def get_github_client(installation_id: int):
    # App ki private key se temporary access token lena
    integration = GithubIntegration(APP_ID, PRIVATE_KEY)
    access_token = integration.get_access_token(installation_id).token
    return Github(access_token)

# --- MODELS ---
class ErrorRequest(BaseModel):
    command: str
    error_log: str

class FixRequest(BaseModel):
    repo_name: str
    file_path: str
    fixed_code: str
    installation_id: int

# --- 1. SCAN/ANALYZE ENDPOINT (Aapka Purana Logic) ---
@app.post("/fix-error")
async def fix_error(request: ErrorRequest):
    prompt = f"Analyze these GitHub files: {request.error_log}. What is missing? Give a fix command in JSON with 'explanation' and 'fix_command' keys."
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)

# --- 2. AUTO-COMMIT ENDPOINT (Naya Logic) ---
@app.post("/apply-fix")
async def apply_fix(data: FixRequest):
    try:
        # User ki installation ID use karke GitHub client banana
        g = get_github_client(data.installation_id)
        repo = g.get_repo(data.repo_name)
        contents = repo.get_contents(data.file_path)

        # File ko update (commit) karna
        repo.update_file(
            path=data.file_path,
            message="🤖 AI Fix: Applied by DevOps-Pulse AI",
            content=data.fixed_code,
            sha=contents.sha
        )
        return {"status": "success", "message": f"Fixed {data.file_path} successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)