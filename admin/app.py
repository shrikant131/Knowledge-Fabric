"""Knowledge Fabric admin control plane.

Run: python admin/app.py
Open: http://localhost:5050/admin
"""
from __future__ import annotations
import json, logging, os, sys, re, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flask import Flask, jsonify, redirect, render_template, request, url_for, session
from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.admin_config import AdminConfigStore
from knowledge_fabric.registry import ConnectorRegistry
from knowledge_fabric.triggers.multi_scheduler import MultiSourceScheduler
from knowledge_fabric.evaluation.live_benchmark import LiveBenchmarkStore, run_benchmark
from knowledge_fabric.evaluation.benchmark_studio import BenchmarkStudioStore, run_studio
from knowledge_fabric.security import Principal
from knowledge_fabric.web_security import WebSecurity, api_error
from knowledge_fabric.jobs import build_manager

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = Flask(__name__)

security = WebSecurity(app)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("KF_COOKIE_SECURE","0")=="1",
    MAX_CONTENT_LENGTH=int(os.getenv("KF_MAX_UPLOAD_BYTES",25*1024*1024)),
)

@app.context_processor
def _security_context():
    return {"csrf_token": security.csrf(), "authenticated": security.authenticated(),
            "auth_mode": security.mode}

@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options","nosniff")
    response.headers.setdefault("X-Frame-Options","DENY")
    response.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security","max-age=31536000; includeSubDomains")
    response.headers.setdefault("Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")
    return response

@app.before_request
def _security_guard():
    if request.path.startswith("/static/") or request.path == "/api/health":
        return None
    if not security.require_csrf() and request.method in {"POST","PUT","PATCH","DELETE"}:
        return api_error("CSRF validation failed",403)
    protected = (request.path.startswith("/admin") or request.path.startswith("/api/admin")
                 or request.path.startswith("/sources") or request.path.startswith("/evaluation")
                 or (request.path.startswith("/quick-start") and request.method != "GET"))
    # Playground remains publicly usable only when explicitly allowed.
    if request.path.startswith("/api/playground") or request.path.startswith("/playground"):
        if os.getenv("KF_PUBLIC_PLAYGROUND","1" if security.mode=="none" else "0")=="1":
            return None
        protected=True
    if protected and not security.authenticated():
        if request.path.startswith("/api/"):
            return api_error("authentication required",401)
        return redirect(url_for("login", next=request.path))
    if request.path.startswith("/api/") and not security.allow_rate(request.path.startswith("/api/admin/benchmark")):
        return api_error("rate limit exceeded",429)
    return None

@app.get("/login")
def login():
    if security.authenticated(): return redirect(request.args.get("next") or url_for("playground"))
    return render_template("login.html", next=request.args.get("next","/admin"))

@app.post("/login")
def login_post():
    if not security.require_csrf(): return api_error("CSRF validation failed",403)
    if not security.login(request.form.get("api_key","")):
        return render_template("login.html", next=request.form.get("next","/admin"), error="Invalid credentials"),401
    return redirect(request.form.get("next") or url_for("admin_console"))

@app.post("/logout")
def logout():
    security.logout()
    return redirect(url_for("playground"))
registry = ConnectorRegistry(manifests_dir="./connectors_registry", status_path="./data/registry_status.json")
scheduler = MultiSourceScheduler(registry)
admin_store = AdminConfigStore()
live_benchmarks = LiveBenchmarkStore()
benchmark_studio = BenchmarkStudioStore()
jobs = build_manager()
ASYNC_JOBS = os.getenv('KF_ASYNC_JOBS','0') == '1'
CONNECTOR_FIELDS = {
    "file": [("root_path", "Root path", "./sample_data")],
    "github": [("repo", "Repository (owner/name)", "psf/requests"), ("ref", "Branch / ref", "main"), ("path", "Optional path", "")],
    "confluence": [("base_url", "Base URL", "https://yourcompany.atlassian.net"), ("space_key", "Space key", "ENG"), ("auth_env_var", "Auth token env var", "CONFLUENCE_API_TOKEN"), ("user_email_env_var", "User email env var", "CONFLUENCE_USER_EMAIL")],
    "sharepoint": [("site_id", "Site ID", ""), ("drive_id", "Drive ID", ""), ("auth_env_var", "Access token env var", "SHAREPOINT_ACCESS_TOKEN")],
}

