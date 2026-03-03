import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from github import Github, Auth  # Sahi imports
from groq import Groq

app = FastAPI()

# 1. Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
# Render newline fix
GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY", "").replace('\\n', '\n')

client = Groq(api_key=GROQ_API_KEY)

class FixRequest(BaseModel):
    command: str
    error_log: str

class ApplyFixRequest(BaseModel):
    repo_name: str
    file_path: str
    fixed_code: str
    installation_id: int

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
        raise HTTPException(status_code=500, detail=str(e))

# 🛠️ API 2: GitHub Commit Logic (The Corrected Version)
@app.post("/apply-fix")
async def apply_fix(request: ApplyFixRequest):
    try:
        print(f"DEBUG: Attempting fix for {request.repo_name}")
        print(f"DEBUG: Installation ID: {request.installation_id}")
        
        # 1. Auth Check
        auth = Auth.AppAuth(GITHUB_APP_ID, GITHUB_PRIVATE_KEY)
        
        # 2. Token Check
        try:
            installation_auth = auth.get_installation_auth(request.installation_id)
            g = Github(auth=installation_auth)
            print("DEBUG: Auth Token generated successfully")
        except Exception as auth_err:
            print(f"❌ Auth Phase Error: {str(auth_err)}")
            raise HTTPException(status_code=401, detail=f"Auth Failed: {str(auth_err)}")

        # 3. Repo Access Check
        repo = g.get_repo(request.repo_name)
        print(f"DEBUG: Repo {repo.full_name} accessed")
        
        # 4. Commit Logic
        try:
            contents = repo.get_contents(request.file_path)
            repo.update_file(contents.path, "AI Auto-Fix", request.fixed_code, contents.sha)
            return {"status": "success", "message": "Updated successfully!"}
        except Exception as commit_err:
            # Agar file nahi milti toh create karega
            repo.create_file(request.file_path, "AI Auto-Fix", request.fixed_code)
            return {"status": "success", "message": "Created successfully!"}

    except Exception as e:
        # Ye line ab 'None' ki jagah pura error degi
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ FULL ERROR LOG:\n{error_details}")
        raise HTTPException(status_code=500, detail=f"GitHub Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)