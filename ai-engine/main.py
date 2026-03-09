import os
import json
import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# CORS Fix for local and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.post("/analyze-repo")
async def analyze_repo(request: Request):
    try:
        data = await request.json()
        file_list = data.get("files_context", "")
        if not file_list:
            return {"target_file": "index.js", "reason": "Empty Repo", "action": "Initialize"}

        prompt = f"Analyze these files: {file_list}. Pick ONE file to fix/optimize. Return ONLY JSON: {{\"target_file\": \"path/to/file\", \"reason\": \"why\", \"action\": \"what\"}}"
        
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(chat.choices[0].message.content)
    except Exception:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="AI Analysis Failed")

@app.post("/apply-fix")
async def apply_fix(request: Request):
    try:
        data = await request.json()
        file_path = data.get("file_path")
        original_code = data.get("original_code", "")

        prompt = f"Fix this file: {file_path}\nCode:\n{original_code}\nReturn ONLY JSON with key 'fixed_code'."
        
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)