def _github_parts(repo):
    value=(repo or "").strip().removeprefix("https://github.com/").removeprefix("http://github.com/").strip("/")
    parts=value.split("/")
    if len(parts) != 2 or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", parts[0]) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", parts[1]):
        raise ValueError("GitHub repository must look like owner/name")
    return parts[0], parts[1]

def _bootstrap_source(source_id="demo", display_name="Demo Knowledge", connector_type="file", options=None):
    options=options or {"root_path":"./sample_data"}
    cfg=PipelineConfig(source_id=source_id, display_name=display_name, connector_type=connector_type, connector_options=options, trigger_type="scheduler", poll_interval_seconds=60, embedder="local", generator="mock", llm_enabled=False, enable_reranker=True, enable_query_expansion=True, enable_self_rag=True, enable_cache=True)
    registry.register(cfg)
    return cfg

def _ensure_demo():
    if not registry.list_sources():
        cfg=_bootstrap_source()
        try:
            result=registry.build_pipeline(cfg.source_id).ingest(); registry.record_run(cfg.source_id,result)
        except Exception as e:
            registry.record_run(cfg.source_id,None,error=str(e))


def _rows():
    return [{"cfg": c, "status": registry.get_status(c.source_id), "running": scheduler.is_running(c.source_id)} for c in registry.list_sources()]

def _safe_float(v, default, lo, hi):
    try: return min(hi, max(lo, float(v)))
    except Exception: return default

def _safe_int(v, default, lo, hi):
    try: return min(hi, max(lo, int(v)))
    except Exception: return default

def _system_summary():
    rows = _rows()
    total_chunks = sum((r["status"].last_result or {}).get("total_chunks", 0) for r in rows)
    errors = sum(bool(r["status"].last_error) for r in rows)
    return {"sources": len(rows), "watching": sum(r["running"] for r in rows), "chunks": total_chunks, "errors": errors,
            "llm_enabled": sum(r["cfg"].effective_llm_enabled() for r in rows)}

@app.route("/playground")
def playground():
    return render_template("playground.html", rows=_rows(), summary=_system_summary())

@app.route("/quick-start")
def quick_start():
    return render_template("quick_start.html", connector_types=list(CONNECTOR_FIELDS))

@app.post("/quick-start/demo")
def quick_demo():
    cfg=registry.get_source("demo") or _bootstrap_source()
    try:
        result=registry.build_pipeline(cfg.source_id).ingest(); registry.record_run(cfg.source_id,result)
    except Exception as e:
        registry.record_run(cfg.source_id,None,error=str(e)); return jsonify({"ok":False,"error":str(e)}),500
    return jsonify({"ok":True,"source_id":cfg.source_id,"result":result})

@app.post("/quick-start/files")
def quick_files():
    root=request.form.get("root_path","").strip()
    uploads=request.files.getlist("files")
    if len(uploads)>50: return jsonify({"ok":False,"error":"maximum 50 files per upload"}),400
    if uploads and any(f.filename for f in uploads):
        safe_dir=Path(os.getenv("KF_DATA_DIR","./data"))/"quick_uploads"; safe_dir.mkdir(parents=True, exist_ok=True)
        for f in uploads:
            if not f.filename: continue
            name=Path(f.filename).name
            if len(name) > 180: return jsonify({"ok":False,"error":"filename too long"}),400
            allowed_ext={".pdf",".md",".txt",".rst",".py",".java",".js",".ts",".go",".json",".yaml",".yml",".csv"}
            if Path(name).suffix.lower() not in allowed_ext: return jsonify({"ok":False,"error":"unsupported file type"}),415
            # Avoid collisions and preserve the user-visible filename as metadata.
            safe_name=f"{uuid.uuid4().hex[:12]}-{name}"
            f.save(safe_dir/safe_name)
        root=str(safe_dir)
    root=root or "./sample_data"
    cfg=_bootstrap_source("quick-files","Uploaded / Local Files","file",{"root_path":root})
    try:
        result=registry.build_pipeline(cfg.source_id).ingest(); registry.record_run(cfg.source_id,result)
    except Exception as e:
        registry.record_run(cfg.source_id,None,error=str(e)); return jsonify({"ok":False,"error":str(e)}),500
    return jsonify({"ok":True,"source_id":cfg.source_id,"result":result})

