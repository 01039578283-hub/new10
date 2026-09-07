"""Non-mutating local/public release checks for site10 title changes."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import unquote, quote
from pathlib import Path
import xml.etree.ElementTree as ET

from personalize_title_suffixes import (
    ROOT, DOMAIN, BASELINE_COMMIT, EXPECTED_TARGETS, EXPECTED_HTML, EXPECTED_SITEMAP, EXPECTED_NOINDEX, REPORT,
    META_RE, attrs, clean, title_of, masked, sha, eligible, learning_blocks,
    update_rss,
)
from title_suffix_rules import HUB_SUFFIXES
from add_subject_anchor_tocs import validate_page as validate_toc

PRIVATE_FILES = {
    "PROJECT_HANDOFF.md": "9a0fe461090e89ae349ceb580105187f36c7b8b6151990076ecd0cc059a670b5",
    "CHAT_HISTORY_2026-07-03.md": "97440684cc053ed4f62044725fd796efd9d01e53746d840ba8d4d55400d11b56",
}

NORM = lambda data: data.replace(b"\r\n", b"\n")

class GitBaseline:
    """Read fixed-commit blobs without thousands of Git subprocesses."""
    def __enter__(self):
        self.process = subprocess.Popen(["git","cat-file","--batch"],cwd=ROOT,
                                        stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        return self
    def read(self,path):
        self.process.stdin.write((BASELINE_COMMIT+":"+path+"\n").encode("utf-8"))
        self.process.stdin.flush()
        header = self.process.stdout.readline().split()
        if len(header)!=3 or header[1]!=b"blob":
            raise ValueError("Missing baseline blob: "+path)
        data = self.process.stdout.read(int(header[2]))
        if self.process.stdout.read(1)!=b"\n":
            raise ValueError("Git batch protocol")
        return data
    def __exit__(self,*unused):
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.wait(timeout=15)

def verify_source(row,source,public=False):
    errors=[]
    if title_of(source)!=row["after"]:
        errors.append("title mismatch")
    if row["after"].split("|",1)[0].rstrip()!=row["before"].split("|",1)[0].rstrip():
        errors.append("title prefix changed")
    expected_hash=row["unchangedNormalizedContentSha256"] if public else row["unchangedContentSha256"]
    body=masked(source).replace("\r\n","\n") if public else masked(source)
    if sha(body)!=expected_hash:
        errors.append("non-title content changed")
    if len(re.findall(r"<h1\b",source,re.I))!=1:
        errors.append("H1 count is not one")
    for tag in META_RE.finditer(source):
        values=attrs(tag[0])
        if values.get("property",values.get("name")) in {"og:title","twitter:title"}:
            if values.get("content")!=row["after"]:
                errors.append("social title mismatch")
    canonical=[attrs(m[0]).get("href") for m in re.finditer(r"<link\b[^>]*>",source,re.I) if attrs(m[0]).get("rel")=="canonical"]
    if canonical!=[row["canonical"]]:
        errors.append("canonical changed")
    robots=[attrs(m[0]).get("content","") for m in META_RE.finditer(source) if attrs(m[0]).get("name")=="robots"]
    if len(robots)!=1 or ("noindex" not in robots[0].lower())!=row["indexable"]:
        errors.append("indexing policy changed")
    nodes=[]
    for match in re.finditer(r"""<script\b[^>]*type=["']application/ld\+json["'][^>]*>(.*?)</script>""",source,re.I|re.S):
        parsed=json.loads(match[1])
        nodes.extend(parsed if isinstance(parsed,list) else parsed.get("@graph",[parsed]))
    main=re.search(r"<main\b[^>]*>(.*?)</main>",source,re.S)
    visible=re.sub(r"\s+","",clean(main[1])) if main else ""
    if row["kind"]!="category":
        blocks=learning_blocks(source,row["kind"])
        allowed=[re.sub(r"\s+","",b["text"]) for b in blocks]
        if row["suffix"]!="·".join(e["label"] for e in row["evidence"]):
            errors.append("suffix evidence labels differ")
    else:
        suffix,terms=HUB_SUFFIXES[row["group"]]
        if row["suffix"]!=suffix:
            errors.append("hub suffix mismatch")
        allowed=[visible]
    for evidence in row["evidence"]:
        excerpt=re.sub(r"\s+","",evidence["excerpt"])
        if excerpt not in visible or not any(excerpt in b for b in allowed):
            errors.append("evidence outside eligible main copy")
        if evidence["match"] not in evidence["excerpt"]:
            errors.append("recorded match absent from excerpt")
        if row["kind"]!="category" and not eligible(row,evidence["label"],evidence["subject"]):
            errors.append("grade/subject mismatch")
    if row["kind"]=="subject":
        errors.extend(validate_toc(source))
    return errors

def public_samples(entries):
    groups=defaultdict(list)
    selected={}
    for row in entries:
        groups[row["group"]+"/"+row["kind"]].append(row)
    for rows in groups.values():
        for index in sorted({0,len(rows)//2,len(rows)-1}):
            selected[rows[index]["path"]]=rows[index]
        for indexable in (True,False):
            match=next((r for r in rows if r["indexable"]==indexable),None)
            if match:
                selected[match["path"]]=match
    for row in entries:
        if "명일동" in row["path"] or row["kind"]=="category":
            selected[row["path"]]=row
    return list(selected.values())

def fetch(url):
    request=Request(url,headers={"User-Agent":"Site10-Title-Release-Check/1.0"})
    with urlopen(request,timeout=35) as response:
        if response.status!=200:
            raise ValueError("HTTP "+str(response.status))
        if unquote(response.url).rstrip("/")!=unquote(url).rstrip("/"):
            raise ValueError("unexpected redirect")
        return response.read(),response.headers.get("Content-Type","")

def discovery(report,public):
    errors=[]
    counts={}
    for name in (["sitemap.xml","rss.xml"] if report["rssExists"] else ["sitemap.xml"]):
        local=(ROOT/name).read_bytes()
        if public:
            data,_=fetch(DOMAIN+"/"+name)
            if NORM(data)!=NORM(local):
                errors.append(name+" differs from verified local source")
        else:
            data=local
        xml=ET.fromstring(data)
        items=xml.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url") if name=="sitemap.xml" else xml.findall(".//item")
        expected=report["sitemapCount"] if name=="sitemap.xml" else report["rssCount"]
        if len(items)!=expected:
            errors.append(name+" count mismatch")
        counts[name]=dict(items=len(items),publicHttpStatus=200 if public else None)
        if name=="sitemap.xml":
            urls=[unquote(item.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc","")) for item in items]
            expected_urls={unquote(row["url"]) for row in report["entries"] if row["indexable"]}
            for path in report["protectedHtml"]:
                route="/" if path=="index.html" else "/"+Path(path).parent.as_posix()+"/"
                expected_urls.add(DOMAIN+route)
            if len(urls)!=len(set(urls)) or set(urls)!=expected_urls:
                errors.append("sitemap differs from the existing indexable-page inventory")
            counts[name]["noindexPagesExcluded"]=report["noindexCount"]
        if name=="rss.xml":
            titles={unquote(x["url"]):x["after"] for x in report["entries"]}
            synced=0
            for item in items:
                key=unquote(item.findtext("link",""))
                if key in titles:
                    synced+=1
                    if item.findtext("title")!=titles[key]:
                        errors.append("RSS title mismatch")
            counts[name]["targetTitles"]=synced
    if not report["rssExists"] and (ROOT/"rss.xml").exists():
        errors.append("RSS was unexpectedly created")
    return errors,counts

def check_baseline(report):
    errors=[]
    with GitBaseline() as baseline:
        for row in report["entries"]:
            original=baseline.read(row["path"]).decode("utf-8")
            if title_of(original)!=row["before"]:
                errors.append(row["path"]+": before title differs from fixed Git baseline")
            if sha(masked(original).replace("\r\n","\n"))!=row["unchangedNormalizedContentSha256"]:
                errors.append(row["path"]+": non-title bytes differ from fixed Git baseline")
        protected=report["protectedHtml"]+["sitemap.xml","robots.txt","llms.txt"]
        for path in protected:
            if NORM((ROOT/path).read_bytes())!=NORM(baseline.read(path)):
                errors.append(path+": protected file changed")
        if report["rssExists"]:
            original_rss=baseline.read("rss.xml").decode("utf-8")
            updated,_=update_rss([dict(url=x["url"],after=x["after"]) for x in report["entries"]],original_rss)
            if updated.replace("\r\n","\n")!=(ROOT/"rss.xml").read_bytes().decode("utf-8").replace("\r\n","\n"):
                errors.append("RSS changes outside matching item titles")
    if (ROOT/"vercel.json").exists():
        errors.append("Unexpected deployment configuration was created")
    for name, expected in PRIVATE_FILES.items():
        file = ROOT/name
        if not file.is_file() or __import__("hashlib").sha256(file.read_bytes()).hexdigest() != expected:
            errors.append(name + ": private initial file was modified")
        tracked = subprocess.run(["git","ls-files","--error-unmatch","--",name],
                                 cwd=ROOT,capture_output=True)
        if tracked.returncode == 0:
            errors.append(name + ": private initial file was staged")
        if name not in (ROOT/".vercelignore").read_text(encoding="utf-8").splitlines():
            errors.append(name + ": missing deployment exclusion")
    return errors

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--public",action="store_true")
    args=parser.parse_args()
    report=json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["site"]==DOMAIN
    assert len(report["entries"])==EXPECTED_TARGETS
    assert len({r["after"] for r in report["entries"]})==EXPECTED_TARGETS
    assert report["sitemapCount"]==EXPECTED_SITEMAP
    assert report["noindexCount"]==EXPECTED_NOINDEX
    rows=public_samples(report["entries"]) if args.public else report["entries"]
    def check(row):
        try:
            if args.public:
                data,content_type=fetch(row["url"])
                if "text/html" not in content_type:
                    raise ValueError("not HTML")
            else:
                data=(ROOT/row["path"]).read_bytes()
            source=data.decode("utf-8")
            return dict(path=row["path"],url=row["url"],title=title_of(source),httpStatus=200 if args.public else None,
                        errors=verify_source(row,source,args.public))
        except Exception as exc:
            return dict(path=row["path"],url=row["url"],errors=[str(exc)])
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(check,rows))
    failures=[r for r in results if r["errors"]]
    global_errors=[] if args.public else check_baseline(report)
    xml_errors,counts=discovery(report,args.public)
    global_errors.extend(xml_errors)
    output=dict(mode="public" if args.public else "local",checked=len(results),failures=len(failures),
                globalErrors=global_errors,discovery=counts,tocPagesChecked=sum(r["kind"]=="subject" for r in rows),checkedAt=datetime.now(timezone.utc).isoformat(),results=results)
    REPORT.with_name("title-suffix-"+output["mode"]+"-verification.json").write_text(
        json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({k:v for k,v in output.items() if k not in {"results","legacyAudits"}},ensure_ascii=False))
    for failure in failures[:10]:
        print(json.dumps(failure,ensure_ascii=False))
    if failures or global_errors:
        raise SystemExit(1)
    print("TITLE_RELEASE_"+output["mode"].upper()+"_PASS")

if __name__=="__main__":
    main()
