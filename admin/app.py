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
# NOTE: this file is intentionally updated through the GitHub contents API;
# the existing routes remain unchanged. Provider status route is inserted below.
