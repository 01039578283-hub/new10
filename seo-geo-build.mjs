/** Apply only reviewed content changes after the preserved media/map pipeline. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {gunzipSync} from 'node:zlib';
import {fingerprint} from './media-placement-build.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(root,'.public-release');
const bytes=gunzipSync(fs.readFileSync(path.join(root,'seo-geo-review.json.gz')));
const summary=JSON.parse(fs.readFileSync(path.join(root,'seo-geo-review-summary.json'),'utf8'));
if(createHash('sha256').update(bytes).digest('hex')!==summary.reviewSha256)throw Error('Reviewed content bundle changed');
const review=JSON.parse(bytes.toString('utf8'));
const pilot=process.argv.includes('--pilot');
const check=process.argv.includes('--check');
const selected=pilot?review.pilot:Object.keys(review.pages);
const stats={reviewed:0,changed:0,alreadyApplied:0,pilot,check};
let cursor=0;
await Promise.all(Array.from({length:12},async()=>{
 while(cursor<selected.length){
  const name=selected[cursor++],row=review.pages[name];
  if(name.startsWith('/')||name.split('/').includes('..')||!name.endsWith('index.html'))throw Error('Unsafe reviewed page');
  const file=path.join(out,name),source=await fs.promises.readFile(file,'utf8');
  const hash=fingerprint(source);stats.reviewed++;
  if(hash===row.after){stats.alreadyApplied++;continue;}
  if(hash!==row.before)throw Error('Content input changed; review required: '+name);
  let html=source.replaceAll('\r\n','\n');
  for(const edit of row.edits){
   if(!edit.old)throw Error('Empty content patch');
   const count=html.split(edit.old).length-1;
   if(count!==edit.count)throw Error('Content occurrence mismatch: '+name+' '+edit.reason);
   html=html.replaceAll(edit.old,edit.new);
  }
  if(fingerprint(html)!==row.after)throw Error('Content result differs from review: '+name);
  if(check)throw Error('Reviewed content has not been applied: '+name);
  await fs.promises.writeFile(file,html);stats.changed++;
 }
}));
if(!pilot){
 const file=path.join(out,'sitemap.xml');let xml=(await fs.promises.readFile(file,'utf8')).replaceAll('\r\n','\n');
 for(const edit of review.sitemap.edits){
  if(xml.includes(edit.new))continue;
  if(xml.split(edit.old).length-1!==1)throw Error('Sitemap entry changed');
  if(check)throw Error('Reviewed sitemap dates have not been applied');
  xml=xml.replace(edit.old,edit.new);
 }
 const digest=createHash('sha256').update(xml.replaceAll('\r\n','\n')).digest('hex');
 if(digest!==review.sitemap.after)throw Error('Unexpected sitemap output');
 if(!check)await fs.promises.writeFile(file,xml);
 const key=review.indexNow.key;
 if(!/^[a-f0-9]{32}$/.test(key))throw Error('Invalid IndexNow ownership file');
 const dest=path.join(out,key+'.txt');
 if(check){if((await fs.promises.readFile(dest,'utf8'))!==key)throw Error('IndexNow file differs');}
 else await fs.promises.writeFile(dest,key);
}
console.log(JSON.stringify(stats));
