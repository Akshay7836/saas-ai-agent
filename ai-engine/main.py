import os, json, uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from github import Github, GithubIntegration

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Clients Setup with Safety Checks
GROQ_KEY = os.environ.get("GROQ_API_KEY")
APP_ID = os.environ.get("GITHUB_APP_ID")
RAW_PRIVATE_KEY = os.environ.get("GITHUB_PRIVATE_KEY")

if not all([GROQ_KEY, APP_ID, RAW_PRIVATE_KEY]):
    print("❌ Critical Error: Environment Variables missing!")

client = Groq(api_key=GROQ_KEY)

def get_github_client(installation_id: int):
    try:
        # Handle key format for Render/Linux environment
        formatted_key = RAW_PRIVATE_KEY.replace('\\n', '\n').strip()
        if "-----BEGIN" not in formatted_key:
            formatted_key = f"-----BEGIN RSA PRIVATE KEY-----\n{formatted_key}\n-----END RSA PRIVATE KEY-----"
            
        integration = GithubIntegration(APP_ID, formatted_key)
        access_token = integration.get_access_token(installation_id).token
        return Github(access_token)
    except Exception as e:
        print(f"Auth Error: {str(e)}")
        return None

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
    try:
        prompt = f"Analyze these files: {request.error_log}. Suggest missing files or fixes. Output ONLY JSON with 'explanation' and 'fix_command' keys."
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(e)}")

@app.post("/apply-fix")
async def apply_fix(data: FixRequest):
    g = get_github_client(data.installation_id)
    if not g:
        raise HTTPException(status_code=401, detail="GitHub App Auth Failed. Check Private Key.")

    try:
        repo = g.get_repo(data.repo_name)
        # AI commands clean-up logic
        clean_code = data.fixed_code.replace("touch ", "").replace("README.md", "").strip() if "touch" in data.fixed_code else data.fixed_code

        try:
            # Update existing file
            contents = repo.get_contents(data.file_path)
            repo.update_file(path=data.file_path, message="🤖 DevOpsAI Fix", content=clean_code, sha=contents.sha)
            return {"status": "success", "message": f"Successfully updated {data.file_path}"}
        except:
            # Create new file
            repo.create_file(path=data.file_path, message="🤖 DevOpsAI Initialization", content=clean_code)
            return {"status": "success", "message": f"Successfully created {data.file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))