"""Knowledge Fabric admin control plane."""
from __future__ import annotations
import json, logging, os, re, sys, uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from flask import Flask, jsonify, redirect, render_template, request, url_for
from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.admin_config import AdminConfigStore
from knowledge_fabric.registry import ConnectorRegistry
from knowledge_fabric.triggers.multi_scheduler import MultiSourceScheduler
from knowledge_fabric.evaluation.live_benchmark import LiveBenchmarkStore, run_benchmark
from knowledge_fabric.evaluation.benchmark_studio import BenchmarkStudioStore, run_studio
from knowledge_fabric.security import Principal
from knowledge_fabric.web_security import WebSecurity, api_error
from knowledge_fabric.jobs import build_manager

logging.basicConfig(level=logging.INFO,format="%(levelname)s %(name)s: %(message)s")
app=Flask(__name__); security=WebSecurity(app)
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=os.getenv("KF_COOKIE_SECURE","0")=="1",MAX_CONTENT_LENGTH=int(os.getenv("KF_MAX_UPLOAD_BYTES",25*1024*1024)))
@app.context_processor
def _ctx(): return {"csrf_token":security.csrf(),"authenticated":security.authenticated(),"auth_mode":security.mode}
@app.after_request
def _headers(r):
    r.headers.setdefault("X-Content-Type-Options","nosniff"); r.headers.setdefault("X-Frame-Options","DENY"); r.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin"); r.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()"); return r
@app.before_request
def _guard():
    if request.path.startswith("/static/") or request.path=="/api/health": return None
    if request.method in {"POST","PUT","PATCH","DELETE"} and not security.require_csrf(): return api_error("CSRF validation failed",403)
    protected=request.path.startswith(("/admin","/api/admin","/sources","/evaluation")) or (request.path.startswith("/quick-start") and request.method!="GET")
    if request.path.startswith(("/playground","/api/playground")) and os.getenv("KF_PUBLIC_PLAYGROUND","1" if security.mode=="none" else "0")!="1": protected=True
    if protected and not security.authenticated(): return api_error("authentication required",401) if request.path.startswith("/api/") else redirect(url_for("login",next=request.path))
    if request.path.startswith("/api/") and not security.allow_rate(False): return api_error("rate limit exceeded",429)
registry=ConnectorRegistry(manifests_dir="./connectors_registry",status_path="./data/registry_status.json"); scheduler=MultiSourceScheduler(registry); admin_store=AdminConfigStore(); live_benchmarks=LiveBenchmarkStore(); benchmark_studio=BenchmarkStudioStore(); jobs=build_manager(); ASYNC_JOBS=os.getenv("KF_ASYNC_JOBS","0")=="1"
CONNECTOR_FIELDS={"file":[("root_path","Root path","./sample_data")],"github":[("repo","Repository (owner/name)","psf/requests"),("ref","Branch / ref","main"),("path","Optional path","")],"confluence":[("base_url","Base URL","https://yourcompany.atlassian.net"),("space_key","Space key","ENG"),("auth_env_var","Auth token env var","CONFLUENCE_API_TOKEN"),("user_email_env_var","User email env var","CONFLUENCE_USER_EMAIL")],"sharepoint":[("site_id","Site ID",""),("drive_id","Drive ID",""),("auth_env_var","Access token env var","SHAREPOINT_ACCESS_TOKEN")]}
def _github_parts(repo):
    p=(repo or "").strip().removeprefix("https://github.com/").removeprefix("http://github.com/").strip("/").split("/")
    if len(p)!=2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",x) for x in p): raise ValueError("GitHub repository must look like owner/name")
    return p
def _safe_int(v,d,lo,hi):
    try:return min(hi,max(lo,int(v)))
    except:return d
def _safe_float(v,d,lo,hi):
    try:return min(hi,max(lo,float(v)))
    except:return d
def _bootstrap_source(source_id="demo",display_name="Demo Knowledge",connector_type="file",options=None):
    cfg=PipelineConfig(source_id=source_id,display_name=display_name,connector_type=connector_type,connector_options=options or {"root_path":"./sample_data"},embedder="local",generator="mock",llm_enabled=False,enable_reranker=True,enable_query_expansion=True,enable_self_rag=True,enable_cache=True); registry.register(cfg); return cfg