@app.post("/quick-start/github")
def quick_github():
    try: owner,repo=_github_parts(request.form.get("repo",""))
    except ValueError as e: return jsonify({"ok":False,"error":str(e)}),400
    sid=f"github-{owner}-{repo}".lower().replace(".","-")
    cfg=_bootstrap_source(sid,f"GitHub · {owner}/{repo}","github",{"owner":owner,"repo":repo,"ref":request.form.get("ref") or None,"token_env_var":"GITHUB_TOKEN"})
    try:
        result=registry.build_pipeline(cfg.source_id).ingest(); registry.record_run(cfg.source_id,result)
    except Exception as e:
        registry.record_run(cfg.source_id,None,error=str(e)); return jsonify({"ok":False,"error":str(e)}),502
    return jsonify({"ok":True,"source_id":cfg.source_id,"result":result})

@app.post("/api/playground/query")
def playground_query():
    payload=request.get_json(silent=True) or {}; sid=payload.get("source_id") or (registry.list_sources()[0].source_id if registry.list_sources() else None); q=(payload.get("question") or "").strip()
    if not sid: return jsonify({"error":"No knowledge source. Start with the demo or add a source."}),400
    if not q: return jsonify({"error":"question is required"}),400
    try: return jsonify(registry.build_pipeline(sid).query(q, principal=Principal(user_id=security.principal()['user_id'], groups=frozenset(security.principal()['groups']), tenant_id=security.principal()['tenant_id'], authenticated=security.principal()['authenticated'])))
    except Exception as e: return jsonify({"error":str(e)}),500

if os.getenv("KF_AUTO_BOOTSTRAP", "1") == "1":
    _ensure_demo()

@app.errorhandler(413)
def request_too_large(_):
    return jsonify({"error":"request exceeds configured upload limit"}), 413

@app.errorhandler(500)
def internal_error(_):
    logging.exception("Unhandled application error")
    return jsonify({"error":"internal server error"}), 500

@app.route("/")
def root(): return redirect(url_for("playground"))

@app.route("/admin")
def admin_console():
    return render_template("admin_console.html", rows=_rows(), connector_types=list(CONNECTOR_FIELDS), summary=_system_summary(), env_status={k: bool(os.getenv(k)) for k in ["OPENAI_API_KEY","GITHUB_TOKEN","CONFLUENCE_API_TOKEN","SHAREPOINT_ACCESS_TOKEN"]})

@app.route("/sources/new")
def new_source_form():
    t = request.args.get("connector_type", "file")
    return render_template("new_source.html", connector_types=list(CONNECTOR_FIELDS), selected_type=t, fields=CONNECTOR_FIELDS[t])

@app.route("/sources", methods=["POST"])
def create_source():
    f = request.form; t = f.get("connector_type","")
    if t not in CONNECTOR_FIELDS: return "Unknown connector", 400
    source_id=f.get("source_id","").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", source_id): return "Invalid source_id", 400
    options = {k: f.get(k, "") for k, _, _ in CONNECTOR_FIELDS[t]}
    if t == "github":
        owner, repo = _github_parts(options.get("repo", ""))
        options = {"owner": owner, "repo": repo, "ref": options.get("ref") or None, "path": options.get("path", ""), "token_env_var": "GITHUB_TOKEN"}
    cfg = PipelineConfig(
        source_id=source_id, display_name=f.get("display_name", "").strip(), connector_type=t,
        connector_options=options, trigger_type=f.get("trigger_type", "scheduler"),
        poll_interval_seconds=_safe_int(f.get("poll_interval_seconds", 60), 60, 5, 86400), embedder=f.get("embedder", "local"),
        generator="mock", llm_enabled=f.get("llm_enabled", "0") == "1", llm_provider=f.get("llm_provider", "bedrock"),
        bedrock_region=f.get("bedrock_region", "us-east-1"), bedrock_chat_model=f.get("bedrock_chat_model") or PipelineConfig.bedrock_chat_model,
        openai_chat_model=f.get("openai_chat_model") or PipelineConfig.openai_chat_model,
        enable_reranker=f.get("enable_reranker", "1") == "1", enable_query_expansion=True,
    )
    if cfg.llm_enabled: cfg.generator = cfg.llm_provider
    registry.register(cfg)
    return redirect(url_for("admin_console"))

