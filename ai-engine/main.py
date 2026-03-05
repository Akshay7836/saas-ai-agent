import os
import json
import traceback
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from groq import Groq

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 🚀 API 1: Deep Repo Analysis
@app.post("/analyze-repo")
async def analyze_repo(request: Request):
    try:
        data = await request.json()
        file_list = data.get("files_context", "")

        if not file_list:
            return {
                "target_file": "index.js",
                "reason": "Repository is empty or missing core files.",
                "action": "Initialize repository with basic structure"
            }

        prompt = f"""
        Analyze this repository file tree:
        {file_list}

        Task: Act as an Autonomous DevOps Agent. Identify ONE file that is either missing, 
        has logical bugs, or needs performance optimization.
        Return ONLY a JSON object:
        {{
            "target_file": "path/to/file.js",
            "reason": "Technical reason for selection",
            "action": "What exact fix will be applied"
        }}
        """
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        print(f"Analysis Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="AI Analysis Failed")

# 🛠️ API 2: Full Code Reconstruction (Zero-Error Fix)
@app.post("/apply-fix")
async def apply_fix(request: Request):
    try:
        data = await request.json()
        file_path = data.get("file_path")
        original_code = data.get("original_code", "")

        # Edge Case: If file is empty or deleted
        context = "This file is currently EMPTY or DELETED. Create it from scratch." if not original_code else f"Current Code:\n{original_code}"

        prompt = f"""
        Task: Reconstruct the file '{file_path}' to be production-ready and bug-free.
        {context}
        
        Requirements:
        1. Fix all syntax and logical errors.
        2. Add professional error handling.
        3. Return ONLY the code. No markdown blocks, no talk.
        """
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile"
        )
        fixed_code = chat.choices[0].message.content.strip()

        # Clean any accidental markdown
        if "```" in fixed_code:
            fixed_code = fixed_code.split("```")[1]
            if "\n" in fixed_code:
                fixed_code = "\n".join(fixed_code.split("\n")[1:])

        return {
            "fixed_code": fixed_code,
            "summary": f"Successfully healed {file_path}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fix-error")
async def fix_error(): return {"explanation": "Agent Online"}