def _ensure_demo():
    if not registry.list_sources():
        c=_bootstrap_source()
        try: registry.record_run(c.source_id,registry.build_pipeline(c.source_id).ingest())
        except Exception as e: registry.record_run(c.source_id,None,error=str(e))
def _rows(): return [{"cfg":c,"status":registry.get_status(c.source_id),"running":scheduler.is_running(c.source_id)} for c in registry.list_sources()]
def _system_summary():
    rows=_rows(); return {"sources":len(rows),"watching":sum(r["running"] for r in rows),"chunks":sum((r["status"].last_result or {}).get("total_chunks",0) for r in rows),"errors":sum(bool(r["status"].last_error) for r in rows),"llm_enabled":sum(r["cfg"].effective_llm_enabled() for r in rows)}

@app.get("/login")
def login():
    if security.authenticated(): return redirect(request.args.get("next") or url_for("playground"))
    return render_template("login.html",next=request.args.get("next","/admin"))
@app.post("/login")
def login_post():
    if not security.login(request.form.get("api_key","")): return render_template("login.html",next=request.form.get("next","/admin"),error="Invalid credentials"),401
    return redirect(request.form.get("next") or url_for("admin_console"))
@app.post("/logout")
def logout(): security.logout(); return redirect(url_for("playground"))
@app.get("/playground")
def playground(): return render_template("playground.html",rows=_rows(),summary=_system_summary())
@app.get("/quick-start")
def quick_start(): return render_template("quick_start.html",connector_types=list(CONNECTOR_FIELDS))
@app.post("/quick-start/demo")
def quick_demo():
    c=registry.get_source("demo") or _bootstrap_source()
    try:r=registry.build_pipeline(c.source_id).ingest(); registry.record_run(c.source_id,r); return jsonify({"ok":True,"source_id":c.source_id,"result":r})
    except Exception as e: registry.record_run(c.source_id,None,error=str(e)); return jsonify({"ok":False,"error":str(e)}),500
@app.post("/quick-start/files")
def quick_files():
    root=request.form.get("root_path","").strip(); uploads=request.files.getlist("files")
    if uploads and any(f.filename for f in uploads):
        d=Path(os.getenv("KF_DATA_DIR","./data"))/"quick_uploads"; d.mkdir(parents=True,exist_ok=True)
        for f in uploads:
            if f.filename: f.save(d/(uuid.uuid4().hex[:12]+"-"+Path(f.filename).name))
        root=str(d)
    c=_bootstrap_source("quick-files","Uploaded / Local Files","file",{"root_path":root or "./sample_data"})
    try:r=registry.build_pipeline(c.source_id).ingest(); registry.record_run(c.source_id,r); return jsonify({"ok":True,"source_id":c.source_id,"result":r})
    except Exception as e: registry.record_run(c.source_id,None,error=str(e)); return jsonify({"ok":False,"error":str(e)}),500
@app.post("/quick-start/github")
def quick_github():
    try:o,r=_github_parts(request.form.get("repo",""))
    except ValueError as e:return jsonify({"ok":False,"error":str(e)}),400
    sid=f"github-{o}-{r}".lower().replace(".","-"); c=_bootstrap_source(sid,f"GitHub · {o}/{r}","github",{"owner":o,"repo":r,"ref":request.form.get("ref") or None,"token_env_var":"GITHUB_TOKEN"})
    try:res=registry.build_pipeline(c.source_id).ingest(); registry.record_run(c.source_id,res); return jsonify({"ok":True,"source_id":c.source_id,"result":res})
    except Exception as e: registry.record_run(c.source_id,None,error=str(e)); return jsonify({"ok":False,"error":str(e)}),502

def _principal():
    p=security.principal(); return Principal(user_id=p["user_id"],groups=frozenset(p["groups"]),tenant_id=p["tenant_id"],authenticated=p["authenticated"])
