const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const app = express();

// Octokit ko bina auth ke initialize kar rahe hain kyunki private operations Python Engine karega
const octokit = new Octokit();

app.use(express.json());

// 1. Static Files Setup: Taaki index.html sahi se load ho
app.use(express.static(path.join(__dirname))); 

const PYTHON_URL = process.env.PYTHON_URL; // Render Environment Variable

// 2. Home Route: Dashboard dikhane ke liye
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// 3. Scan Route: Repo ki files check karke AI ko bhejta hai
app.post('/scan', async (req, res) => {
    console.log("🔍 Scanning repo:", req.body.repo);
    try {
        const repoInput = req.body.repo;
        if (!repoInput.includes('/')) {
            return res.status(400).json({ explanation: "Please use 'owner/repo' format." });
        }

        const [owner, name] = repoInput.split('/');
        
        // GitHub API se file list uthana
        const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
        const files = data.map(f => f.name).join(', ');
        
        // Python AI Engine ko analysis ke liye bhejna
        const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
            command: "Scan", 
            error_log: files 
        });
        
        // AI response + repo info frontend ko wapas dena
        res.json({ 
            explanation: aiRes.data.explanation,
            fix_command: aiRes.data.fix_command,
            repo: repoInput 
        });

    } catch (e) { 
        console.error("❌ Scan Error:", e.message);
        res.status(500).json({ explanation: "Repo not found or private! Check the name." }); 
    }
});

// 4. Apply Fix Route: Frontend se aane wale data ko Python Engine (Commit logic) tak pahunchana
app.post('/apply-fix', async (req, res) => {
    console.log("🚀 Applying fix for:", req.body.repo_name);
    try {
        // Python Engine (`main.py`) ko call karna
        const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, req.body);
        
        // Python se aane wala success/error response wapas bhejna
        res.json(aiRes.data);
    } catch (e) {
        console.error("❌ Fix Error:", e.message);
        res.status(500).json({ 
            status: "error", 
            message: "AI Engine (Python) se connection nahi ho paya!" 
        });
    }
});

// Server Start
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`✅ Orchestrator running on port ${PORT}`);
    console.log(`🔗 Python Engine URL: ${PYTHON_URL}`);
});