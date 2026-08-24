from vennela.automation.process.models import ProcessModel
from vennela.automation.process.manager import ProcessManager
from vennela.automation.persistence.storage_adapter import SQLiteStorageAdapter
from vennela.automation.process.states import ProcessState


def test_dependent_promoted_on_completion(tmp_path):
    db = tmp_path / "phase1dep_prom.db"
    storage = SQLiteStorageAdapter(str(db))
    pm = ProcessManager(storage=storage)

    a = ProcessModel(process_id="A")
    b = ProcessModel(process_id="B")
    pm.create_process(a)
    pm.create_process(b)

    pm.add_dependency("B", "A")
    assert "A" in pm.get_process("B").dependencies

    # advance A through lifecycle to RUNNING then complete
    pm.transition_process("A", "QUEUED", expected_version=1)
    pm.transition_process("A", "READY", expected_version=2)
    pm.transition_process("A", "RUNNING", expected_version=3)
    pm.complete_process("A", result={"ok": True}, expected_version=4)
    # B should be promoted to QUEUED
    b_after = pm.get_process("B")
    assert b_after.state == ProcessState.QUEUED.value


def test_dependent_blocked_on_failed_dependency(tmp_path):
    db = tmp_path / "phase1dep_block.db"
    storage = SQLiteStorageAdapter(str(db))
    pm = ProcessManager(storage=storage)

    a = ProcessModel(process_id="A2")
    b = ProcessModel(process_id="B2")
    pm.create_process(a)
    pm.create_process(b)

    pm.add_dependency("B2", "A2")

    # advance A to RUNNING then fail
    pm.transition_process("A2", "QUEUED", expected_version=1)
    pm.transition_process("A2", "READY", expected_version=2)
    pm.transition_process("A2", "RUNNING", expected_version=3)
    pm.fail_process("A2", error={"msg": "boom"}, expected_version=4)
    b_after = pm.get_process("B2")
    # B2 should be BLOCKED
    assert b_after.state == ProcessState.BLOCKED.value
    assert b_after.error is not None
