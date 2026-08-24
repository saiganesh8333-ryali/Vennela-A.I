from vennela.automation.process.models import ProcessModel
from vennela.automation.persistence.storage_adapter import SQLiteStorageAdapter


def test_persistence_roundtrip(tmp_path):
    db = tmp_path / "phase1persist.db"
    storage = SQLiteStorageAdapter(str(db))
    p = ProcessModel(process_id="PX")
    storage.create(p.process_id, p.to_dict(), p.version)
    fetched = storage.get("PX")
    assert fetched is not None
    assert fetched["process_id"] == "PX"
    # update
    fetched["priority"] = 9
    storage.update("PX", fetched, expected_version=1)
    fetched2 = storage.get("PX")
    assert fetched2["priority"] == 9