@app.post("/api/playground/query")
def playground_query():
    p=request.get_json(silent=True) or {}; sid=p.get("source_id") or (registry.list_sources()[0].source_id if registry.list_sources() else None); q=(p.get("question") or "").strip()
    if not sid or not q:return jsonify({"error":"source_id and question are required"}),400
    try:return jsonify(registry.build_pipeline(sid).query(q,principal=_principal()))
    except Exception as e:return jsonify({"error":str(e)}),500

@app.get("/")
def root():return redirect(url_for("playground"))
@app.get("/admin")
def admin_console():return render_template("admin_console.html",rows=_rows(),connector_types=list(CONNECTOR_FIELDS),summary=_system_summary(),env_status={k:bool(os.getenv(k)) for k in ["OPENAI_API_KEY","AWS_ACCESS_KEY_ID","AWS_PROFILE","GITHUB_TOKEN","CONFLUENCE_API_TOKEN","SHAREPOINT_ACCESS_TOKEN"]})
@app.get("/sources/new")
def new_source_form():
    t=request.args.get("connector_type","file"); return render_template("new_source.html",connector_types=list(CONNECTOR_FIELDS),selected_type=t,fields=CONNECTOR_FIELDS[t])
@app.post("/sources")
def create_source():
    f=request.form; t=f.get("connector_type",""); sid=f.get("source_id","").strip()
    if t not in CONNECTOR_FIELDS or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",sid):return "Invalid source",400
    opts={k:f.get(k,"") for k,_,_ in CONNECTOR_FIELDS[t]}
    if t=="github":
        o,r=_github_parts(opts["repo"]); opts={"owner":o,"repo":r,"ref":opts.get("ref") or None,"path":opts.get("path",""),"token_env_var":"GITHUB_TOKEN"}
    c=PipelineConfig(source_id=sid,display_name=f.get("display_name","").strip(),connector_type=t,connector_options=opts,trigger_type=f.get("trigger_type","scheduler"),poll_interval_seconds=_safe_int(f.get("poll_interval_seconds",60),60,5,86400),embedder=f.get("embedder","local"),generator=f.get("llm_provider","bedrock") if f.get("llm_enabled")=="1" else "mock",llm_enabled=f.get("llm_enabled")=="1",llm_provider=f.get("llm_provider","bedrock"),bedrock_region=f.get("bedrock_region","us-east-1"),bedrock_chat_model=f.get("bedrock_chat_model") or PipelineConfig.bedrock_chat_model,openai_chat_model=f.get("openai_chat_model") or PipelineConfig.openai_chat_model,enable_reranker=f.get("enable_reranker","1")=="1")
    registry.register(c); return redirect(url_for("admin_console"))
@app.post("/sources/<source_id>/delete")
def delete_source(source_id):scheduler.stop_source(source_id);registry.unregister(source_id);return redirect(url_for("admin_console"))
def _run_ingest_job(sid):
    try:r=registry.build_pipeline(sid).ingest();registry.record_run(sid,r);return r
    except Exception as e:registry.record_run(sid,None,error=str(e));raise
@app.post("/sources/<source_id>/ingest")
def ingest_now(source_id):
    try:r=_run_ingest_job(source_id);return jsonify(r) if request.is_json else redirect(url_for("admin_console"))
    except Exception as e:return jsonify({"error":str(e)}),500
@app.post("/sources/<source_id>/watch/start")
def start_watch(source_id):scheduler.start_source(source_id);registry.set_watching(source_id,True);return redirect(url_for("admin_console"))
@app.post("/sources/<source_id>/watch/stop")
def stop_watch(source_id):scheduler.stop_source(source_id);registry.set_watching(source_id,False);return redirect(url_for("admin_console"))
@app.route("/sources/<source_id>/query",methods=["GET","POST"])
def query_source(source_id):
    result=None; question=""
    if request.method=="POST":question=request.form.get("question","");result=registry.build_pipeline(source_id).query(question,principal=_principal())
    return render_template("query.html",cfg=registry.get_source(source_id),question=question,answer=result["answer"] if result else None,retrieved=result["retrieved"] if result else [],result=result)
