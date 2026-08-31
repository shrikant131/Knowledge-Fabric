"""GitHub connector with authentication-aware rate-limit handling and diagnostics."""
from __future__ import annotations
import base64, hashlib, os, re
from typing import Iterable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from knowledge_fabric.chunking.code_chunker import split_code_symbols
from knowledge_fabric.chunking.doc_chunker import split_doc_sections
from knowledge_fabric.connectors.base import SourceConnector
from knowledge_fabric.types import Chunk, ParsedDocument, RawItem

CODE_EXTENSIONS={".py":"python",".java":"java",".js":"javascript",".ts":"typescript",".go":"go"}
DOC_EXTENSIONS={".md":"markdown",".txt":"text",".rst":"text"}
IGNORE_DIRS={".git","node_modules","dist","build",".venv","venv","__pycache__"}
DEFAULT_MAX_FILE_BYTES=1_000_000

class GitHubConnector(SourceConnector):
    def __init__(self, owner, repo, source_id=None, ref=None, token_env_var="GITHUB_TOKEN", max_file_bytes=DEFAULT_MAX_FILE_BYTES, timeout=30, max_files=10000):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",owner) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",repo): raise ValueError("Invalid GitHub owner/repository name")
        self.owner,self.repo,self.source_id,self.ref=owner,repo,source_id or f"github:{owner}/{repo}",ref
        self.token_env_var=token_env_var; self.token=os.getenv(token_env_var)
        self.max_file_bytes,self.max_files,self.timeout=max_file_bytes,max_files,timeout
        self.session=requests.Session()
        retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=.5,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset(["GET"]),respect_retry_after_header=True)
        self.session.mount("https://",HTTPAdapter(max_retries=retry,pool_connections=10,pool_maxsize=10))
        self.session.headers.update({"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"Knowledge-Fabric/1.0"})
        if self.token: self.session.headers["Authorization"]=f"Bearer {self.token}"
        self.last_access={"authenticated":bool(self.token),"remaining":None,"limit":None,"reset":None,"rate_limited":False}
    @property
    def base(self): return f"https://api.github.com/repos/{self.owner}/{self.repo}"
    def connection_status(self):
        try:
            data=self._get(self.base)
            return {"ok":True,"authenticated":bool(self.token),"public":not bool(data.get("private")),"rate_limited":False,"remaining":self.last_access.get("remaining"),"limit":self.last_access.get("limit"),"message":"Authenticated GitHub access" if self.token else "Anonymous public GitHub access"}
        except Exception as e:
            return {"ok":False,"authenticated":bool(self.token),"rate_limited":self.last_access.get("rate_limited",False),"remaining":self.last_access.get("remaining"),"limit":self.last_access.get("limit"),"message":str(e)}
    def fetch(self)->Iterable[RawItem]:
        repo_info=self._get(self.base); ref=self.ref or repo_info.get("default_branch","main")
        commit=self._get(f"{self.base}/commits/{ref}"); sha=commit["sha"]
        tree=self._get(f"{self.base}/git/trees/{sha}?recursive=1")
        if tree.get("truncated"): raise RuntimeError("GitHub tree is truncated; choose a narrower path/ref")
        yielded=0
        for node in tree.get("tree",[]):
            if yielded>=self.max_files: break
            if node.get("type")!="blob": continue
            path=node.get("path","")
            if any(part in IGNORE_DIRS for part in path.split("/")): continue
            ext=os.path.splitext(path)[1].lower()
            if ext not in CODE_EXTENSIONS and ext not in DOC_EXTENSIONS: continue
            if int(node.get("size") or 0)>self.max_file_bytes: continue
            blob_sha=node.get("sha")
            if not blob_sha: continue
            blob=self._get(f"{self.base}/git/blobs/{blob_sha}")
            if blob.get("encoding")!="base64": continue
            try: content=base64.b64decode(blob["content"]).decode("utf-8",errors="ignore")
            except Exception: continue
            yielded+=1
            yield RawItem(source_id=self.source_id,item_id=path,content=content,content_type="code" if ext in CODE_EXTENSIONS else "doc",language=CODE_EXTENSIONS.get(ext) or DOC_EXTENSIONS.get(ext),source_hash=blob_sha,extra={"repo":f"{self.owner}/{self.repo}","ref":ref,"commit":sha,"blob_sha":blob_sha,"url":f"https://github.com/{self.owner}/{self.repo}/blob/{sha}/{path}"})
    def detect_delta(self,items,seen_hashes): return [item for item in items if seen_hashes.get(item.item_id)!=item.content_hash]
    def parse(self,item):
        sections=[(f"{s.kind}:{s.name}",s.text) for s in split_code_symbols(item.content,item.language or "")] if item.content_type=="code" else split_doc_sections(item.content)
        return ParsedDocument(item.source_id,item.item_id,item.content_type,item.language,sections,extra={"content_hash":item.content_hash,**item.extra})
    def chunk(self,doc):
        return [Chunk(chunk_id=hashlib.sha256(f"{doc.source_id}:{doc.item_id}:{i}".encode()).hexdigest()[:16],source_id=doc.source_id,item_id=doc.item_id,text=text,symbol=symbol,language=doc.language,content_hash=hashlib.sha256(text.encode()).hexdigest(),extra={"parent_content_hash":doc.extra.get("content_hash"),**{k:v for k,v in doc.extra.items() if k!="content_hash"}}) for i,(symbol,text) in enumerate(doc.sections) if text.strip()]
    def _get(self,url):
        response=self.session.get(url,timeout=self.timeout)
        self.last_access.update({"remaining":response.headers.get("X-RateLimit-Remaining"),"limit":response.headers.get("X-RateLimit-Limit"),"reset":response.headers.get("X-RateLimit-Reset")})
        if response.status_code in (403,429):
            remaining=response.headers.get("X-RateLimit-Remaining")
            if response.status_code==429 or remaining=="0" or "rate limit" in response.text.lower():
                self.last_access["rate_limited"]=True
                mode="authenticated" if self.token else "anonymous"
                hint=f"GitHub API rate limit reached ({mode})."
                if not self.token: hint += " Set GITHUB_TOKEN for authenticated access."
                raise RuntimeError(hint)
        if response.status_code>=400: raise RuntimeError(f"GitHub API {response.status_code}: {response.text[:300]}")
        return response.json()
