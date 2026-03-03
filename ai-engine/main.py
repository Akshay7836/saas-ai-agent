import os, json, uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from github import Github, GithubIntegration

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
APP_ID = os.environ.get("GITHUB_APP_ID")
PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY").replace('\\n', '\n') # Key format fix

def get_github_client(installation_id: int):
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
    prompt = f"Analyze files: {request.error_log}. Provide a JSON with 'explanation' and 'fix_command'. If a file like README.md is missing, suggest its content in 'fix_command'."
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
        # AI commands like 'touch' ko clean karna
        clean_code = data.fixed_code.replace("touch README.md", "").strip()

        try:
            # Step 1: Update existing file
            contents = repo.get_contents(data.file_path)
            repo.update_file(path=data.file_path, message="🤖 AI Update", content=clean_code, sha=contents.sha)
            return {"status": "success", "message": f"Updated {data.file_path}"}
        except:
            # Step 2: Create if missing
            repo.create_file(path=data.file_path, message="🤖 AI Create", content=clean_code)
            return {"status": "success", "message": f"Created {data.file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))