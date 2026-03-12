from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from groq import Groq
import os

app = FastAPI()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class RepoRequest(BaseModel):
    repo: str
    files: List[str]

class FixRequest(BaseModel):
    file_path: str
    original_code: str

@app.post("/analyze")
def analyze(req: RepoRequest):
    # Filter code files
    code_files = [f for f in req.files if f.endswith(('.py', '.js', '.ts', '.go'))]
    target = code_files[0] if code_files else "README.md"

    prompt = f"Analyze this filename: {target}. Why might this file need a DevOps/SRE review? Reply in JSON: {{'reason': '...', 'action': '...'}}"
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    import json
    ai_data = json.loads(response.choices[0].message.content)
    return {
        "target_file": target,
        "reason": ai_data.get("reason", "Code smells detected"),
        "action": ai_data.get("action", "Refactor")
    }

@app.post("/get-fix")
def get_fix(req: FixRequest):
    prompt = f"Fix the following code for file {req.file_path}. Improve performance and safety. Return ONLY the code in JSON field 'fixed_code'.\n\nCode:\n{req.original_code}"
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    import json
    return json.loads(response.choices[0].message.content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)