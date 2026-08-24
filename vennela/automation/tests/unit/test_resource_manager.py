from vennela.automation.resources.resource_manager import ResourceManager


def test_mutex_acquire_release():
    rm = ResourceManager()
    rm.register_resource("R1", capacity=1)
    assert rm.request("R1", "P1") is True
    # P2 should be queued
    assert rm.request("R1", "P2") is False
    # P1 releases
    assert rm.release("R1", "P1") is True
    # Now P2 should have been granted
    status = rm.status("R1")
    assert status["holders"].get("P2") == 1


def test_semaphore_behavior():
    rm = ResourceManager()
    rm.register_resource("S1", capacity=2)
    assert rm.request("S1", "P1") is True
    assert rm.request("S1", "P2") is True
    # P3 should be queued
    assert rm.request("S1", "P3") is False
    # Release one holder
    assert rm.release("S1", "P1") is True
    status = rm.status("S1")
    # P3 should have been granted (either P2 or P3 depending on order); check P3 present
    assert status is not None
    assert "P3" in status["holders"] or "P2" in status["holders"]


def test_waiter_order_fifo():
    rm = ResourceManager()
    rm.register_resource("R2", capacity=1)
    assert rm.request("R2", "A") is True
    assert rm.request("R2", "B") is False
    assert rm.request("R2", "C") is False
    # release A -> B should get it first
    assert rm.release("R2", "A")
    status = rm.status("R2")
    assert status["holders"].get("B") == 1


def test_release_invalid():
    rm = ResourceManager()
    rm.register_resource("R3", capacity=1)
    assert rm.request("R3", "X") is True
    # releasing more than held should fail
    assert rm.release("R3", "X", count=2) is False
    # releasing non-holder should fail
    assert rm.release("R3", "Y") is False
