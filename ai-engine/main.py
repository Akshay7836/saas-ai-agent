from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from groq import Groq
import os
import json

app = FastAPI()

# Check for API Key
GROQ_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY)

class RepoRequest(BaseModel):
    repo: str
    files: List[str]

class FixRequest(BaseModel):
    file_path: str
    original_code: str

@app.post("/analyze")
def analyze(req: RepoRequest):
    # DevOps relevant files filter karein
    code_files = [f for f in req.files if f.endswith(('.py', '.js', '.ts', '.go', '.yml', '.yaml', 'Dockerfile'))]
    target = code_files[0] if code_files else "README.md"

    # AI ko context de rahe hain ki wo kyun analyze kar raha hai
    prompt = (
        f"Analyze the file '{target}' for SRE/DevOps best practices, security, and performance. "
        f"Identify one major improvement. Reply ONLY in JSON format: "
        f"{{\"reason\": \"short explanation\", \"action\": \"what to fix\"}}"
    )
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a world-class SRE Engineer. Output only JSON."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    ai_data = json.loads(response.choices[0].message.content)
    return {
        "target_file": target,
        "reason": ai_data.get("reason", "Potential performance bottleneck detected."),
        "action": ai_data.get("action", "Optimize code structure")
    }

@app.post("/get-fix")
def get_fix(req: FixRequest):
    # ⚠️ CRITICAL: Strict prompt to return FULL code, not just snippets
    prompt = (
        f"Fix the following code for file '{req.file_path}'. "
        "Instructions: Fix all bugs, improve performance, and ensure it follows SRE best practices. "
        "IMPORTANT: Return the FULL corrected file content. Do not skip any part of the code. "
        "Return ONLY a JSON object with a single key 'fixed_code' containing the string of the new code."
        f"\n\nOriginal Code:\n{req.original_code}"
    )
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a code-generator. You return the full source code for a file without any markdown or explanation."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    # AI se aane wala JSON parse karein
    fix_data = json.loads(response.choices[0].message.content)
    
    # Safety Check: Agar AI ne galat key di ho toh handle karein
    if "fixed_code" not in fix_data:
        return {"fixed_code": req.original_code}
        
    return fix_data

if __name__ == "__main__":
    import uvicorn
    # Render usually provides the PORT env var
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)