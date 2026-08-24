from vennela.automation.process.models import ProcessModel
from vennela.automation.process.manager import ProcessManager
from vennela.automation.persistence.storage_adapter import SQLiteStorageAdapter


def test_dependencies_and_circular_detection(tmp_path):
    db = tmp_path / "phase1deps.db"
    storage = SQLiteStorageAdapter(str(db))
    pm = ProcessManager(storage=storage)

    a = ProcessModel(process_id="A")
    b = ProcessModel(process_id="B")
    c = ProcessModel(process_id="C")
    pm.create_process(a)
    pm.create_process(b)
    pm.create_process(c)

    pm.add_dependency("B", "A")
    assert "A" in pm.get_process("B").dependencies

    pm.add_dependency("C", "B")
    assert "B" in pm.get_process("C").dependencies

    # attempt to create circular: A depends on C -> should raise
    try:
        pm.add_dependency("A", "C")
        assert False, "Expected circular dependency rejection"
    except ValueError:
        pass