@app.get("/api/sources")
def api_sources():return jsonify([{"source_id":r["cfg"].source_id,"display_name":r["cfg"].display_name,"type":r["cfg"].connector_type,"watching":r["running"],"last_run":r["status"].last_run_at,"last_error":r["status"].last_error,"last_result":r["status"].last_result} for r in _rows()])
@app.get("/api/jobs")
def api_jobs():return jsonify({"jobs":jobs.store.list(max(1,min(100,int(request.args.get("limit",50)))) )})
@app.get("/api/health")
def api_health():return jsonify({"status":"ok","async_jobs":ASYNC_JOBS,**_system_summary()})
@app.post("/api/sources/<source_id>/query")
def api_query(source_id):
    q=(request.get_json(silent=True) or {}).get("question","")
    if not q:return jsonify({"error":"question is required"}),400
    try:return jsonify(registry.build_pipeline(source_id).query(q,principal=_principal()))
    except Exception as e:return jsonify({"error":str(e)}),500
@app.post("/api/sources/<source_id>/llm")
def api_llm(source_id):
    c=registry.get_source(source_id)
    if not c:return jsonify({"error":"source not found"}),404
    p=request.get_json(silent=True) or {};c.llm_enabled=bool(p.get("enabled"));c.llm_provider=p.get("provider",c.llm_provider);c.generator=c.llm_provider if c.llm_enabled else "mock";registry.register(c)
    try:g=registry.build_pipeline(source_id).generator;return jsonify({"enabled":c.llm_enabled,"provider":c.llm_provider,"ready":bool(g.health()) if hasattr(g,"health") else c.llm_enabled})
    except Exception as e:return jsonify({"enabled":c.llm_enabled,"provider":c.llm_provider,"ready":False,"error":str(e)}),400
@app.get("/sources/<source_id>/settings")
def source_settings(source_id):return render_template("settings.html",cfg=registry.get_source(source_id))
@app.post("/sources/<source_id>/settings")
def save_settings(source_id):
    c=registry.get_source(source_id)
    if not c:return "Not found",404
    f=request.form;c.llm_enabled=f.get("llm_enabled")=="1";c.llm_provider=f.get("llm_provider",c.llm_provider);c.generator=c.llm_provider if c.llm_enabled else "mock";c.bedrock_region=f.get("bedrock_region",c.bedrock_region);c.bedrock_chat_model=f.get("bedrock_chat_model",c.bedrock_chat_model);c.openai_chat_model=f.get("openai_chat_model",c.openai_chat_model);c.openai_api_key_env=f.get("openai_api_key_env",c.openai_api_key_env);c.enable_reranker=f.get("enable_reranker")=="1";c.enable_query_expansion=f.get("enable_query_expansion")=="1";c.enable_cache=f.get("enable_cache")=="1";c.enable_self_rag=f.get("enable_self_rag")=="1";c.top_k=_safe_int(f.get("top_k"),c.top_k,1,50);c.max_tokens=_safe_int(f.get("max_tokens"),c.max_tokens,100,10000);c.max_agent_steps=_safe_int(f.get("max_agent_steps"),c.max_agent_steps,1,10);c.max_context_chars=_safe_int(f.get("max_context_chars"),c.max_context_chars,1000,100000);c.cache_similarity_threshold=_safe_float(f.get("cache_similarity_threshold"),c.cache_similarity_threshold,.5,1);c.public_access=f.get("public_access","1")=="1";c.allowed_users=[x.strip() for x in f.get("allowed_users","").split(",") if x.strip()];c.allowed_groups=[x.strip() for x in f.get("allowed_groups","").split(",") if x.strip()];c.confidence_threshold=_safe_float(f.get("confidence_threshold"),c.confidence_threshold,0,1);c.reranker_weight=_safe_float(f.get("reranker_weight"),c.reranker_weight,0,2);c.symbol_match_weight=_safe_float(f.get("symbol_match_weight"),c.symbol_match_weight,0,10);registry.register(c);return redirect(url_for("admin_console")+"#ai")

