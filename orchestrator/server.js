// const express = require('express');
// const axios = require('axios');
// const path = require('path');
// const { Octokit } = require("@octokit/rest");
// const app = express();

// // 1. GitHub Token for Public Scans
// // Ensure GITHUB_TOKEN is added in Render Environment Variables
// const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });

// // 2. Python Engine URL Safety
// const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); 

// app.use(express.json());

// // 3. Serving Static Files (CSS/JS)
// app.use(express.static(path.join(__dirname))); 

// // 4. Root Route: Load index.html directly
// app.get('/', (req, res) => {
//     res.sendFile(path.join(__dirname, 'index.html'));
// });

// // 🚀 API 1: Scan Repository
// app.post('/scan', async (req, res) => {
//     const { repo } = req.body;
//     if (!repo || !repo.includes('/')) {
//         return res.status(400).json({ explanation: "Invalid format. Use 'owner/repo'." });
//     }

//     try {
//         const [owner, name] = repo.split('/');
//         // Fetch repo contents via Octokit
//         const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
//         const fileNames = data.map(f => f.name).join(', ');

//         // Send file list to Python AI Engine
//         const aiRes = await axios.post(`${PYTHON_URL}/fix-error`, { 
//             command: "Scan", 
//             error_log: `Files found: ${fileNames}. Suggest a README or improvements.` 
//         });

//         res.json({ ...aiRes.data, repo });
//     } catch (e) {
//         console.error("❌ Scan Error:", e.message);
//         res.status(500).json({ explanation: "Repo not accessible or GitHub API limit hit." });
//     }
// });

// // 🛠️ API 2: Apply Auto-Fix
// app.post('/apply-fix', async (req, res) => {
//     try {
//         console.log("Pushing fix to Python Engine...");
//         // Forwarding installation_id and code to Python
//         const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, req.body);
//         res.json(aiRes.data);
//     } catch (e) {
//         console.error("❌ Apply Fix Error:", e.response?.data || e.message);
//         const errMsg = e.response?.data?.detail || "AI Engine connection failed.";
//         res.status(500).json({ status: "error", message: errMsg });
//     }
// });

// // 5. Start Server
// const PORT = process.env.PORT || 3000;
// app.listen(PORT, () => {
//     console.log(`✅ SaaS Orchestrator Live on Port ${PORT}`);
//     console.log(`🔗 Python Engine connected at: ${PYTHON_URL}`);
// });



const express = require('express');
const axios = require('axios');
const path = require('path');
const { Octokit } = require("@octokit/rest");
const app = express();

// 1. GitHub Token for Public Scans
const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });

// 2. Python Engine URL Safety
const PYTHON_URL = process.env.PYTHON_URL?.replace(/\/$/, ""); 

app.use(express.json());
app.use(express.static(path.join(__dirname))); 

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
        const { data } = await octokit.repos.getContent({ owner, repo: name, path: '' });
        const fileNames = data.map(f => f.name).join(', ');

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

// 🛠️ API 2: Final Sync with Python AI Engine
app.post('/apply-fix', async (req, res) => {
    try {
        const { repo, file_path, installation_id } = req.body;
        const [owner, name] = repo.split('/');

        console.log(`🤖 Requesting fix from AI Engine for: ${file_path}`);
        
        // 1. Get Fix from Python Engine (Mapping repo to repo_name for Python sync)
        const aiRes = await axios.post(`${PYTHON_URL}/apply-fix`, {
            repo_name: repo,
            file_path: file_path,
            installation_id: installation_id
        });
        
        const { fixed_code, summary } = aiRes.data; 

        // 2. Create Unique Branch Name
        const newBranch = `ai-fix-${Date.now()}`;

        // 3. Get Main Branch SHA
        const { data: mainRef } = await octokit.git.getRef({
            owner, repo: name, ref: 'heads/main'
        });

        // 4. Create New Branch
        await octokit.git.createRef({
            owner, repo: name,
            ref: `refs/heads/${newBranch}`,
            sha: mainRef.object.sha
        });

        // 5. Get File SHA (Try-Catch in case file doesn't exist yet)
        let fileSha;
        try {
            const { data: fileData } = await octokit.repos.getContent({
                owner, repo: name, path: file_path, ref: 'main'
            });
            fileSha = fileData.sha;
        } catch (err) {
            console.log("File not found on main, creating fresh file.");
        }

        // 6. Push Fix to New Branch
        await octokit.repos.createOrUpdateFileContents({
            owner, repo: name,
            path: file_path,
            message: `🤖 AI Fix: Optimized ${file_path}`,
            content: Buffer.from(fixed_code).toString('base64'),
            branch: newBranch,
            sha: fileSha // Will be undefined for new files
        });

        // 7. Create Pull Request with AI Summary
        const pr = await octokit.pulls.create({
            owner, repo: name,
            title: `🛠️ AI Suggestion: Fix for ${file_path}`,
            head: newBranch,
            base: 'main',
            body: summary || "AI generated logical optimizations and improvements."
        });

        res.json({ 
            status: "success", 
            message: "PR created successfully!", 
            pr_url: pr.data.html_url 
        });

    } catch (e) {
        console.error("❌ PR Workflow Error:", e.response?.data || e.message);
        res.status(500).json({ 
            status: "error", 
            message: e.response?.data?.detail || "Failed to create PR. Please check logs." 
        });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`✅ SaaS Orchestrator Live with PR Workflow on Port ${PORT}`);
});