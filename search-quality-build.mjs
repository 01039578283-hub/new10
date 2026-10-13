/** Apply reviewed navigation, practice examples and consistent entity references. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {parseHTML} from './image-order-build.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'.public-release');
const review=JSON.parse(fs.readFileSync(path.join(root,'search-quality-review.json'),'utf8'));
const marker='data-search-quality="20261013"';
// The preceding favicon stage may run last. Exclude only those icon tags from
// the reviewed HTML fingerprint; all other input must match the reviewed page.
const sourceFingerprint=s=>createHash('sha256').update(s.replaceAll('\r\n','\n').replace(/<link\b[^>]*>/gi,t=>{const rel=t.match(/\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i);return /^(?:icon|shortcut icon|apple-touch-icon|apple-touch-icon-precomposed)$/i.test((rel?.[1]??rel?.[2]??rel?.[3]??'').trim())?'':t;})).digest('hex');
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const plain=s=>s.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
const ancestors=n=>{const p=[];for(let x=n.parent;x;x=x.parent)p.push(x);return p;};
const canonicalId=v=>{try{const u=new URL(v);if(u.origin!==review.base)return v;return u.origin+u.pathname.split('/').map(p=>encodeURIComponent(decodeURIComponent(p))).join('/')+u.search+(u.hash?'#'+encodeURIComponent(decodeURIComponent(u.hash.slice(1))):'');}catch{return v;}};
const localPath=v=>{try{return decodeURIComponent(new URL(v,review.base).pathname)}catch{return ''}};
const legacy=new Map(Object.entries(review.legacyIds).map(([k,v])=>[canonicalId(k),canonicalId(v)]));
const stats={pages:0,changed:0,bodyChanged:0,schemaChanged:0,nearbyPages:0,branchNavigationPages:0,practicePages:0,tuitionFAQPages:0,curriculumLinkPages:0,normalizedIds:0,centerReferences:0,changedFiles:[],bodyFiles:[]};
const branchStyle='<style data-search-quality-style="20261013">.sq-grade-routes{display:grid;gap:14px;margin-top:18px}.sq-area{min-width:0}.sq-area h4{margin:0 0 10px}.sq-area nav{display:flex;flex-wrap:wrap;gap:8px}.sq-area a{box-sizing:border-box;display:inline-flex;align-items:center;min-height:44px;padding:10px 12px;border:1px solid #d6dfda;border-radius:10px;text-decoration:none;background:#f8fbf9;color:#1b4635}.sq-area a:hover,.sq-area a:focus-visible{background:#e8f3ec;outline:2px solid #456b56;outline-offset:2px}.sq-example{margin-top:20px;padding-top:16px;border-top:1px solid #d6dfda}.sq-example p{overflow-wrap:anywhere}.sq-example h3{margin-top:0}@media(max-width:480px){.sq-area a{flex:1 1 42%;justify-content:center}}</style>';
const modified=new Set();
for(const name of Object.keys(review.pageHashes)){
 const file=path.join(out,name),source=fs.readFileSync(file,'utf8');stats.pages++;
 if(source.includes(marker))continue;
 if(sourceFingerprint(source)!==review.pageHashes[name])throw Error('Unreviewed source HTML '+name);
 const row=review.pages[name]||{},nodes=parseHTML(source),edits=[];let body=false;
 const replace=(n,value)=>edits.push({start:n.start,end:n.end,value});
 if(row.nearbyLinks){
  const olds=nodes.filter(n=>n.tag==='a'&&plain(source.slice(n.start,n.end)).includes('같은 시도 인근 지역'));
  if(olds.length!==row.oldNearbyCount)throw Error('Nearby source changed '+name);
  const replacement=row.nearbyLinks.map(a=>`<a href="${esc(a.href)}"><strong>${esc(a.text)}</strong><small>${esc(a.detail)}</small></a>`).join('');
  olds.forEach((n,i)=>replace(n,i?'':replacement));
  const sec=ancestors(olds[0]).find(n=>n.tag==='section');
  if(!sec)throw Error('Missing nearby section '+name);
  for(const h of nodes.filter(n=>n.tag==='h2'&&ancestors(n).includes(sec))){const s=source.slice(h.start,h.end);replace(h,s.replace('관련 학년·과목과 인근 지역','학년·과목 안내와 지점 비교'));}
  for(const p of nodes.filter(n=>n.tag==='p'&&ancestors(n).includes(sec))){const s=source.slice(p.start,p.end);if(s.includes('같은 지역의 다른 학년·과목과 가까운 지역 페이지를 구분해 연결했습니다.'))replace(p,s.replace('같은 지역의 다른 학년·과목과 가까운 지역 페이지를 구분해 연결했습니다.','현재 동네의 다른 학년·과목을 먼저 살펴보고, 실제 지점 주소를 비교해 보세요.'));}
  body=true;stats.nearbyPages++;
 }
 if(row.gradeGroups?.length){
  const old=nodes.find(n=>n.tag==='section'&&n.attrs.class==='cu-subsection'&&source.slice(n.start,n.end).includes('<h3 style="margin-top:24px">학년별 상담 방향</h3>'));
  const learning=nodes.find(n=>n.tag==='section'&&n.attrs.id==='learning');
  if(!old&&(name!=='지점안내/강원/석사점/index.html'||!learning))throw Error('Missing branch grade navigation '+name);
  const groups=row.gradeGroups.map(g=>`<div class="cu-subsection sq-area"><h4>${esc(g.area)} 학년별 안내</h4><nav aria-label="${esc(g.area)} 학년별 상담 준비">${g.links.map(a=>`<a href="${esc(a.href)}">${esc(a.text)}</a>`).join('')}</nav></div>`).join('');
  // Retain original learning-method links below the local route navigation.
  const original=old?source.slice(old.start,old.end).replace('<h3 style="margin-top:24px">학년별 상담 방향</h3>','<h3 style="margin-top:24px">학습 방법 전체 목록</h3>'):'';
  const replacement=`<section class="cu-subsection" id="grade-consultation"><h3>동네·학년별 상담 준비</h3><p>아래는 ${esc(row.branchName)} 안내에 연결된 동네별 자료입니다. 현재 학년의 학습 점검과 방문 정보를 함께 읽어 보세요. 안내 페이지가 있다는 뜻이며, 현재 모집과 수업 시간표는 위의 과목별 범위와 지점 상담에서 확인합니다.</p><div class="sq-grade-routes">${groups}</div></section>${original}`;
  if(old)replace(old,replacement);else edits.push({start:learning.closeStart,end:learning.closeStart,value:replacement});
  body=true;stats.branchNavigationPages++;
 }
 if(row.practice){
  const sec=nodes.find(n=>n.attrs.id==='practice-task');if(!sec)throw Error('Missing practice section '+name);
  const [title,question,answer,next,check]=row.practice.content;
  const block=`<div class="sq-example" data-practice-example="20261013"><h3>${esc(title)}</h3><p>아래는 직접 만든 학습 연습 예시입니다. 학교 시험 문제나 실제 학생 사례가 아니며, 현재 배우는 단원에 맞춰 활용하세요.</p><p><strong>먼저 해보기</strong> ${esc(question)}</p><p><strong>풀이와 확인</strong> ${esc(answer)}</p><p><strong>조건을 바꿔 다시 해보기</strong> ${esc(next)}</p><p><strong>학생·학부모 확인 기준</strong> ${esc(check)}</p></div>`;
  edits.push({start:sec.closeStart,end:sec.closeStart,value:block});body=true;stats.practicePages++;
 }
 // Point to the expanded examples using descriptive text, without changing any URL.
 let linksChanged=0;
 for(const n of nodes.filter(n=>n.tag==='a'&&ancestors(n).some(p=>p.attrs.id==='study-curriculum-reading'))){
  const parts=localPath(n.attrs.href).split('/').filter(Boolean);
  if(parts[0]!=='공부커리큘럼'||parts.length!==3||!['수학','영어'].includes(parts[2]))continue;
  const original=source.slice(n.start,n.end);
  if(!original.includes('학습 순서 보기'))continue;
  replace(n,original.replace('학습 순서 보기',parts[2]==='수학'?'학습 순서·풀이 예제 보기':(['초1','초2'].includes(parts[1])?'학습 순서·소리 연습 보기':'학습 순서·문장 연습 보기')));linksChanged++;
 }
 if(linksChanged){body=true;stats.curriculumLinkPages++;}
 edits.sort((a,b)=>b.start-a.start);let html=source,last=source.length;
 for(const e of edits){if(e.end>last)throw Error('Overlapping page changes '+name);html=html.slice(0,e.start)+e.value+html.slice(e.end);last=e.start;}
 if(row.tuitionFAQ){const old='페이지의 교육비 표는 지역 공통 참고 금액을 구분해 표시했습니다.';if(!html.includes(old))throw Error('Missing tuition answer '+name);html=html.replaceAll(old,row.tuitionFAQ);body=true;stats.tuitionFAQPages++;}
 let schemaChanged=false;
 const related=(()=>{if(!row.nearbyLinks)return null;const ns=parseHTML(html),sec=ns.find(n=>n.tag==='section'&&plain(html.slice(n.start,n.end)).includes('현재 동네의 다른 학년·과목을 먼저 살펴보고, 실제 지점 주소를 비교해 보세요.'));if(!sec)throw Error('Missing replacement related section');return ns.filter(n=>n.tag==='a'&&ancestors(n).includes(sec)).map(n=>({name:plain(html.slice(n.start,n.end)),url:new URL(n.attrs.href,review.base).href}));})();
 html=html.replace(/<script\b([^>]*\btype\s*=\s*["']application\/ld\+json["'][^>]*)>([\s\S]*?)<\/script\s*>/gi,(whole,attrs,json)=>{
  const data=JSON.parse(json),before=JSON.stringify(data);
  function walk(v){
   if(Array.isArray(v)){v.forEach(walk);return;}
   if(!v||typeof v!=='object')return;
   if(typeof v['@id']==='string'){
    const id=canonicalId(v['@id']),samePage=localPath(id)===localPath('/'+name.replace(/index\.html$/,''));
    let next=legacy.get(id)||id;
    if(row.centerId&&!v['@type']&&samePage&&new URL(id).hash==='#organization')next=canonicalId(row.centerId);
    if(next!==v['@id']){if(next===canonicalId(row.centerId||''))stats.centerReferences++;else stats.normalizedIds++;v['@id']=next;}
   }
   const types=Array.isArray(v['@type'])?v['@type']:[v['@type']];
   if(related&&types.includes('ItemList')&&v['@id']?.endsWith('#related')){v.itemListElement=related.map((a,i)=>({'@type':'ListItem',position:i+1,name:a.name,url:a.url}));if('numberOfItems' in v)v.numberOfItems=related.length;}
   if(body&&types.some(t=>['WebPage','Article','CollectionPage'].includes(t))){const url=v.url||v['@id'];if(url&&localPath(url)===localPath('/'+name.replace(/index\.html$/,'')))v.dateModified=review.date;}
   Object.values(v).forEach(walk);
  }
  walk(data);if(JSON.stringify(data)===before)return whole;schemaChanged=true;return `<script${attrs}>${JSON.stringify(data).replaceAll('<','\\u003c')}</script>`;
 });
 if(body){
  html=html.replace(/<p\b[^>]*class="[^"]*\bbranch-meta\b[^"]*"[^>]*>[\s\S]*?<\/p>/g,p=>p.includes('내용 업데이트')?p.replace(/<time\b[^>]*>[\s\S]*?<\/time>/,'<time datetime="2026-10-13">2026년 10월 13일</time>'):p);
  if(row.practice)html=html.replace(/<p\b[^>]*class="cc-date"[^>]*>[\s\S]*?<\/p>/g,p=>p.replace(/<time\b[^>]*>[\s\S]*?<\/time>/,'<time datetime="2026-10-13">2026년 10월 13일</time>'));
  if(row.gradeGroups?.length||row.practice)html=html.replace('</head>',branchStyle+'</head>');
 }
 if(html!==source){html=html.replace(/<html\b/,`<html ${marker}`);fs.writeFileSync(file,html);stats.changed++;stats.changedFiles.push(name);modified.add(name);if(body){stats.bodyChanged++;stats.bodyFiles.push(name);}if(schemaChanged)stats.schemaChanged++;}
}
// Update only changed canonical pages; retain sitemap URL order and all other entries.
const sitemap=path.join(out,'sitemap.xml');let xml=fs.readFileSync(sitemap,'utf8');
xml=xml.replace(/<url>([\s\S]*?)<\/url>/g,(whole,inner)=>{const loc=inner.match(/<loc>([^<]+)<\/loc>/)?.[1];if(!loc)return whole;const file=decodeURIComponent(new URL(loc).pathname).slice(1)+'index.html';if(!modified.has(file))return whole;return /<lastmod>/.test(whole)?whole.replace(/<lastmod>[^<]*<\/lastmod>/,`<lastmod>${review.date}</lastmod>`):whole.replace('</url>',`<lastmod>${review.date}</lastmod></url>`);});
fs.writeFileSync(sitemap,xml);
if(process.env.SEARCH_QUALITY_REPORT)fs.writeFileSync(process.env.SEARCH_QUALITY_REPORT,JSON.stringify(stats,null,2));
console.log(JSON.stringify({...stats,changedFiles:undefined,bodyFiles:undefined}));
