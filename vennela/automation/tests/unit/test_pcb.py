from vennela.automation.process.pcb import PCB
from vennela.automation.process.models import ProcessModel
from vennela.automation.process.states import ProcessState, InvalidStateTransition


def test_pcb_transition_valid():
    p = ProcessModel(process_id="P1")
    pcb = PCB(p)
    pcb.transition(ProcessState.QUEUED.value)
    assert p.state == ProcessState.QUEUED.value


def test_pcb_transition_invalid():
    p = ProcessModel(process_id="P2")
    pcb = PCB(p)
    try:
        pcb.transition("NON_EXISTENT")
        assert False, "Should have raised"
    except InvalidStateTransition:
        pass
