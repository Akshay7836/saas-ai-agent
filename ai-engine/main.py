from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from groq import Groq
import os
import json

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
    # Filter for DevOps/Config files first
    priority_files = [f for f in req.files if f.endswith(('.yml', '.yaml', 'Dockerfile', '.py', '.js'))]
    target = priority_files[0] if priority_files else req.files[0]

    prompt = (
        f"Analyze '{target}' for SRE/DevOps best practices. "
        "Identify one critical improvement. Output ONLY JSON: "
        "{\"target_file\": \"...\", \"reason\": \"...\", \"action\": \"...\"}"
    )
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": "You are a world-class SRE. Output only JSON."},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

@app.post("/get-fix")
def get_fix(req: FixRequest):
    prompt = (
        f"Fix the file '{req.file_path}'. Improve performance and safety. "
        "Return the ENTIRE source code corrected. "
        "Return ONLY a JSON object with the key 'fixed_code'."
        f"\n\nOriginal Code:\n{req.original_code}"
    )
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": "You are a code-generator. Output only JSON."},
                  {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)