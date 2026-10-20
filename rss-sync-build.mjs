/** Publish the current full article feed, guarded by the reviewed page inputs. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {fingerprint} from './media-placement-build.mjs';
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'.public-release');
const bytes=gunzipSync(fs.readFileSync(path.join(root,'rss-sync-review.json.gz')));
const summary=JSON.parse(fs.readFileSync(path.join(root,'rss-sync-summary.json'),'utf8'));
const digest=s=>createHash('sha256').update(s).digest('hex');
if(digest(bytes)!==summary.reviewSha256)throw Error('RSS review bundle differs');
const review=JSON.parse(bytes.toString('utf8'));let cursor=0;const pages=Object.entries(review.pages);
await Promise.all(Array.from({length:12},async()=>{while(cursor<pages.length){const [name,hash]=pages[cursor++];if(name.startsWith('/')||name.split('/').includes('..'))throw Error('Unsafe RSS input');if(fingerprint(await fs.promises.readFile(path.join(out,name),'utf8'))!==hash)throw Error('RSS body needs review after page change: '+name);}}));
const file=path.join(out,'rss.xml'),source=(await fs.promises.readFile(file,'utf8')).replaceAll('\r\n','\n');
const hash=digest(source);
if(![review.before,review.after].includes(hash)||digest(review.output)!==review.after)throw Error('Unreviewed RSS content');
if(Buffer.byteLength(review.output)>=10_000_000)throw Error('RSS exceeds official size limit');
if(process.argv.includes('--check')){if(hash!==review.after)throw Error('Current full feed has not been applied');}
else if(hash!==review.after)await fs.promises.writeFile(file,review.output);
console.log(JSON.stringify({rssItems:review.items.length,guardedPages:pages.length,fullCurrentBodies:true,publicationDatesPreserved:true,bytes:Buffer.byteLength(review.output),check:process.argv.includes('--check')}));
