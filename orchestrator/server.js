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

app.post('/scan', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, repoName] = repo.split('/');
        const octo = await getAgentOctokit(installation_id);

        const { data: tree } = await octo.git.getTree({ 
            owner, repo: repoName, tree_sha: 'main', recursive: true 
        });

        const files = tree.tree
            .filter(f => f.type === 'blob' && !f.path.includes('node_modules'))
            .map(f => f.path).join(", ");

        const ai = await axios.post(`${PYTHON_URL}/analyze-repo`, { files_context: files });
        res.json({ ...ai.data, repo });
    } catch (e) {
        res.status(500).json({ explanation: "Check App Permissions on GitHub." });
    }
});

app.post('/apply-fix', async (req, res) => {
    try {
        const { repo, installation_id } = req.body;
        const [owner, repoName] = repo.split('/');
        const octo = await getAgentOctokit(installation_id);

        const { data: tree } = await octo.git.getTree({ owner, repo: repoName, tree_sha: 'main', recursive: true });
        const files = tree.tree.map(f => f.path).join(", ");
        const analysis = await axios.post(`${PYTHON_URL}/analyze-repo`, { files_context: files });
        const target = analysis.data.target_file;

        let original = "";
        let fileSha = null; // SHA buffer fix
        try {
            const { data: file } = await octo.repos.getContent({ owner, repo: repoName, path: target });
            original = Buffer.from(file.content, 'base64').toString();
            fileSha = file.sha; // Capture SHA for update
        } catch (err) { console.log("Creating new file..."); }

        const fix = await axios.post(`${PYTHON_URL}/apply-fix`, { file_path: target, original_code: original });

        const branch = `ai-heal-${Date.now()}`;
        const { data: ref } = await octo.git.getRef({ owner, repo: repoName, ref: 'heads/main' });
        await octo.git.createRef({ owner, repo: repoName, ref: `refs/heads/${branch}`, sha: ref.object.sha });

        // FIX: Added 'sha' to the update call
        await octo.repos.createOrUpdateFileContents({
            owner, repo: repoName, path: target, 
            message: `🤖 AI Minion: Fixed ${target}`,
            content: Buffer.from(fix.data.fixed_code).toString('base64'),
            branch, 
            sha: fileSha 
        });

        const pr = await octo.pulls.create({
            owner, repo: repoName, title: `🛡️ AI Fix: ${target}`,
            head: branch, base: 'main', 
            body: `### 🤖 AI Agent Report\n- **Target:** ${target}\n- **Action:** ${analysis.data.action}`
        });

        res.json({ status: "success", pr_url: pr.data.html_url });
    } catch (e) {
        res.status(500).json({ status: "error", message: e.message });
    }
});

app.listen(process.env.PORT || 3000);