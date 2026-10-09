/** Fixed, reviewed photographs remain at their existing bottom location. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseHTML, imageRole} from './image-order-build.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const output=path.resolve(root,process.argv[2]||'.public-release');
const review=JSON.parse(fs.readFileSync(path.join(root,'bottom-representative-review.json'),'utf8'));
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
const parents=n=>{const out=[];for(let p=n.parent;p;p=p.parent)out.push(p);return out;};
const local=s=>decodeURIComponent(new URL(s,review.base).pathname);
const attribute=(tag,key,value)=>{
 const re=new RegExp('\\s'+key+'(?:\\s*=\\s*(?:"[^"]*"|\'[^\']*\'|[^\\s>]+))?','i');
 return re.test(tag)?tag.replace(re,` ${key}="${esc(value)}"`):tag.replace(/\s*\/?>$/,` ${key}="${esc(value)}">`);
};
const style='<style data-bottom-representative="v1">.branch-og-bottom{box-sizing:border-box;width:100%;max-width:918px;margin:32px auto;padding:24px;background:#fff;border:1px solid #e3e0db;border-radius:20px}.branch-og-bottom figure{margin:0}.branch-og-bottom img{display:block;width:100%;height:auto;max-width:100%;object-fit:contain}.branch-og-bottom figcaption{margin-top:12px;color:#555;line-height:1.6}@media(max-width:600px){.branch-og-bottom{padding:16px}}</style>';
const report={pages:0,changed:0,reusedBottom:0,addedBottom:0,removedHidden:0,unfolded:0};
for(const row of review.pages){
 const file=path.join(output,row.file),source=fs.readFileSync(file,'utf8');report.pages++;
 if(source.includes('data-bottom-representative="v1"'))continue;
 const nodes=parseHTML(source),main=nodes.find(n=>n.tag==='main'),head=nodes.find(n=>n.tag==='head');
 if(!main||!head)throw Error('Missing page regions: '+row.file);
 const edits=[],add=(n,value)=>edits.push({start:n.start,end:n.end,value});
 const bodyImages=nodes.filter(n=>n.tag==='img'&&parents(n).includes(main));
 const oldHidden=bodyImages.filter(n=>imageRole(n)==='representative'&&(Object.hasOwn(n.attrs,'hidden')||/display\s*:\s*none/i.test(n.attrs.style||'')));
 for(const n of oldHidden)add(n,'');
 report.removedHidden+=Number(oldHidden.length>0);
 const gallery=bodyImages.filter(n=>parents(n).some(p=>/\bbranch-gallery\b/.test(p.attrs.class||'')));
 const selected=bodyImages.filter(n=>local(n.attrs.src)===local(row.image.imageUrl));
 if(selected.length>1)throw Error('Existing duplicate selected photo: '+row.file);
 if(selected.length&&!gallery.includes(selected[0]))throw Error('Selected photograph outside verified bottom gallery: '+row.file);
 const gates=[...new Set(gallery.flatMap(parents).filter(n=>n.tag==='details'))];
 for(const gate of gates){
  edits.push({start:gate.start,end:gate.openEnd,value:source.slice(gate.start,gate.openEnd).replace(/^<details\b/i,'<div').replace(/\sopen(?:="[^"]*")?/i,'')});
  edits.push({start:gate.closeStart,end:gate.end,value:'</div>'});
  for(const child of gate.children.filter(n=>n.tag==='summary'))add(child,'');
 }
 report.unfolded+=Number(gates.length>0);
 if(selected.length){
  const n=selected[0];let tag=source.slice(n.start,n.end);
  for(const [key,value] of Object.entries({'alt':row.alt,'width':row.image.width,'height':row.image.height,'data-page-representative':'true'}))tag=attribute(tag,key,value);
  add(n,tag);
  const figure=parents(n).find(p=>p.tag==='figure');const caption=figure?.children.find(p=>p.tag==='figcaption');
  if(caption)add(caption,`<figcaption>${esc(row.caption)}</figcaption>`);
  report.reusedBottom++;
 }else{
  const section=`\n<section class="branch-og-bottom" id="branch-representative"><h2>${row.image.kind==='actual'?esc(row.branch)+' 사진':'학습 공간 구성 예시'}</h2><figure><img data-page-representative="true" src="${esc(row.image.src)}" width="${row.image.width}" height="${row.image.height}" alt="${esc(row.alt)}" loading="lazy" decoding="async"><figcaption>${esc(row.caption)}</figcaption></figure></section>\n`;
  edits.push({start:main.closeStart,end:main.closeStart,value:section});report.addedBottom++;
 }
 for(const meta of nodes.filter(n=>n.tag==='meta'&&parents(n).includes(head))){
  if(/^(og:image|twitter:image)(:|$)/i.test(meta.attrs.property||meta.attrs.name||''))add(meta,'');
 }
 const metadata=`<meta property="og:image" content="${esc(row.image.imageUrl)}"><meta property="og:image:width" content="${row.image.width}"><meta property="og:image:height" content="${row.image.height}"><meta property="og:image:alt" content="${esc(row.alt)}"><meta name="twitter:image" content="${esc(row.image.imageUrl)}"><meta name="twitter:image:alt" content="${esc(row.alt)}">`;
 edits.push({start:head.closeStart,end:head.closeStart,value:metadata+style});
 for(const script of nodes.filter(n=>n.tag==='script'&&n.attrs.type==='application/ld+json')){
  const chunk=source.slice(script.start,script.end),open=chunk.indexOf('>')+1,close=chunk.toLowerCase().lastIndexOf('</script');
  const json=JSON.parse(chunk.slice(open,close));const graph=Array.isArray(json)?json:json['@graph']||[json];let changed=false;
  for(const entity of graph){
   if(!entity.url||local(entity.url)!==local(row.url))continue;
   const types=Array.isArray(entity['@type'])?entity['@type']:[entity['@type']];
   if(types.some(t=>['WebPage','Article','CollectionPage'].includes(t))){
    entity.primaryImageOfPage={'@type':'ImageObject',url:row.image.imageUrl,width:row.image.width,height:row.image.height,caption:row.caption};
    if(Object.hasOwn(entity,'image'))entity.image=row.image.imageUrl;
    changed=true;
   }
  }
  if(changed)add(script,chunk.slice(0,open)+JSON.stringify(json).replaceAll('<','\\u003c')+chunk.slice(close));
 }
 edits.sort((a,b)=>b.start-a.start);let result=source,last=source.length;
 for(const e of edits){if(e.end>last)throw Error('Overlapping image changes: '+row.file);result=result.slice(0,e.start)+e.value+result.slice(e.end);last=e.start;}
 if(result!==source){fs.writeFileSync(file,result);report.changed++;}
}
console.log(JSON.stringify(report));
