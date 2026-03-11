const bodyParser=require("body-parser")
const {Octokit}=require("@octokit/core")
const {createAppAuth}=require("@octokit/auth-app")
const axios=require("axios")
require("dotenv").config()
const bodyParser = require("body-parser")
const path = require("path")

const app = express()

app.use(bodyParser.json())

// serve static files (index.html)
app.use(express.static(__dirname))

// root route
app.get("/", (req,res)=>{
res.sendFile(path.join(__dirname,"index.html"))
})
function getOctokit(installationId){

return new Octokit({

authStrategy:createAppAuth,

auth:{
appId:process.env.GITHUB_APP_ID,
privateKey:process.env.GITHUB_PRIVATE_KEY,
installationId:installationId
}

})

}

app.post("/scan",async(req,res)=>{

try{

const {repo,installation_id}=req.body

if(!repo || !installation_id){
return res.status(400).json({error:"repo or installation_id missing"})
}

const [owner,repoName]=repo.split("/")

const octokit=getOctokit(installation_id)

const files=await octokit.request(
"GET /repos/{owner}/{repo}/contents",
{owner:owner,repo:repoName}
)

const ai=await axios.post(
process.env.AI_ENGINE_URL+"/analyze",
{
repo:repo,
files:files.data
}
)

res.json(ai.data)

}catch(err){

console.log(err)

res.status(500).json({error:"scan failed"})

}

})

app.post("/apply-fix",async(req,res)=>{

try{

const {repo,installation_id,target_file}=req.body

if(!repo || !installation_id || !target_file){
return res.status(400).json({error:"missing parameters"})
}

const [owner,repoName]=repo.split("/")

const octokit=getOctokit(installation_id)

const repoInfo=await octokit.request(
"GET /repos/{owner}/{repo}",
{owner:owner,repo:repoName}
)

const base=repoInfo.data.default_branch

const ref=await octokit.request(
"GET /repos/{owner}/{repo}/git/ref/heads/{branch}",
{owner:owner,repo:repoName,branch:base}
)

const sha=ref.data.object.sha

const branch="ai-fix-"+Date.now()

await octokit.request(
"POST /repos/{owner}/{repo}/git/refs",
{
owner:owner,
repo:repoName,
ref:"refs/heads/"+branch,
sha:sha
}
)

await octokit.request(
"PUT /repos/{owner}/{repo}/contents/{path}",
{
owner:owner,
repo:repoName,
path:target_file,
message:"AI DevOps Fix",
content:Buffer.from("//AI Fix\n").toString("base64"),
branch:branch
}
)

const pr=await octokit.request(
"POST /repos/{owner}/{repo}/pulls",
{
owner:owner,
repo:repoName,
title:"AI DevOps Fix",
head:branch,
base:base
}
)

res.json({pr_url:pr.data.html_url})

}catch(err){

console.log(err)

res.status(500).json({error:"PR failed"})

}

})

const PORT=process.env.PORT||3000

app.listen(PORT,()=>{
console.log("Server running on port "+PORT)
})