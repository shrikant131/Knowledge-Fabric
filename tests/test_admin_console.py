from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from admin.app import app

def test_admin_console_loads():
    c=app.test_client(); r=c.get('/admin'); assert r.status_code==200; assert b'Administration Console' in r.data; assert b'Live Test Lab' in r.data

def test_health_summary():
    c=app.test_client(); r=c.get('/api/admin/summary'); assert r.status_code==200; d=r.get_json(); assert 'sources' in d and 'chunks' in d

def test_env_status_shape():
    c=app.test_client(); d=c.get('/api/admin/env-status').get_json(); assert 'OPENAI_API_KEY' in d and 'GITHUB_TOKEN' in d

def test_live_test_does_not_fake_without_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    c=app.test_client(); d=c.post('/api/admin/live-test', json={'repo':'psf/requests','provider':'openai'}).get_json(); assert d['status']=='blocked'

def test_control_plane_persists_and_versions(tmp_path, monkeypatch):
    from knowledge_fabric.admin_config import AdminConfigStore
    store=AdminConfigStore(str(tmp_path/'cfg.json'), str(tmp_path/'audit.jsonl'))
    snap, changed=store.update({'default_top_k':12}, reason='test')
    assert snap['version']==1 and changed['default_top_k']['new']==12
    assert store.snapshot()['settings']['default_top_k']==12
    assert store.audit(10)[0]['changes']['default_top_k']['new']==12

def test_control_plane_api_rejects_unknown_field():
    c=app.test_client(); r=c.post('/api/admin/control-plane',json={'settings':{'not_a_setting':1}}); assert r.status_code==400
