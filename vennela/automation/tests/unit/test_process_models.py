from vennela.automation.process.models import ProcessModel, ProcessType


def test_process_model_serialization_roundtrip():
    p = ProcessModel(process_id="P1", process_type=ProcessType.TOOL_TASK)
    d = p.to_dict()
    assert d["process_id"] == "P1"
    p2 = ProcessModel.from_dict(d)
    assert p2.process_id == "P1"
    assert p2.process_type == ProcessType.TOOL_TASK
