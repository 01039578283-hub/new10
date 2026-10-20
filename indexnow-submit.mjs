/** Notify once after production verification, never from the build pipeline. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
const root=path.dirname(fileURLToPath(import.meta.url));
const argv=process.argv.slice(2),value=name=>{const i=argv.indexOf(name);return i<0?null:argv[i+1]};
const bytes=gunzipSync(fs.readFileSync(path.join(root,'seo-geo-review.json.gz')));
const summary=JSON.parse(fs.readFileSync(path.join(root,'seo-geo-review-summary.json'),'utf8'));
const digest=s=>createHash('sha256').update(s).digest('hex');
if(digest(bytes)!==summary.reviewSha256)throw Error('Review bundle checksum differs');
const review=JSON.parse(bytes.toString('utf8')),base=new URL(review.base);
const urls=review.indexNow.urlList;
if(urls.length<1||urls.length>10000||new Set(urls).size!==urls.length)throw Error('Invalid changed URL batch');
const entries=urls.map(url=>{
 const u=new URL(url);
 if(u.origin!==base.origin||u.protocol!=='https:'||u.search||u.hash)throw Error('Unexpected notification URL');
 const file=decodeURIComponent(u.pathname).slice(1)+'index.html',row=review.pages[file];
 if(!row||row.before===row.after||(!row.bodyRewrite&&!row.reasons.includes('subject-specific school preparation')))throw Error('URL lacks a reviewed substantive change');
 return {url,file,after:row.after};
});
const batchHash=digest(JSON.stringify(entries));
if(!argv.includes('--submit')){
 console.log(JSON.stringify({mode:'dry-run',urls:urls.length,unique:true,onlyReviewedCurrentContentChanges:true,automaticSubmissionDuringBuild:false}));
 process.exit(0);
}
const receiptFile=value('--receipt'),validationFile=value('--validation'),fileManifest=value('--files');
if(!receiptFile||!validationFile||!fileManifest)throw Error('Production validation, file hashes and receipt path are required');
if(fs.existsSync(receiptFile)){
 const previous=JSON.parse(fs.readFileSync(receiptFile,'utf8'));
 if(previous.batchHash===batchHash&&[200,202].includes(previous.status)){
  console.log(JSON.stringify({mode:'already-received',urls:previous.urls,status:previous.status,repeatRequestSent:false}));process.exit(0);
 }
}
const verified=new Map(JSON.parse(fs.readFileSync(validationFile,'utf8')).map(row=>[row.file,row]));
const hashes=JSON.parse(fs.readFileSync(fileManifest,'utf8'));
for(const {file} of entries){const r=verified.get(file);if(!r||r.status!==200||r.errors.length||r.sha256!==hashes[file]?.sha256)throw Error('Missing successful production response verification: '+file);}
const key=review.indexNow.key,keyLocation=new URL('/'+key+'.txt',base).href;
const keyResponse=await fetch(keyLocation,{redirect:'error',signal:AbortSignal.timeout(30000)});
if(keyResponse.status!==200||(await keyResponse.text())!==key)throw Error('Live ownership TXT differs');
const endpoint='https://searchadvisor.naver.com/indexnow';
const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json; charset=utf-8'},body:JSON.stringify({host:base.hostname,key,keyLocation,urlList:urls}),signal:AbortSignal.timeout(45000)});
const body=(await response.text()).slice(0,1200);
const git=spawnSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'});if(git.status!==0)throw Error('Cannot record release commit');
const result={commit:git.stdout.trim(),batchHash,urls:urls.length,endpoint,submittedAt:new Date().toISOString(),status:response.status,response:body,result:response.status===200?'received; indexing not guaranteed':response.status===202?'received; ownership validation pending':'not confirmed received'};
fs.writeFileSync(receiptFile,JSON.stringify(result,null,2));
console.log(JSON.stringify({...result,response:undefined,batchHash:undefined}));
if(![200,202].includes(response.status))process.exitCode=1;
