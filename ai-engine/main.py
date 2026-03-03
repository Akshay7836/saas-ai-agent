import os
import json
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from github import Github, GithubIntegration

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
APP_ID = os.environ.get("GITHUB_APP_ID")
PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY")

def get_github_client(installation_id: int):
    # Private key se token generate karna
    integration = GithubIntegration(APP_ID, PRIVATE_KEY)
    access_token = integration.get_access_token(installation_id).token
    return Github(access_token)

class ErrorRequest(BaseModel):
    command: str
    error_log: str

class FixRequest(BaseModel):
    repo_name: str
    file_path: str
    fixed_code: str
    installation_id: int

@app.post("/fix-error")
async def fix_error(request: ErrorRequest):
    prompt = f"Analyze these GitHub files: {request.error_log}. What is missing? Give a fix command in JSON with 'explanation' and 'fix_command' keys. If a file is missing, provide only the file content in 'fix_command'."
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)

@app.post("/apply-fix")
async def apply_fix(data: FixRequest):
    try:
        g = get_github_client(data.installation_id)
        repo = g.get_repo(data.repo_name)
        
        # AI kabhi-kabhi "touch README.md" bhejta hai, use saaf karna
        clean_code = data.fixed_code.replace("touch README.md", "").strip()

        try:
            # 1. Check if file exists to UPDATE
            contents = repo.get_contents(data.file_path)
            repo.update_file(
                path=data.file_path,
                message="🤖 AI Fix: Updated by DevOps AI",
                content=clean_code,
                sha=contents.sha
            )
            return {"status": "success", "message": f"Updated {data.file_path} successfully!"}
            
        except Exception:
            # 2. If file not found (404), CREATE it
            repo.create_file(
                path=data.file_path,
                message="🤖 AI Fix: Created missing file",
                content=clean_code,
                branch="main" 
            )
            return {"status": "success", "message": f"Created {data.file_path} successfully!"}
            
    except Exception as e:
        # Pura error message return karna debugging ke liye
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)