@app.get("/api/admin/summary")
def api_admin_summary():return jsonify(_system_summary())
@app.get("/api/admin/config/<source_id>")
def api_config(source_id):
    c=registry.get_source(source_id);return jsonify(c.to_yaml_dict()) if c else (jsonify({"error":"source not found"}),404)
@app.post("/api/admin/source/<source_id>/settings")
def api_source_settings(source_id):
    c=registry.get_source(source_id)
    if not c:return jsonify({"error":"source not found"}),404
    p=request.get_json(silent=True) or {}
    for k in ("top_k","max_tokens","max_agent_steps","max_context_chars","confidence_threshold","cache_similarity_threshold","reranker_weight","symbol_match_weight","enable_reranker","enable_query_expansion","enable_cache","enable_self_rag","llm_enabled","llm_provider","bedrock_region","bedrock_chat_model","openai_chat_model","local_llm_model","local_llm_base_url","local_llm_timeout","public_access","allowed_users","allowed_groups","agent_time_budget_seconds","max_tool_results","max_query_chars"):
        if k in p and hasattr(c,k):setattr(c,k,p[k])
    c.generator=c.llm_provider if c.llm_enabled else "mock";registry.register(c);return jsonify({"ok":True,"config":c.to_yaml_dict()})
@app.get("/api/admin/env-status")
def env_status():return jsonify({k:bool(os.getenv(k)) for k in ["OPENAI_API_KEY","AWS_ACCESS_KEY_ID","AWS_PROFILE","AWS_DEFAULT_REGION","GITHUB_TOKEN","CONFLUENCE_API_TOKEN","SHAREPOINT_ACCESS_TOKEN"]})
@app.get("/api/admin/provider-status")
def provider_status():
    out={"local":{"ready":True,"message":"Local pipeline available; real generation requires Ollama or another configured local runtime."},"openai":{"ready":bool(os.getenv("OPENAI_API_KEY")),"message":"API key configured" if os.getenv("OPENAI_API_KEY") else "API key not configured"},"bedrock":{"ready":False,"credentials":False,"region":os.getenv("AWS_DEFAULT_REGION","us-east-1"),"message":"AWS credentials unavailable"}}
    try:
        import boto3
        s=boto3.Session(region_name=out["bedrock"]["region"]);creds=s.get_credentials();out["bedrock"]["credentials"]=bool(creds and getattr(creds,"access_key",None));out["bedrock"]["ready"]=out["bedrock"]["credentials"];out["bedrock"]["message"]="AWS credentials detected" if out["bedrock"]["ready"] else "AWS credentials unavailable"
        if out["bedrock"]["ready"]:
            try:s.client("bedrock-runtime",region_name=out["bedrock"]["region"]);out["bedrock"]["message"]="Bedrock runtime client initialized"
            except Exception as e:out["bedrock"]["ready"]=False;out["bedrock"]["message"]=str(e)
    except Exception as e:out["bedrock"]["message"]=str(e)
    return jsonify(out)
@app.post("/api/admin/test-provider")
def test_provider():
    p=request.get_json(silent=True) or {};provider=p.get("provider","openai")
    try:
        if provider=="bedrock":
            from knowledge_fabric.generation.bedrock_generator import BedrockGenerator;g=BedrockGenerator(model_id=p.get("model",PipelineConfig.bedrock_chat_model),region_name=p.get("region","us-east-1"))
        elif provider=="openai":
            from knowledge_fabric.generation.openai_generator import OpenAIGenerator;g=OpenAIGenerator(model_id=p.get("model",PipelineConfig.openai_chat_model),api_key_env=p.get("api_key_env","OPENAI_API_KEY"),base_url=p.get("base_url",PipelineConfig.openai_base_url))
        elif provider=="local":
            from knowledge_fabric.generation.local_generator import LocalGenerator;g=LocalGenerator(model_id=p.get("model",PipelineConfig.local_llm_model),base_url=p.get("base_url",PipelineConfig.local_llm_base_url))
        else:return jsonify({"ready":True,"provider":"mock","message":"Deterministic mode"})
        ready=bool(g.health()) if hasattr(g,"health") else True
        if ready and hasattr(g,"probe"):ready=bool(g.probe())
        return jsonify({"ready":ready,"provider":provider,"message":"Live model probe successful." if ready else "Provider is not ready or model access failed."})
    except Exception as e:return jsonify({"ready":False,"provider":provider,"message":str(e)}),200
