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

// 🚀 Step 1: Deep Scan
app.post('/scan', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, repoName] = repo.split('/');
        const octo = await getAgentOctokit(installation_id);

        // Fetch recursive tree to see EVERYTHING
        const { data: tree } = await octo.git.getTree({ 
            owner, repo: repoName, tree_sha: 'main', recursive: true 
        });

        const files = tree.tree
            .filter(f => f.type === 'blob' && !f.path.includes('node_modules'))
            .map(f => f.path).join(", ");

        const ai = await axios.post(`${PYTHON_URL}/analyze-repo`, { files_context: files });
        res.json({ explanation: `🎯 Target: ${ai.data.target_file}\n🛠️ Action: ${ai.data.action}\n💡 Reason: ${ai.data.reason}`, repo });
    } catch (e) {
        res.status(500).json({ explanation: "Connection Failed. Ensure App is installed on this repo." });
    }
});

// 🛠️ Step 2: Auto-Heal (Stripe Minion Style)
app.post('/apply-fix', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, repoName] = repo.split('/');
        const octo = await getAgentOctokit(installation_id);

        // 1. Analyze again for fresh context
        const { data: tree } = await octo.git.getTree({ owner, repo: repoName, tree_sha: 'main', recursive: true });
        const files = tree.tree.map(f => f.path).join(", ");
        const analysis = await axios.post(`${PYTHON_URL}/analyze-repo`, { files_context: files });
        const target = analysis.data.target_file;

        // 2. Fetch code with Error Handling (Edge Case: Missing File)
        let original = "";
        let sha = null;
        try {
            const { data: file } = await octo.repos.getContent({ owner, repo: repoName, path: target });
            original = Buffer.from(file.content, 'base64').toString();
            sha = file.sha;
        } catch (err) { console.log("New file detection..."); }

        // 3. AI Fix
        const fix = await axios.post(`${PYTHON_URL}/apply-fix`, { file_path: target, original_code: original });

        // 4. Git Operations
        const branch = `ai-minion-heal-${Date.now()}`;
        const { data: ref } = await octo.git.getRef({ owner, repo: repoName, ref: 'heads/main' });
        await octo.git.createRef({ owner, repo: repoName, ref: `refs/heads/${branch}`, sha: ref.object.sha });

        await octo.repos.createOrUpdateFileContents({
            owner, repo: repoName, path: target, message: `🤖 AI Minion: Healed ${target}`,
            content: Buffer.from(fix.data.fixed_code).toString('base64'),
            branch, sha
        });

        const pr = await octo.pulls.create({
            owner, repo: repoName, title: `🛡️ AI Healing PR: ${target}`,
            head: branch, base: 'main', body: `### 🤖 AI Agent Report\n- **Target:** ${target}\n- **Fix:** ${analysis.data.action}`
        });

        res.json({ status: "success", pr_url: pr.data.html_url });
    } catch (e) {
        res.status(500).json({ status: "error", message: e.message });
    }
});

app.listen(process.env.PORT || 3000);