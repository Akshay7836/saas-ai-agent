const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const app = express();

// Render Environment Variables se Token uthana
const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); // Aakhiri slash hatane ke liye

app.use(express.json());
app.use(express.static(path.join(__dirname))); 

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

// Scan Logic: GitHub se files lekar AI ko bhejna
app.post('/scan', async (req, res) => {
    const repoInput = req.body.repo;
    console.log("🔍 Scanning:", repoInput);

    if (!repoInput || !repoInput.includes('/')) {
        return res.status(400).json({ explanation: "Format 'owner/repo' hona chahiye!" });
    }

    try {
        const [owner, name] = repoInput.split('/');
        
        // GitHub API call
        const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
        const files = data.map(f => f.name).join(', ');
        
        // Python Engine call
        const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
            command: "Scan", 
            error_log: files 
        });
        
        res.json({ ...aiRes.data, repo: repoInput });
    } catch (e) { 
        console.error("❌ Scan Error:", e.response?.data || e.message);
        res.status(500).json({ explanation: "GitHub Error: Check if repo is public and GITHUB_TOKEN is valid." }); 
    }
});

// Apply Fix: AI suggestion ko GitHub par commit karna
app.post('/apply-fix', async (req, res) => {
    try {
        const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, req.body);
        res.json(aiRes.data);
    } catch (e) {
        console.error("❌ Apply Fix Error:", e.response?.data || e.message);
        res.status(500).json({ status: "error", message: "AI Engine connection failed!" });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 Node Server ready on port ${PORT}`));