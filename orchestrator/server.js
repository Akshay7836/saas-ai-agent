const express = require('express');
const axios = require('axios');
const { Octokit } = require("@octokit/rest");
const { createAppAuth } = require("@octokit/auth-app");
const app = express();

const APP_ID = process.env.GITHUB_APP_ID;
const PRIVATE_KEY = process.env.GITHUB_PRIVATE_KEY.replace(/\\n/g, '\n');
const PYTHON_URL = process.env.PYTHON_URL.replace(/\/$/, "");

app.use(express.json());
app.use(express.static(__dirname));

async function getAgentOctokit(id) {
    return new Octokit({
        authStrategy: createAppAuth,
        auth: { appId: APP_ID, privateKey: PRIVATE_KEY, installationId: id },
    });
}

// 🚀 Step 1: Deep Scan with RAG Indexing
app.post('/scan', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, repoName] = repo.split('/');
        const octo = await getAgentOctokit(installation_id);

        // 1. Fetch recursive tree
        const { data: tree } = await octo.git.getTree({ 
            owner, repo: repoName, tree_sha: 'main', recursive: true 
        });

        // 2. Filter for logic/config files to index (Avoid binaries/images)
        const relevantFiles = tree.tree.filter(f => 
            f.type === 'blob' && 
            !f.path.includes('node_modules') &&
            !f.path.includes('.git') &&
            (f.path.endsWith('.js') || f.path.endsWith('.py') || f.path.endsWith('.html') || f.path.endsWith('.json') || f.path.includes('Dockerfile'))
        );

        // 3. Fetch ACTUAL content for indexing (The "RAG" Feed)
        const fileContents = {};
        await Promise.all(relevantFiles.map(async (file) => {
            try {
                const { data } = await octo.repos.getContent({ owner, repo: repoName, path: file.path });
                fileContents[file.path] = Buffer.from(data.content, 'base64').toString();
            } catch (err) { console.error(`Skipping ${file.path}`); }
        }));

        // 4. Send content to Python for Vector Indexing
        await axios.post(`${PYTHON_URL}/index-repo`, { files: fileContents });

        // 5. Run Multi-Issue Analysis
        const fileList = relevantFiles.map(f => f.path).join(", ");
        const aiResponse = await axios.post(`${PYTHON_URL}/analyze-repo`, { files_context: fileList });
        
        // Formulate a combined explanation for the UI
        const issuesSummary = aiResponse.data.issues.map(i => 
            `📍 File: ${i.target_file}\n⚠️ Issue: ${i.reason}\n🛠️ Fix: ${i.action}\n`
        ).join("\n---\n");

        res.json({ 
            explanation: issuesSummary, 
            issues: aiResponse.data.issues, // Pass the array to UI for the fix button
            repo 
        });

    } catch (e) {
        console.error(e);
        res.status(500).json({ explanation: "Connection Failed. Ensure App is installed and Python Engine is up." });
    }
});

// 🛠️ Step 2: Auto-Heal (Supports specific file targeting)
app.post('/apply-fix', async (req, res) => {
    try {
        const { repo, installation_id, target_file } = req.body;
        const [owner, repoName] = repo.split('/');
        const octo = await getAgentOctokit(installation_id);

        // 1. Fetch current file content
        let original = "";
        let sha = null;
        try {
            const { data: file } = await octo.repos.getContent({ owner, repo: repoName, path: target_file });
            original = Buffer.from(file.content, 'base64').toString();
            sha = file.sha;
        } catch (err) { console.log("Creating new file..."); }

        // 2. Get AI Fix
        const fixResponse = await axios.post(`${PYTHON_URL}/apply-fix`, { 
            file_path: target_file, 
            original_code: original 
        });

        // 3. Git Operations
        const branch = `ai-heal-${Date.now()}`;
        const { data: ref } = await octo.git.getRef({ owner, repo: repoName, ref: 'heads/main' });
        await octo.git.createRef({ owner, repo: repoName, ref: `refs/heads/${branch}`, sha: ref.object.sha });

        await octo.repos.createOrUpdateFileContents({
            owner, repo: repoName, 
            path: target_file, 
            message: `🤖 AI Minion: Healed ${target_file}`,
            content: Buffer.from(fixResponse.data.fixed_code).toString('base64'),
            branch, 
            sha
        });

        const pr = await octo.pulls.create({
            owner, repo: repoName, 
            title: `🛡️ AI Healing PR: ${target_file}`,
            head: branch, 
            base: 'main', 
            body: `### 🤖 AI Agent Report\n- **Target:** ${target_file}\n- **Status:** Automatically reconstructed for production.`
        });

        res.json({ status: "success", pr_url: pr.data.html_url });
    } catch (e) {
        res.status(500).json({ status: "error", message: e.message });
    }
});

app.listen(process.env.PORT || 3000);