@app.get("/evaluation/live-lab")
def live_lab():return render_template("live_lab.html",runs=live_benchmarks.list(),summary=_system_summary())
@app.get("/evaluation/benchmark-studio")
def benchmark_studio_page():return render_template("benchmark_studio.html",summary=_system_summary(),runs=benchmark_studio.list())
@app.get("/api/admin/benchmark-studio")
def list_benchmark_studio():return jsonify({"runs":benchmark_studio.list(int(request.args.get("limit",50)))})
@app.post("/api/admin/benchmark-studio")
def run_benchmark_studio():
    p=request.get_json(silent=True) or {};matrix=p.get("matrix") or []
    if not matrix:return jsonify({"status":"failed","reason":"matrix must contain at least one benchmark configuration"}),400
    c=registry.get_source(p.get("source_id")) if p.get("source_id") else (registry.list_sources()[0] if registry.list_sources() else _bootstrap_source())
    try:r=run_studio(c,matrix,cases=p.get("cases"));benchmark_studio.append(r);return jsonify(r)
    except Exception as e:return jsonify({"status":"failed","reason":str(e)}),500
@app.get("/api/admin/live-tests")
def list_live_tests():return jsonify({"runs":live_benchmarks.list(int(request.args.get("limit",50)))})
@app.post("/api/admin/live-test")
def live_test():
    p=request.get_json(silent=True) or {};c=registry.get_source(p.get("source_id")) if p.get("source_id") else (registry.list_sources()[0] if registry.list_sources() else _bootstrap_source())
    try:r=run_benchmark(c,p.get("repo","psf/requests"),provider=p.get("provider","local"),model=p.get("model"),ref=p.get("ref"),cases=p.get("cases"));live_benchmarks.append(r);return jsonify(r)
    except Exception as e:return jsonify({"status":"failed","reason":str(e)}),500
@app.get("/api/admin/control-plane")
def control_plane():return jsonify(admin_store.snapshot())
@app.get("/api/admin/audit")
def audit_log():return jsonify({"events":admin_store.audit(max(1,min(500,int(request.args.get("limit",100)))))})
@app.post("/api/admin/control-plane")
def update_control_plane():
    p=request.get_json(silent=True) or {};changes=p.get("settings",p.get("changes",{}))
    try:snap,changed=admin_store.update(changes,actor=p.get("actor","admin"),reason=p.get("reason","control-plane update"),expected_version=p.get("expected_version"));return jsonify({"ok":True,"config":snap,"changed":changed})
    except ValueError as e:return jsonify({"error":str(e)}),409
@app.post("/api/admin/apply-defaults/<source_id>")
def apply_defaults(source_id):
    c=registry.get_source(source_id)
    if not c:return jsonify({"error":"source not found"}),404
    s=admin_store.snapshot().get("settings",{});m={"llm_provider":"default_llm_provider","top_k":"default_top_k","max_tokens":"default_max_tokens","max_context_chars":"default_max_context_chars","confidence_threshold":"default_confidence_threshold","enable_reranker":"default_reranker","enable_query_expansion":"default_query_expansion","enable_self_rag":"default_self_rag","enable_cache":"default_cache","max_agent_steps":"default_max_agent_steps"}
    for f,k in m.items():
        if k in s:setattr(c,f,s[k])
    c.generator=c.llm_provider if c.llm_enabled else "mock";registry.register(c);return jsonify({"ok":True,"config":c.to_yaml_dict()})

if os.getenv("KF_AUTO_BOOTSTRAP","1")=="1":_ensure_demo()
@app.errorhandler(413)
def too_large(_):return jsonify({"error":"request exceeds configured upload limit"}),413
@app.errorhandler(500)
def internal(_):logging.exception("Unhandled application error");return jsonify({"error":"internal server error"}),500
if __name__=="__main__":scheduler.start_all();app.run(host="0.0.0.0",port=5050,debug=False)
