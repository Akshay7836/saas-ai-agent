# import os
# import traceback
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from groq import Groq

# app = FastAPI()

# # Configuration
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# client = Groq(api_key=GROQ_API_KEY)

# class FixRequest(BaseModel):
#     command: str
#     error_log: str

# class ApplyFixRequest(BaseModel):
#     repo_name: str
#     file_path: str
#     installation_id: int
#     # Note: 'fixed_code' ab request se nahi, AI se aayega

# @app.get("/")
# def home():
#     return {"status": "AI Engine is running"}

# # 🚀 API 1: AI Analysis (Same logic)
# @app.post("/fix-error")
# async def fix_error(request: FixRequest):
#     try:
#         prompt = f"Analyze these files: {request.error_log}. Provide a short explanation of what's missing and how to improve it."
#         chat_completion = client.chat.completions.create(
#             messages=[{"role": "user", "content": prompt}],
#             model="llama-3.3-70b-versatile",
#         )
#         return {"explanation": chat_completion.choices[0].message.content}
#     except Exception as e:
#         print(f"❌ Groq Error: {repr(e)}")
#         raise HTTPException(status_code=500, detail=f"AI Error: {repr(e)}")

# # 🛠️ API 2: NEW Logic - Generate Code only
# @app.post("/apply-fix")
# async def apply_fix(request: ApplyFixRequest):
#     try:
#         print(f"🤖 Generating fix for {request.file_path}...")
        
#         # Humein ab AI se actual code mangwana hai
#         prompt = f"""
#         Task: Fix or Optimize the code for the file: {request.file_path}.
#         Context: The user wants to improve logical handling and code quality.
#         Requirement: Return ONLY the code. No markdown, no explanations.
#         """
        
#         chat_completion = client.chat.completions.create(
#             messages=[{"role": "user", "content": prompt}],
#             model="llama-3.3-70b-versatile",
#         )
        
#         fixed_code = chat_completion.choices[0].message.content
        
#         # Cleaner code extraction (Removing ``` if AI includes them)
#         if "```" in fixed_code:
#             fixed_code = fixed_code.split("```")[1]
#             if fixed_code.startswith("python") or fixed_code.startswith("javascript"):
#                 fixed_code = "\n".join(fixed_code.split("\n")[1:])

#         # Commit ka kaam ab server.js karega, hum sirf code bhej rahe hain
#         return {
#             "status": "success",
#             "fixed_code": fixed_code.strip(),
#             "explanation": "AI generated code successfully"
#         }

#     except Exception as e:
#         error_trace = traceback.format_exc()
#         print(f"❌ AI GENERATION ERROR:\n{error_trace}")
#         raise HTTPException(status_code=500, detail=f"AI Engine Error: {str(e)}")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=10000)



import os
import traceback
import json
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from groq import Groq

app = FastAPI()

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

class AnalyzeRequest(BaseModel):
    files_context: str

class ApplyFixRequest(BaseModel):
    repo_name: str
    file_path: str
    installation_id: int
    original_code: str = ""  # New: Hum ab original code bhejenge server.js se

@app.get("/")
def home():
    return {"status": "AI Agent Engine is running"}

# 🚀 API 1: Analyze & Detect Bug (The Detective)
@app.post("/analyze-repo")
async def analyze_repo(request: AnalyzeRequest):
    try:
        prompt = f"""
        You are a Senior Software Architect. Scan this list of files in a repository:
        {request.files_context}

        Task: Identify ONE critical file that needs improvement, bug fixing, or optimization.
        Return ONLY a JSON response (no markdown, no text):
        {{
            "target_file": "path/to/file.js",
            "reason": "Explain why this file needs attention",
            "action": "What improvement should be made"
        }}
        """
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"} # Groq supports JSON mode
        )
        
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ Analysis Error: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 🛠️ API 2: Dynamic Code Generation (The Mechanic)
@app.post("/apply-fix")
async def apply_fix(request: ApplyFixRequest):
    try:
        print(f"🤖 Fixing: {request.file_path}...")
        
        prompt = f"""
        File: {request.file_path}
        Original Code:
        {request.original_code}

        Task: Improve this code. Fix bugs, add error handling, or optimize logic.
        Requirement: Return ONLY the code. No markdown code blocks (```), no explanations.
        """
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        
        fixed_code = chat_completion.choices[0].message.content

        # Cleaner code extraction logic
        if "```" in fixed_code:
            parts = fixed_code.split("```")
            # Usually the code is in the second part if the AI uses blocks
            fixed_code = parts[1]
            if "\n" in fixed_code:
                # Remove the language name (e.g., 'javascript') if it exists
                first_line = fixed_code.split("\n")[0].strip().lower()
                if first_line in ["javascript", "python", "node", "js", "py"]:
                    fixed_code = "\n".join(fixed_code.split("\n")[1:])

        return {
            "status": "success",
            "fixed_code": fixed_code.strip(),
            "summary": f"AI optimized {request.file_path} for better stability."
        }

    except Exception as e:
        print(f"❌ AI Fix Error: {repr(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)