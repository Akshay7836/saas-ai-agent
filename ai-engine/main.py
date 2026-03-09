import os
import json
import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq

app = FastAPI()

# CORS Enable taaki Node.js se baat ho sake
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.post("/analyze-repo")
async def analyze_repo(request: Request):
    try:
        data = await request.json()
        file_list = data.get("files_context", "")

        if not file_list:
            return {"target_file": "index.js", "reason": "Repo empty", "action": "Init project"}

        prompt = f"Analyze these files: {file_list}. Identify ONE file needing a fix. Return ONLY JSON: {{\"target_file\": \"...\", \"reason\": \"...\", \"action\": \"...\"}}"
        
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-specdec", # Professional stable model
            response_format={"type": "json_object"}
        )
        return json.loads(chat.choices[0].message.content)
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Analysis Failed")

@app.post("/apply-fix")
async def apply_fix(request: Request):
    try:
        data = await request.json()
        file_path = data.get("file_path")
        original_code = data.get("original_code", "")

        context = "File is empty. Create it." if not original_code else f"Code:\n{original_code}"
        
        # Strict JSON request for the code itself
        prompt = f"Fix {file_path}. {context}. Return ONLY a JSON object with key 'fixed_code' containing the full corrected code string."
        
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-specdec",
            response_format={"type": "json_object"}
        )
        
        res = json.loads(chat.choices[0].message.content)
        return {"fixed_code": res['fixed_code'], "summary": f"Healed {file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)