const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const app = express();

// 1. GitHub Token for Public Scans
// Ensure GITHUB_TOKEN is added in Render Environment Variables
const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });

// 2. Python Engine URL Safety
const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); 

app.use(express.json());

// 3. Serving Static Files (CSS/JS)
app.use(express.static(path.join(__dirname))); 

// 4. Root Route: Load index.html directly
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// 🚀 API 1: Scan Repository
app.post('/scan', async (req, res) => {
    const { repo } = req.body;
    if (!repo || !repo.includes('/')) {
        return res.status(400).json({ explanation: "Invalid format. Use 'owner/repo'." });
    }

    try {
        const [owner, name] = repo.split('/');
        // Fetch repo contents via Octokit
        const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
        const fileNames = data.map(f => f.name).join(', ');

        // Send file list to Python AI Engine
        const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
            command: "Scan", 
            error_log: `Files found: ${fileNames}. Suggest a README or improvements.` 
        });

        res.json({ ...aiRes.data, repo });
    } catch (e) {
        console.error("❌ Scan Error:", e.message);
        res.status(500).json({ explanation: "Repo not accessible or GitHub API limit hit." });
    }
});

// 🛠️ API 2: Apply Auto-Fix
app.post('/apply-fix', async (req, res) => {
    try {
        console.log("Pushing fix to Python Engine...");
        // Forwarding installation_id and code to Python
        const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, req.body);
        res.json(aiRes.data);
    } catch (e) {
        console.error("❌ Apply Fix Error:", e.response?.data || e.message);
        const errMsg = e.response?.data?.detail || "AI Engine connection failed.";
        res.status(500).json({ status: "error", message: errMsg });
    }
});

// 5. Start Server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`✅ SaaS Orchestrator Live on Port ${PORT}`);
    console.log(`🔗 Python Engine connected at: ${PYTHON_URL}`);
});