import os
import uvicorn
import json
import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from dotenv import load_dotenv

from rag.repo_indexer import index_repo, search_code

load_dotenv()

app = FastAPI()

# -----------------------------
# CORS Configuration
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# GROQ API Setup
# -----------------------------
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError("GROQ_API_KEY environment variable not set")

client = Groq(api_key=api_key)

# -----------------------------
# Analyze Repository
# -----------------------------
@app.post("/analyze-repo")
async def analyze_repo(request: Request):

    try:

        data = await request.json()
        files = data.get("files", [])

        if not files:
            return {
                "target_file": None,
                "reason": "No files received from repository",
                "action": "Check repository scanning step"
            }

        # Build vector database
        vectordb = index_repo(files)

        # Search relevant code snippets
        relevant_code = search_code(
            vectordb,
            "find missing implementation TODO incomplete function bug logic error"
        )

        prompt = f"""
You are a senior DevOps engineer reviewing repository code.

Analyze these code snippets and detect:

- bugs
- missing logic
- incomplete implementations
- bad practices

Code snippets:

{json.dumps(relevant_code, indent=2)}

Return JSON:

{{
"target_file":"file path",
"reason":"problem detected",
"action":"how to fix"
}}
"""

        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )

        response = chat.choices[0].message.content

        try:
            return json.loads(response)
        except Exception:
            return {
                "target_file": None,
                "reason": "AI returned invalid JSON",
                "action": response
            }

    except Exception:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="AI analysis failed")


# -----------------------------
# Apply Fix
# -----------------------------
@app.post("/apply-fix")
async def apply_fix(request: Request):

    try:

        data = await request.json()

        file_path = data.get("file_path")
        original_code = data.get("original_code", "")

        prompt = f"""
Fix issues in this file.

File: {file_path}

Code:
{original_code}

Return JSON:

{{"fixed_code":"corrected code"}}
"""

        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )

        response = chat.choices[0].message.content

        try:
            return json.loads(response)
        except Exception:
            return {
                "fixed_code": response
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Pull Request Review
# -----------------------------
@app.post("/review-pr")
async def review_pr(request: Request):

    try:

        data = await request.json()
        diff = data.get("diff", "")

        if not diff:
            return {
                "review_comment": "No diff provided",
                "severity": "low"
            }

        prompt = f"""
You are a senior software engineer reviewing a Pull Request.

Review the following Git diff and detect:

- bugs
- security issues
- performance problems
- bad practices

Diff:

{diff}

Return JSON:

{{
"review_comment":"review feedback",
"severity":"low | medium | high"
}}
"""

        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )

        response = chat.choices[0].message.content

        try:
            return json.loads(response)
        except Exception:
            return {
                "review_comment": response,
                "severity": "unknown"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Run FastAPI Server
# -----------------------------
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )