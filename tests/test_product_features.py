from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.pipeline import KnowledgeFabricPipeline

def test_local_product_query_and_confidence(tmp_path):
    cfg=PipelineConfig(source_id='x',connector_options={'root_path':'sample_data'},index_dir=str(tmp_path),generator='mock',llm_enabled=False)
    p=KnowledgeFabricPipeline(cfg)
    r=p.ingest()
    assert r['total_chunks'] > 0
    out=p.query('How does retry work?')
    assert out['retrieved']
    assert out['confidence']['label'] in {'low','medium','high'}
    assert 'claim_coverage' in out['confidence']
    assert out['trace']

def test_llm_switch_is_configurable_without_breaking_local_mode(tmp_path):
    cfg=PipelineConfig(source_id='x',connector_options={'root_path':'sample_data'},index_dir=str(tmp_path),generator='mock',llm_enabled=False)
    assert not cfg.effective_llm_enabled()
    cfg.llm_enabled=True; cfg.llm_provider='mock'
    assert cfg.effective_llm_enabled()