@app.post("/sources/<source_id>/delete")
def delete_source(source_id): scheduler.stop_source(source_id); registry.unregister(source_id); return redirect(url_for("admin_console"))

@app.post("/sources/<source_id>/ingest")
def ingest_now(source_id):
    if ASYNC_JOBS:
        job=jobs.submit("ingest", _run_ingest_job, source_id)
        return (jsonify(job),202) if request.is_json else redirect(url_for("admin_console"))
    result=_run_ingest_job(source_id)
    if request.is_json: return jsonify(result)
    return redirect(url_for("admin_console"))

def _run_ingest_job(source_id):
    try:
        result=registry.build_pipeline(source_id).ingest(); registry.record_run(source_id,result); return result
    except Exception as e:
        registry.record_run(source_id,None,error=str(e)); raise

@app.post("/sources/<source_id>/watch/start")
def start_watch(source_id): scheduler.start_source(source_id); registry.set_watching(source_id, True); return redirect(url_for("admin_console"))
@app.post("/sources/<source_id>/watch/stop")
def stop_watch(source_id): scheduler.stop_source(source_id); registry.set_watching(source_id, False); return redirect(url_for("admin_console"))

@app.route("/sources/<source_id>/query", methods=["GET", "POST"])
def query_source(source_id):
    answer = None; retrieved = []; result = None; question = ""
    if request.method == "POST":
        question = request.form.get("question", "")
        result = registry.build_pipeline(source_id).query(question, principal=Principal(user_id=security.principal()['user_id'], groups=frozenset(security.principal()['groups']), tenant_id=security.principal()['tenant_id'], authenticated=security.principal()['authenticated'])); answer = result["answer"]; retrieved = result["retrieved"]
    cfg = registry.get_source(source_id)
    return render_template("query.html", cfg=cfg, question=question, answer=answer, retrieved=retrieved, result=result)

@app.get("/api/sources")
def api_sources():
    return jsonify([{"source_id": r["cfg"].source_id, "display_name": r["cfg"].display_name, "type": r["cfg"].connector_type,
                     "watching": r["running"], "last_run": r["status"].last_run_at, "last_error": r["status"].last_error,
                     "last_result": r["status"].last_result} for r in _rows()])

@app.get("/api/jobs")
def api_jobs():
    try: limit=max(1,min(100,int(request.args.get("limit",50))))
    except Exception: limit=50
    return jsonify({"jobs":jobs.store.list(limit)})

@app.get("/api/jobs/<job_id>")
def api_job(job_id):
    job=jobs.store.get(job_id)
    return (jsonify(job),200) if job else (jsonify({"error":"job not found"}),404)

@app.get("/api/health")
def api_health(): return jsonify({"status": "ok", "async_jobs": ASYNC_JOBS, **_system_summary()})

@app.post("/api/sources/<source_id>/query")
def api_query(source_id):
    payload = request.get_json(silent=True) or {}; q = payload.get("question", "")
    if not q: return jsonify({"error": "question is required"}), 400
    try: return jsonify(registry.build_pipeline(source_id).query(q, principal=Principal(user_id=security.principal()['user_id'], groups=frozenset(security.principal()['groups']), tenant_id=security.principal()['tenant_id'], authenticated=security.principal()['authenticated'])))
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.post("/api/sources/<source_id>/llm")
def api_llm(source_id):
    cfg = registry.get_source(source_id)
    if not cfg: return jsonify({"error": "source not found"}), 404
    payload = request.get_json(silent=True) or {}; enabled = bool(payload.get("enabled"))
    cfg.llm_enabled = enabled; cfg.llm_provider = payload.get("provider", cfg.llm_provider); cfg.generator = cfg.llm_provider if enabled else "mock"
    registry.register(cfg)
    try:
        p = registry.build_pipeline(source_id); status = {"enabled": enabled, "provider": cfg.llm_provider, "ready": enabled}
        if hasattr(p.generator, "health"): status["ready"] = bool(p.generator.health())
        return jsonify(status)
    except Exception as e: return jsonify({"enabled": enabled, "provider": cfg.llm_provider, "ready": False, "error": str(e)}), 400

