import os
from vennela.automation.process.models import ProcessModel
from vennela.automation.process.manager import ProcessManager
from vennela.automation.persistence.storage_adapter import SQLiteStorageAdapter


def _cleanup_db(db_path):
    try:
        os.remove(db_path)
    except Exception:
        pass


def test_create_get_update_process(tmp_path):
    db = tmp_path / "phase1.db"
    storage = SQLiteStorageAdapter(str(db))
    pm = ProcessManager(storage=storage)

    p = ProcessModel(process_id="P100")
    pm.create_process(p)
    fetched = pm.get_process("P100")
    assert fetched is not None
    assert fetched.process_id == "P100"

    # update: change priority
    fetched.priority = 5
    pm.update_process(fetched, expected_version=1)
    fetched2 = pm.get_process("P100")
    assert fetched2.priority == 5

    _cleanup_db(str(db))
