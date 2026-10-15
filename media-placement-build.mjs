/** Move the existing body/map block before the branch facts, without rewriting it. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {parseHTML} from './image-order-build.mjs';

const root=path.dirname(fileURLToPath(import.meta.url));
export const fingerprint=source=>createHash('sha256').update(source.replaceAll('\r\n','\n').replace(/<link\b[^>]*>/gi,tag=>{
 const rel=tag.match(/\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i);
 return /^(?:icon|shortcut icon|apple-touch-icon|apple-touch-icon-precomposed)$/i.test((rel?.[1]??rel?.[2]??rel?.[3]??'').trim())?'':tag;
})).digest('hex');
const plain=source=>source.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
export function moveMedia(source,row){
 const nodes=parseHTML(source);
 const media=nodes.filter(n=>n.attrs.id===row.imageId),facts=nodes.filter(n=>n.attrs.id===row.factsId);
 if(media.length!==1||facts.length!==1)throw Error('Ambiguous image/facts block');
 const [image]=media,[target]=facts;
 if(image.parent!==target.parent||image.parent?.tag!=='main')throw Error('Unreviewed image/facts containment');
 const heading=nodes.find(n=>n.tag==='h2'&&n.parent===target);
 if(!heading||plain(source.slice(heading.openEnd,heading.closeStart))!==row.heading)throw Error('Branch facts heading changed');
 if(!nodes.some(n=>((n.tag==='img'&&n.attrs['data-media-role']==='body')||(n.tag==='a'&&n.attrs['data-image-enlarge']==='body'))&&n.start>image.start&&n.end<image.end))throw Error('Body image missing');
 const siblings=image.parent.children;
 if(siblings.indexOf(image)+1===siblings.indexOf(target))return source;
 const block=source.slice(image.start,image.end);
 const without=source.slice(0,image.start)+source.slice(image.end);
 const position=target.start-(image.start<target.start?block.length:0);
 return without.slice(0,position)+block+without.slice(position);
}
export function build(){
 const review=JSON.parse(fs.readFileSync(path.join(root,'media-placement-review.json'),'utf8'));
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'release-public-manifest.json'),'utf8'));
 const stats={pages:0,changed:0,alreadyCorrect:0,roles:{}};
 for(const [name,row] of Object.entries(review.pages)){
  if(!Object.hasOwn(manifest.files,name)||!name.endsWith('/index.html'))throw Error('Page outside public manifest '+name);
  const file=path.resolve(root,'.public-release',name);
  if(!file.startsWith(path.join(root,'.public-release')+path.sep))throw Error('Unsafe page path');
  const source=fs.readFileSync(file,'utf8'),hash=fingerprint(source);
  if(hash!==row.before&&hash!==row.after)throw Error('Unreviewed HTML '+name);
  const after=moveMedia(source,row);
  if(fingerprint(after)!==row.after)throw Error('Unexpected moved output '+name);
  stats.pages++;stats.roles[row.role]=(stats.roles[row.role]||0)+1;
  if(after!==source){fs.writeFileSync(file,after);stats.changed++;}else stats.alreadyCorrect++;
 }
 return stats;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(build()));