@app.get("/sources/<source_id>/settings")
def source_settings(source_id):
    cfg = registry.get_source(source_id)
    if not cfg: return "Not found", 404
    return render_template("settings.html", cfg=cfg)

@app.post("/sources/<source_id>/settings")
def save_settings(source_id):
    cfg = registry.get_source(source_id)
    if not cfg: return "Not found", 404
    f = request.form
    cfg.llm_enabled = f.get("llm_enabled") == "1"; cfg.llm_provider = f.get("llm_provider", cfg.llm_provider); cfg.generator = cfg.llm_provider if cfg.llm_enabled else "mock"
    cfg.bedrock_region = f.get("bedrock_region", cfg.bedrock_region); cfg.bedrock_chat_model = f.get("bedrock_chat_model", cfg.bedrock_chat_model)
    cfg.openai_chat_model = f.get("openai_chat_model", cfg.openai_chat_model); cfg.openai_api_key_env = f.get("openai_api_key_env", cfg.openai_api_key_env)
    cfg.enable_reranker = f.get("enable_reranker") == "1"; cfg.enable_query_expansion = f.get("enable_query_expansion") == "1"; cfg.enable_cache = f.get("enable_cache") == "1"; cfg.enable_self_rag = f.get("enable_self_rag") == "1"
    cfg.top_k = _safe_int(f.get("top_k"), cfg.top_k, 1, 50); cfg.max_tokens = _safe_int(f.get("max_tokens"), cfg.max_tokens, 100, 10000); cfg.max_agent_steps = _safe_int(f.get("max_agent_steps"), cfg.max_agent_steps, 1, 10)
    cfg.max_context_chars = _safe_int(f.get("max_context_chars"), cfg.max_context_chars, 1000, 100000); cfg.cache_similarity_threshold = _safe_float(f.get("cache_similarity_threshold"), cfg.cache_similarity_threshold, .5, 1.0)
    cfg.public_access = f.get("public_access", "1") == "1"
    cfg.allowed_users = [x.strip() for x in f.get("allowed_users","").split(",") if x.strip()]
    cfg.allowed_groups = [x.strip() for x in f.get("allowed_groups","").split(",") if x.strip()]
    cfg.confidence_threshold = _safe_float(f.get("confidence_threshold"), cfg.confidence_threshold, 0, 1); cfg.reranker_weight = _safe_float(f.get("reranker_weight"), cfg.reranker_weight, 0, 2); cfg.symbol_match_weight = _safe_float(f.get("symbol_match_weight"), cfg.symbol_match_weight, 0, 10)
    registry.register(cfg)
    return redirect(url_for("admin_console") + "#ai")

@app.get("/api/admin/summary")
def api_admin_summary(): return jsonify(_system_summary())

@app.get("/api/admin/config/<source_id>")
def api_config(source_id):
    cfg = registry.get_source(source_id)
    if not cfg: return jsonify({"error": "source not found"}), 404
    return jsonify(cfg.to_yaml_dict())

@app.post("/api/admin/source/<source_id>/settings")
def api_source_settings(source_id):
    cfg = registry.get_source(source_id)
    if not cfg: return jsonify({"error": "source not found"}), 404
    payload = request.get_json(silent=True) or {}
    for field in ("top_k", "max_tokens", "max_agent_steps", "max_context_chars", "confidence_threshold", "cache_similarity_threshold", "reranker_weight", "symbol_match_weight", "enable_reranker", "enable_query_expansion", "enable_cache", "enable_self_rag", "llm_enabled", "llm_provider", "bedrock_region", "bedrock_chat_model", "openai_chat_model",
    "public_access", "allowed_users", "allowed_groups", "agent_time_budget_seconds", "max_tool_results", "max_query_chars"):
        if field in payload and hasattr(cfg, field): setattr(cfg, field, payload[field])
    cfg.generator = cfg.llm_provider if cfg.llm_enabled else "mock"
    cfg.agent_time_budget_seconds=_safe_int(cfg.agent_time_budget_seconds,cfg.agent_time_budget_seconds,1,120)
    cfg.max_tool_results=_safe_int(cfg.max_tool_results,cfg.max_tool_results,1,1000)
    cfg.max_query_chars=_safe_int(cfg.max_query_chars,cfg.max_query_chars,100,20000)
    registry.register(cfg)
    return jsonify({"ok": True, "config": cfg.to_yaml_dict()})

