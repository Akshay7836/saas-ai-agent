import os
import json
import traceback
from fastapi import FastAPI,HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from dotenv import load_dotenv

from rag.repo_indexer import index_repo, search_code

load_dotenv()

app=FastAPI()

app.add_middleware(
CORSMiddleware,
allow_origins=["*"],
allow_methods=["*"],
allow_headers=["*"]
)

client=Groq(api_key=os.getenv("GROQ_API_KEY"))

@app.post("/analyze-repo")
async def analyze_repo(request:Request):

    try:

        data=await request.json()

        files=data.get("files",[])

        vectordb=index_repo(files)

        relevant_code=search_code(
            vectordb,
            "bug missing code bad practice incomplete function"
        )

        prompt=f"""
You are a senior DevOps engineer reviewing a repository.

Analyze these code snippets retrieved from the repository.

Detect:

- bugs
- missing code
- incomplete implementations
- bad practices

Code:

{json.dumps(relevant_code,indent=2)}

Return JSON:

{{
"target_file":"file path",
"reason":"problem detected",
"action":"fix description"
}}
"""

        chat=client.chat.completions.create(

            messages=[{"role":"user","content":prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type":"json_object"}

        )

        return json.loads(chat.choices[0].message.content)

    except Exception:

        print(traceback.format_exc())

        raise HTTPException(status_code=500,detail="AI analysis failed")

@app.post("/apply-fix")
async def apply_fix(request:Request):

    try:

        data=await request.json()

        file_path=data.get("file_path")

        original_code=data.get("original_code","")

        prompt=f"""
Fix issues in this file.

File: {file_path}

Code:
{original_code}

Return JSON:

{{"fixed_code":"corrected code"}}
"""

        chat=client.chat.completions.create(

            messages=[{"role":"user","content":prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type":"json_object"}

        )

        return json.loads(chat.choices[0].message.content)

    except Exception as e:

        raise HTTPException(status_code=500,detail=str(e))

if __name__=="__main__":

    import uvicorn

    uvicorn.run(app,host="0.0.0.0",port=8000)