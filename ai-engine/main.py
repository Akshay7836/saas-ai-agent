import os
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from github import Github, Auth
from groq import Groq

app = FastAPI()

# 1. Configuration with safe defaults
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
# Render newline fix: standard procedure for private keys on PaaS
GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY", "").replace('\\n', '\n').strip()

client = Groq(api_key=GROQ_API_KEY)

class FixRequest(BaseModel):
    command: str
    error_log: str

class ApplyFixRequest(BaseModel):
    repo_name: str
    file_path: str
    fixed_code: str
    installation_id: int

@app.get("/")
def home():
    return {"status": "AI Engine is running"}

# 🚀 API 1: AI Analysis
@app.post("/fix-error")
async def fix_error(request: FixRequest):
    try:
        prompt = f"Analyze these files: {request.error_log}. Provide a short explanation of what's missing and how to improve it."
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        return {"explanation": chat_completion.choices[0].message.content}
    except Exception as e:
        print(f"❌ Groq Error: {repr(e)}")
        raise HTTPException(status_code=500, detail=f"AI Error: {repr(e)}")

# 🛠️ API 2: GitHub Commit Logic
@app.post("/apply-fix")
async def apply_fix(request: ApplyFixRequest):
    try:
        print(f"DEBUG: Starting fix for {request.repo_name} (ID: {request.installation_id})")
        
        # 1. Initialize App Auth
        app_auth = Auth.AppAuth(GITHUB_APP_ID, GITHUB_PRIVATE_KEY)
        
        # 2. Get Installation-specific Token
        # This is the most stable way to get a token for a specific user installation
        try:
            token = app_auth.get_installation_auth(request.installation_id)
            g = Github(auth=token)
            print("DEBUG: GitHub Installation Token acquired")
        except Exception as auth_err:
            print(f"❌ Auth Phase Error: {repr(auth_err)}")
            raise HTTPException(status_code=401, detail=f"GitHub Auth Failed: {repr(auth_err)}")

        # 3. Access Repository
        repo = g.get_repo(request.repo_name)
        
        # 4. Commit Changes
        try:
            # Check if file exists to update
            contents = repo.get_contents(request.file_path)
            repo.update_file(
                path=contents.path,
                message="AI Auto-Fix: Improvement applied",
                content=request.fixed_code,
                sha=contents.sha
            )
            return {"status": "success", "message": f"Successfully updated {request.file_path}"}
        except Exception:
            # If file doesn't exist, create it
            repo.create_file(
                path=request.file_path,
                message="AI Auto-Fix: File created",
                content=request.fixed_code
            )
            return {"status": "success", "message": f"Successfully created {request.file_path}"}

    except Exception as e:
        # Capture full traceback for Render logs
        error_trace = traceback.format_exc()
        print(f"❌ FULL ERROR LOG:\n{error_trace}")
        
        # Ensure detail is never empty/None to avoid frontend confusion
        error_msg = str(e) if str(e).strip() else repr(e)
        raise HTTPException(status_code=500, detail=f"GitHub Error: {error_msg}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)