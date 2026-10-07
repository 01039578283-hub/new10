/** Apply only reviewed media derivatives and content-hashed stylesheet/script URLs. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseHTML,targetPage} from './image-order-build.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
function assetFile(src,name){
 if(/^(?:https?:)?\/\//.test(src)||src.startsWith('data:'))return null;
 const clean=src.split(/[?#]/)[0];
 return decodeURIComponent(path.posix.normalize(clean.startsWith('/')?clean.slice(1):path.posix.join(path.posix.dirname(name),clean)));
}
export function readableContext(dir=root){return JSON.parse(fs.readFileSync(path.join(dir,'readable-media-review.json'),'utf8'));}
export function versionResources(source,name,review){
 return source.replace(/(<(?:script|link)\b[^>]*?\s(?:src|href)=")[^"]+("[^>]*>)/gi,(whole,a,b)=>{
  const val=whole.slice(a.length,-b.length),file=assetFile(val,name);return review.versions[file]?a+'/'+review.versions[file]+b:whole;
 });
}
export function transformReadable(source,name,review){
 const original=source;source=versionResources(source,name,review);
 if(source.includes('data-readable-media="20261007"'))return {html:source,changed:source!==original};
 let s=source,core=false;const edits=[];const nodes=parseHTML(s);let sizes=0,segments=0,enlargements=0;
 for(const n of nodes){
  if(n.tag!=='img'||!n.attrs.src)continue;
  const file=assetFile(n.attrs.src,name),info=review.images[file];if(!info)continue;
  let tag=s.slice(n.start,n.end);
  if(!n.attrs.width||!n.attrs.height){tag=tag.replace(/\s(?:width|height)=["'][^"']*["']/g,'').replace(/\s*\/?\s*>$/,` width="${info.width}" height="${info.height}"${tag.endsWith('/>')?' /':''}>`);sizes++;}
  let p=n.parent,role='';while(p){if(p.attrs['data-media-role']){role=p.attrs['data-media-role'];break;}p=p.parent;}
  if(!role)role=/(?:본문|지도)/.test(n.attrs.alt||'')?((n.attrs.alt||'').includes('지도')?'map':'body'):'';
  const meaningful=targetPage(name)&&['body','map'].includes(role);
  if(meaningful){
   core=true;const alt=n.attrs.alt||`${role==='map'?'지도':'학습 안내'} 이미지`,original='/'+file;
   let parent=n.parent,anchor=null;while(parent&&parent.tag!=='figure'){if(parent.tag==='a')anchor=parent;parent=parent.parent;}
   if(anchor)throw Error('Existing media anchor requires explicit review: '+name+' '+file);
   const open=(extra='')=>`<a class="image-enlarge${extra}" href="${esc(original)}" data-image-enlarge="${role}" data-original-width="${info.width}" data-original-height="${info.height}" data-original-alt="${esc(alt)}" aria-label="${esc(alt)} 확대">`;
   const tiled=review.tiled[file];
   if(tiled){
    tag=tiled.tiles.map((t,i)=>open(' segment')+`<img src="/${t.file}" alt="${esc(alt)} · ${i+1}/${tiled.tiles.length} 구간" width="${t.width}" height="${t.height}" loading="lazy" decoding="async" data-image-segment="${i+1}" data-original-src="${esc(original)}">`+'</a>').join('');segments+=tiled.tiles.length;
   }else tag=open()+tag+'</a>';
   enlargements++;
  }
  if(tag!==s.slice(n.start,n.end))edits.push({start:n.start,end:n.end,text:tag});
 }
 if(core){
  // Visible HTML links provide navigation to the existing fact section even without scripts.
  const facts=nodes.find(n=>n.attrs.id==='center-facts'||n.attrs.id==='directions');
  const sequence=nodes.find(n=>n.attrs['data-image-order']==='sequence-v1');
  if(sequence){
   const note=`<p class="media-reading-note">이미지를 누르면 원본 너비로 확대됩니다.${facts?` <a href="#${facts.attrs.id}">주소·수강 조건을 텍스트로 확인</a>`:''} <a href="/상담문의/">전화·문자 상담 안내</a></p>`;
   edits.push({start:sequence.start,end:sequence.start,text:note});
  }
 }
 for(const e of edits.sort((a,b)=>b.start-a.start))s=s.slice(0,e.start)+e.text+s.slice(e.end);
 if(core)s=s.replace(/<\/head\s*>/i,`<link rel="stylesheet" href="/assets/readable-media.css"><script defer src="/assets/readable-media.js"></script></head>`);
 // Version URLs, rather than caching mutable asset names for a year.
 s=versionResources(s,name,review);
 s=s.replace(/<html\b/i,'<html data-readable-media="20261007"');
 return {html:s,changed:s!==original,sizes,segments,enlargements};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const review=readableContext();const manifest=JSON.parse(fs.readFileSync(path.join(root,'release-public-manifest.json'),'utf8'));const output=path.join(root,'.public-release');const report={pages:0,changed:0,sizes:0,segments:0,enlargements:0};
 for(const name of Object.keys(manifest.files).filter(n=>n.endsWith('index.html'))){const f=path.join(output,name),r=transformReadable(fs.readFileSync(f,'utf8'),name,review);report.pages++;if(r.changed){fs.writeFileSync(f,r.html);report.changed++;}for(const k of ['sizes','segments','enlargements'])report[k]+=r[k]||0;}
 console.log(JSON.stringify(report));
}
