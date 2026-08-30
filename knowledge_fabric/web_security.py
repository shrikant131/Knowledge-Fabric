"""Web security helpers for local and simple cloud deployments."""
from __future__ import annotations
import os
from functools import wraps
from flask import request, session, redirect, url_for, jsonify
from knowledge_fabric.security import ConstantTimeSecret, RateLimiter, new_csrf_token

class WebSecurity:
    def __init__(self, app):
        self.app=app
        self.mode=os.getenv("KF_AUTH_MODE","none").lower()
        self.admin_key=os.getenv("ADMIN_API_KEY","").strip()
        if self.mode not in {"none","api_key"}:
            raise RuntimeError("KF_AUTH_MODE must be 'none' or 'api_key'")
        if self.mode=="api_key" and len(self.admin_key)<16:
            raise RuntimeError("ADMIN_API_KEY must be at least 16 characters when KF_AUTH_MODE=api_key")
        if os.getenv("KF_RATE_BACKEND","local")=="redis":
            from knowledge_fabric.security import RedisRateLimiter
            redis_url=os.getenv("KF_REDIS_URL","").strip()
            if not redis_url: raise RuntimeError("KF_REDIS_URL is required when KF_RATE_BACKEND=redis")
            self.rate=RedisRateLimiter(redis_url,int(os.getenv("KF_RATE_LIMIT",60)),60)
            self.benchmark_rate=RedisRateLimiter(redis_url,int(os.getenv("KF_BENCHMARK_RATE_LIMIT",10)),60)
        else:
            self.rate=RateLimiter(int(os.getenv("KF_RATE_LIMIT",60)),60)
            self.benchmark_rate=RateLimiter(int(os.getenv("KF_BENCHMARK_RATE_LIMIT",10)),60)
        app.config["MAX_CONTENT_LENGTH"]=int(os.getenv("KF_MAX_UPLOAD_BYTES",25*1024*1024))
        if not app.secret_key:
            if self.mode=="api_key":
                raise RuntimeError("SECRET_KEY must be configured for authenticated deployments")
            app.secret_key=os.urandom(32)

    def principal(self):
        if self.mode=="api_key" and session.get("authenticated"):
            return {"user_id":session.get("user_id","admin"),"groups":session.get("groups",["admin"]),
                    "tenant_id":session.get("tenant_id","local"),"authenticated":True}
        return {"user_id":"anonymous","groups":[],"tenant_id":os.getenv("KF_DEFAULT_TENANT","local"),"authenticated":False}

    def csrf(self):
        token=session.get("_csrf")
        if not token:
            token=new_csrf_token(); session["_csrf"]=token
        return token

    def require_csrf(self):
        if request.method not in {"POST","PUT","PATCH","DELETE"} or self.mode=="none":
            return True
        token=request.headers.get("X-CSRF-Token") or request.form.get("_csrf")
        return bool(token and ConstantTimeSecret.matches(token,session.get("_csrf","")))

    def authenticated(self):
        return self.mode=="none" or bool(session.get("authenticated"))

    def login(self,key):
        if ConstantTimeSecret.matches(key,self.admin_key):
            session.clear(); session["authenticated"]=True; session["user_id"]="admin"; session["groups"]=["admin"]; session["tenant_id"]=os.getenv("KF_DEFAULT_TENANT","local"); session["_csrf"]=new_csrf_token()
            return True
        return False

    def logout(self):
        session.clear()

    def allow_rate(self, benchmark=False):
        key=f"{request.remote_addr or 'unknown'}:{'bench' if benchmark else 'api'}"
        return (self.benchmark_rate if benchmark else self.rate).allow(key)

def api_error(message, code):
    return jsonify({"error":message}),code
