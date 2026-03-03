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
        # 1. App Authentication
        auth = Auth.AppAuth(GITHUB_APP_ID, GITHUB_PRIVATE_KEY)
        
        # 2. Get GitHub instance for this SPECIFIC installation
        # Purana 'get_installations()[0]' wala method hata kar ye use karein
        g = Github(auth=auth.get_installation_auth(request.installation_id))
        
        repo = g.get_repo(request.repo_name)
        
        try:
            # Update existing file
            contents = repo.get_contents(request.file_path)
            repo.update_file(contents.path, "AI Auto-Fix: Updated file", request.fixed_code, contents.sha)
            msg = f"Updated {request.file_path} successfully!"
        except Exception:
            # Create new file if not exists
            repo.create_file(request.file_path, "AI Auto-Fix: Created file", request.fixed_code)
            msg = f"Created {request.file_path} successfully!"
            
        return {"status": "success", "message": msg}
    except Exception as e:
        print(f"❌ Actual Commit Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GitHub Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)