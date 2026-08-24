from vennela.automation.process.models import ProcessModel
from vennela.automation.process.manager import ProcessManager
from vennela.automation.persistence.storage_adapter import SQLiteStorageAdapter


def test_full_lifecycle(tmp_path):
    db = tmp_path / "phase1lifec.db"
    storage = SQLiteStorageAdapter(str(db))
    pm = ProcessManager(storage=storage)

    p = ProcessModel(process_id="L1")
    pm.create_process(p)
    assert pm.get_process("L1").state == "PENDING"

    # move to queued
    pm.transition_process("L1", "QUEUED", expected_version=1)
    assert pm.get_process("L1").state == "QUEUED"

    # ready
    pm.transition_process("L1", "READY", expected_version=2)
    assert pm.get_process("L1").state == "READY"

    # running
    pm.transition_process("L1", "RUNNING", expected_version=3)
    assert pm.get_process("L1").state == "RUNNING"

    # complete
    pm.complete_process("L1", result={"ok": True}, expected_version=4)
    assert pm.get_process("L1").state == "COMPLETED"
    assert pm.get_process("L1").result == {"ok": True}