@app.get("/api/admin/env-status")
def env_status():
    keys = ["OPENAI_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_PROFILE", "GITHUB_TOKEN", "CONFLUENCE_API_TOKEN", "SHAREPOINT_ACCESS_TOKEN"]
    return jsonify({k: bool(os.getenv(k)) for k in keys})

@app.post("/api/admin/test-provider")
def test_provider():
    payload = request.get_json(silent=True) or {}; provider = payload.get("provider", "openai")
    try:
        if provider == "openai":
            from knowledge_fabric.generation.openai_generator import OpenAIGenerator
            g = OpenAIGenerator(model_id=payload.get("model", PipelineConfig.openai_chat_model), api_key_env=payload.get("api_key_env", "OPENAI_API_KEY"), base_url=payload.get("base_url", PipelineConfig.openai_base_url))
        elif provider == "bedrock":
            from knowledge_fabric.generation.bedrock_generator import BedrockGenerator
            g = BedrockGenerator(model_id=payload.get("model", PipelineConfig.bedrock_chat_model), region_name=payload.get("region", "us-east-1"))
        else: return jsonify({"ready": True, "provider": "local", "message": "Local mode requires no external credentials."})
        ready = bool(g.health()) if hasattr(g, "health") else True
        if ready and hasattr(g, "probe"):
            ready=bool(g.probe())
        return jsonify({"ready": ready, "provider": provider, "message": "Live model probe successful." if ready else "Provider is not ready or model access failed."})
    except Exception as e: return jsonify({"ready": False, "provider": provider, "message": str(e)}), 200

@app.get("/evaluation/live-lab")
def live_lab():
    return render_template("live_lab.html", runs=live_benchmarks.list(), summary=_system_summary())

@app.get("/evaluation/benchmark-studio")
def benchmark_studio_page():
    return render_template("benchmark_studio.html", summary=_system_summary(), runs=benchmark_studio.list())

@app.get("/api/admin/benchmark-studio")
def list_benchmark_studio():
    return jsonify({"runs": benchmark_studio.list(int(request.args.get("limit",50)))})

@app.post("/api/admin/benchmark-studio")
def run_benchmark_studio():
    payload=request.get_json(silent=True) or {}
    matrix=payload.get("matrix") or []
    if not isinstance(matrix,list) or not matrix:
        return jsonify({"status":"failed","reason":"matrix must contain at least one benchmark configuration"}),400
    if len(matrix)>12:
        return jsonify({"status":"failed","reason":"maximum 12 matrix runs per request"}),400
    cases=payload.get("cases")
    if cases is not None and (not isinstance(cases,list) or len(cases)>25):
        return jsonify({"status":"failed","reason":"cases must be a list with at most 25 cases"}),400
    cfg=registry.get_source(payload.get("source_id")) if payload.get("source_id") else (registry.list_sources()[0] if registry.list_sources() else _bootstrap_source())
    try:
        if ASYNC_JOBS:
            job=jobs.submit("benchmark_studio", _run_studio_job, cfg, matrix, cases)
            return jsonify(job),202
        result=run_studio(cfg,matrix,cases=cases)
        benchmark_studio.append(result)
        return jsonify(result),200
    except Exception as e:
        return jsonify({"status":"failed","reason":str(e)}),500

def _run_studio_job(cfg,matrix,cases):
    result=run_studio(cfg,matrix,cases=cases); benchmark_studio.append(result); return result

@app.get("/api/admin/live-tests")
def list_live_tests():
    return jsonify({"runs": live_benchmarks.list(int(request.args.get("limit",50)))})

