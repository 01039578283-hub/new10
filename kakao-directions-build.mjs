/** Add reviewed, link-free directions below the existing map image. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseHTML} from './image-order-build.mjs';
import {fingerprint} from './media-placement-build.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const marker='data-kakao-directions="20261017"';
export function transform(source,row,review){
 if(source.includes(marker))return source;
 const nodes=parseHTML(source),main=nodes.find(n=>n.tag==='main');
 if(!main)throw Error('Missing page main');
 let position,section;
 if(row.kind==='detail'){
  const images=nodes.filter(n=>n.tag==='img'&&n.attrs['data-media-role']==='map');
  if(images.length!==1)throw Error('Existing map image is missing or ambiguous');
  let figure=images[0].parent;while(figure&&figure.tag!=='figure')figure=figure.parent;
  if(!figure)throw Error('Existing map figure requires review');
  let sequence=figure.parent;while(sequence&&sequence.attrs['data-image-order']!=='sequence-v1')sequence=sequence.parent;
  if(!sequence)throw Error('Map figure outside reviewed image sequence');
  const map=review.maps[row.branch];if(!map)throw Error('Missing verified branch map');
  position=figure.end;
  section='<section class="kakao-directions" id="kakao-directions" '+marker+' data-kakao-key="'+escape(map.key)+'" data-kakao-branch="'+escape(row.branch)+'"><h2>찾아오시는 길</h2>'+map.html+'</section>';
 }else if(row.kind==='hub'){
  if(!row.branches?.length)throw Error('Empty location hub');
  const first=row.branches[0];
  const options=row.branches.map(branch=>'<option value="'+escape(branch)+'" data-kakao-entry="'+escape(review.maps[branch].entry)+'">'+escape(branch)+'</option>').join('');
  position=main.closeStart;
  section='<section class="kakao-directions" id="kakao-directions-hub" '+marker+' data-kakao-hub><h2>지점별 찾아오시는 길</h2><label for="kakao-hub-branch">위치를 확인할 지점</label><select class="kd-hub-select" id="kakao-hub-branch" data-kakao-select data-selected="'+escape(first)+'">'+options+'</select><p class="kd-hub-status" role="status" aria-live="polite"></p><div class="kd-hub-panel">'+review.maps[first].html+'</div></section>';
 }else throw Error('Unknown map page role');
 let html=source.slice(0,position)+section+source.slice(position);
 html=html.replace(/<\/head\s*>/i,'<style data-kakao-style="20261017">'+review.style+'</style>$&');
 html=html.replace(/<\/body\s*>/i,'<script async data-kakao-loader="20261017" src="'+escape(review.loader)+'"></script>$&');
 // Match the existing final favicon pass so local and production bytes agree.
 html=html.replace(/<head\b[^>]*>[\s\S]*?<\/head>/i,head=>head.replace(/<link\b[^>]*>/gi,tag=>{
  const rel=tag.match(/\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i);
  return /^(?:icon|shortcut icon|apple-touch-icon|apple-touch-icon-precomposed)$/i.test((rel?.[1]??rel?.[2]??rel?.[3]??'').trim())?'':tag;
 }).replace(/<\/head>/i,'<link rel="icon" type="image/png" sizes="96x96" href="/assets/site-favicon.png"><link rel="apple-touch-icon" sizes="180x180" href="/assets/site-apple-touch-icon.png"></head>'));
 return html;
}
export function build(){
 const review=JSON.parse(fs.readFileSync(path.join(root,'kakao-directions-review.json'),'utf8'));
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'release-public-manifest.json'),'utf8'));
 for(const name of Object.keys(review.assets))if(!Object.hasOwn(manifest.files,name)||!fs.existsSync(path.join(root,'.public-release',name)))throw Error('Map asset outside reviewed release '+name);
 const stats={pages:0,changed:0,alreadyApplied:0,details:0,hubs:0,branchMaps:Object.keys(review.maps).length};
 for(const [name,row] of Object.entries(review.pages)){
  if(!Object.hasOwn(manifest.files,name))throw Error('Page outside release '+name);
  const file=path.join(root,'.public-release',name),source=fs.readFileSync(file,'utf8'),hash=fingerprint(source);
  if(hash!==row.before&&hash!==row.after)throw Error('Unreviewed source HTML '+name);
  const html=transform(source,row,review);
  if(fingerprint(html)!==row.after)throw Error('Unexpected directions output '+name);
  stats.pages++;stats[row.kind==='hub'?'hubs':'details']++;
  if(html!==source){fs.writeFileSync(file,html);stats.changed++;}else stats.alreadyApplied++;
 }
 return stats;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(build()));
