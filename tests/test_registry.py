from knowledge_fabric.config import PipelineConfig
from knowledge_fabric.registry import ConnectorRegistry


def _registry(tmp_path):
    return ConnectorRegistry(
        manifests_dir=str(tmp_path / "connectors_registry"),
        status_path=str(tmp_path / "data" / "status.json"),
    )


def test_register_writes_manifest_and_appears_in_list(tmp_path):
    reg = _registry(tmp_path)
    cfg = PipelineConfig(source_id="src1", connector_type="file",
                          connector_options={"root_path": "./sample_data"})
    reg.register(cfg)

    sources = reg.list_sources()
    assert len(sources) == 1
    assert sources[0].source_id == "src1"
    assert sources[0].connector_options["root_path"] == "./sample_data"


def test_unregister_removes_manifest_and_status(tmp_path):
    reg = _registry(tmp_path)
    cfg = PipelineConfig(source_id="src1", connector_type="file")
    reg.register(cfg)
    reg.record_run("src1", {"chunks_ingested": 3})

    reg.unregister("src1")
    assert reg.list_sources() == []
    status = reg.get_status("src1")
    assert status.last_run_at is None  # fresh/default status after unregister


def test_record_run_tracks_success_and_error(tmp_path):
    reg = _registry(tmp_path)
    cfg = PipelineConfig(source_id="src1", connector_type="file")
    reg.register(cfg)

    reg.record_run("src1", {"chunks_ingested": 5}, error=None)
    status = reg.get_status("src1")
    assert status.last_error is None
    assert status.last_result["chunks_ingested"] == 5
    assert status.total_runs == 1

    reg.record_run("src1", None, error="boom")
    status = reg.get_status("src1")
    assert status.last_error == "boom"
    assert status.total_runs == 2


def test_status_persists_across_registry_instances(tmp_path):
    reg1 = _registry(tmp_path)
    cfg = PipelineConfig(source_id="src1", connector_type="file")
    reg1.register(cfg)
    reg1.record_run("src1", {"chunks_ingested": 7})

    # simulate restart: new ConnectorRegistry pointed at the same paths
    reg2 = ConnectorRegistry(
        manifests_dir=str(tmp_path / "connectors_registry"),
        status_path=str(tmp_path / "data" / "status.json"),
    )
    status = reg2.get_status("src1")
    assert status.last_result["chunks_ingested"] == 7