@app.post("/api/admin/live-test")
def live_test():
    payload = request.get_json(silent=True) or {}
    repo = payload.get("repo", "psf/requests")
    provider = payload.get("provider", "local")
    cfg = registry.get_source(payload.get("source_id")) if payload.get("source_id") else (registry.list_sources()[0] if registry.list_sources() else _bootstrap_source())
    try:
        if ASYNC_JOBS:
            job=jobs.submit("live_test", _run_live_test_job, cfg, repo, provider, payload.get("model"), payload.get("ref"), payload.get("cases"))
            return jsonify(job),202
        run = _run_live_test_job(cfg,repo,provider,payload.get("model"),payload.get("ref"),payload.get("cases"))
        return jsonify(run), 200 if run.get("status") in ("completed","blocked") else 500
    except Exception as e:
        return jsonify({"status":"failed","repo":repo,"provider":provider,"reason":str(e)}),500


def _run_live_test_job(cfg,repo,provider,model,ref,cases):
    run=run_benchmark(cfg,repo,provider=provider,model=model,ref=ref,cases=cases); live_benchmarks.append(run); return run

@app.get("/api/admin/control-plane")
def control_plane():
    return jsonify(admin_store.snapshot())

@app.get("/api/admin/audit")
def audit_log():
    try: limit=max(1,min(500,int(request.args.get("limit",100))))
    except Exception: limit=100
    return jsonify({"events": admin_store.audit(limit)})

@app.post("/api/admin/control-plane")
def update_control_plane():
    payload=request.get_json(silent=True) or {}
    changes=payload.get("settings", payload.get("changes", {}))
    if not isinstance(changes, dict): return jsonify({"error":"settings must be an object"}),400
    # Only known product controls are persisted here; source-specific settings remain on source manifests.
    allowed={
      "default_llm_provider","default_llm_model","default_temperature","default_max_tokens",
      "default_top_k","default_max_context_chars","default_confidence_threshold",
      "default_reranker","default_query_expansion","default_self_rag","default_cache",
      "default_max_agent_steps","default_allowed_sensitivity","live_test_repo","live_test_provider",
      "live_test_model","telemetry_enabled","audit_enabled"
    }
    unknown=sorted(set(changes)-allowed)
    if unknown: return jsonify({"error":"unknown settings","fields":unknown}),400
    # normalize high-impact values
    for k in list(changes):
        v=changes[k]
        if k in {"default_top_k","default_max_tokens","default_max_context_chars","default_max_agent_steps"}:
            try: changes[k]=int(v)
            except: return jsonify({"error":f"{k} must be an integer"}),400
        if k in {"default_temperature","default_confidence_threshold"}:
            try: changes[k]=float(v)
            except: return jsonify({"error":f"{k} must be numeric"}),400
    try:
        snap, changed=admin_store.update(changes, actor=payload.get("actor","admin"), reason=payload.get("reason","control-plane update"), expected_version=payload.get("expected_version"))
    except ValueError as e: return jsonify({"error":str(e)}),409
    return jsonify({"ok":True,"config":snap,"changed":changed})

@app.post("/api/admin/apply-defaults/<source_id>")
def apply_defaults(source_id):
    cfg=registry.get_source(source_id)
    if not cfg: return jsonify({"error":"source not found"}),404
    s=admin_store.snapshot().get('settings',{})
    mapping={
      'llm_provider':'default_llm_provider','top_k':'default_top_k','max_tokens':'default_max_tokens',
      'max_context_chars':'default_max_context_chars','confidence_threshold':'default_confidence_threshold',
      'enable_reranker':'default_reranker','enable_query_expansion':'default_query_expansion',
      'enable_self_rag':'default_self_rag','enable_cache':'default_cache','max_agent_steps':'default_max_agent_steps'
    }
    for field,key in mapping.items():
        if key in s: setattr(cfg,field,s[key])
    if cfg.llm_provider in ('openai','bedrock') and cfg.llm_enabled: cfg.generator=cfg.llm_provider
    registry.register(cfg)
    return jsonify({"ok":True,"config":cfg.to_yaml_dict()})

if __name__ == "__main__":
    scheduler.start_all(); app.run(host="0.0.0.0", port=5050, debug=False)
