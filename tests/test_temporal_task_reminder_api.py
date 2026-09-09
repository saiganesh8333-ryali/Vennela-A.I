"""
Integration tests for Temporal Context, Task, Reminder subsystems, NEXUS Intent Classifier, and FastAPI Endpoints.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
import pytest

from app import app, get_temporal_context, get_task_manager, get_reminder_manager
from core.nexus_intent import NexusIntent, NexusIntentClassifier
from core.temporal import TemporalContext
from llm_router.adapter import VennelaLLMAdapter
from llm_router.gateway import Gateway
from llm_router.providers.mock import MockProvider


@pytest.fixture
def client(monkeypatch):
    fixed = datetime(2026, 9, 10, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    
    import app as app_module
    monkeypatch.setattr(app_module, "_temporal_context", tc)
    
    # Reset managers to clean in-memory state
    from core.tasks import InMemoryTaskRepository, TaskManager
    from core.reminders import InMemoryReminderRepository, ReminderManager
    from core.scheduler import ReminderScheduler
    
    task_repo = InMemoryTaskRepository()
    rem_repo = InMemoryReminderRepository()
    
    tm = TaskManager(repository=task_repo, temporal_context=tc)
    rm = ReminderManager(repository=rem_repo, temporal_context=tc)
    sched = ReminderScheduler(repository=rem_repo, temporal_context=tc)
    
    monkeypatch.setattr(app_module, "_task_manager", tm)
    monkeypatch.setattr(app_module, "_reminder_manager", rm)
    monkeypatch.setattr(app_module, "_reminder_scheduler", sched)
    
    # Mock LLM Adapter so non-intent chats also succeed cleanly
    groq_p = MockProvider("groq", "Mock LLM Response")
    gateway = Gateway.create(custom_providers={"groq": groq_p})
    mock_adapter = VennelaLLMAdapter(router=gateway.router)
    monkeypatch.setattr(app_module, "_llm_adapter_instance", mock_adapter)
    
    return TestClient(app)


# =======================================================
# 1. NEXUS INTENT CLASSIFIER UNIT TESTS
# =======================================================

def test_01_nexus_intent_classification():
    fixed = datetime(2026, 9, 10, 10, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    tc = TemporalContext("Asia/Kolkata", fixed_now=fixed)
    classifier = NexusIntentClassifier(tc)

    # TIME_QUERY
    r1 = classifier.classify("Vennela, what time is it?")
    assert r1.intent == NexusIntent.TIME_QUERY

    # DATE_QUERY
    r2 = classifier.classify("Vennela, what's today's date?")
    assert r2.intent == NexusIntent.DATE_QUERY
    assert r2.entities["target_expr"] == "today"

    r2_tom = classifier.classify("Vennela, what day is tomorrow?")
    assert r2_tom.intent == NexusIntent.DATE_QUERY
    assert r2_tom.entities["target_expr"] == "tomorrow"

    # TASK_CREATE
    r3 = classifier.classify("Create a task to finish my Vennela project tomorrow.")
    assert r3.intent == NexusIntent.TASK_CREATE
    assert "finish my vennela project" in r3.entities["title"].lower()

    # TASK_LIST
    r4 = classifier.classify("Show my tasks for tomorrow.")
    assert r4.intent == NexusIntent.TASK_LIST
    assert r4.entities["due_date_expr"] == "tomorrow"

    # TASK_COMPLETE
    r5 = classifier.classify("Mark my Vennela project task complete.")
    assert r5.intent == NexusIntent.TASK_COMPLETE

    # TASK_CANCEL
    r6 = classifier.classify("Cancel task 123")
    assert r6.intent == NexusIntent.TASK_CANCEL

    # REMINDER_CREATE
    r7 = classifier.classify("Remind me tomorrow at 7 AM to study Maths.")
    assert r7.intent == NexusIntent.REMINDER_CREATE
    assert "Study Maths" in r7.entities["title"]
    assert "tomorrow at 7 am" in r7.entities["remind_expr"].lower()

    r7_b = classifier.classify("Remind me at 11 PM to prepare for tomorrow.")
    assert r7_b.intent == NexusIntent.REMINDER_CREATE
    assert "Prepare For Tomorrow" in r7_b.entities["title"]

    # REMINDER_LIST
    r8 = classifier.classify("Show my reminders.")
    assert r8.intent == NexusIntent.REMINDER_LIST

    # REMINDER_CANCEL
    r9 = classifier.classify("Cancel my 11 PM reminder.")
    assert r9.intent == NexusIntent.REMINDER_CANCEL


# =======================================================
# 2. REST API ENDPOINTS TESTS
# =======================================================

def test_02_time_and_date_endpoints(client):
    # GET /time
    resp_time = client.get("/time")
    assert resp_time.status_code == 200
    time_data = resp_time.json()
    assert time_data["timezone"] == "Asia/Kolkata"
    assert time_data["time"] == "10:00 AM"

    # GET /date
    resp_date = client.get("/date")
    assert resp_date.status_code == 200
    date_data = resp_date.json()
    assert date_data["day_of_week"] == "Thursday"
    assert date_data["iso"] == "2026-09-10"
    assert date_data["tomorrow"]["day_of_week"] == "Friday"
    assert date_data["tomorrow"]["iso"] == "2026-09-11"


def test_03_tasks_rest_endpoints(client):
    # POST /tasks
    create_resp = client.post("/tasks", json={
        "title": "Write Backend Tests",
        "description": "Coverage for Temporal Context",
        "priority": "HIGH",
        "due_expr": "tomorrow at 5 PM",
        "user_id": "boss_user"
    })
    assert create_resp.status_code == 200
    task = create_resp.json()
    task_id = task["task_id"]
    assert task["title"] == "Write Backend Tests"
    assert task["priority"] == "HIGH"
    assert task["status"] == "PENDING"

    # GET /tasks
    list_resp = client.get("/tasks?user_id=boss_user")
    assert list_resp.status_code == 200
    tasks = list_resp.json()
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == task_id

    # GET /tasks/{id}
    get_resp = client.get(f"/tasks/{task_id}?user_id=boss_user")
    assert get_resp.status_code == 200
    assert get_resp.json()["task_id"] == task_id

    # PATCH /tasks/{id}
    patch_resp = client.patch(f"/tasks/{task_id}", json={
        "title": "Updated Test Task Title",
        "user_id": "boss_user"
    })
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Test Task Title"

    # POST /tasks/{id}/complete
    comp_resp = client.post(f"/tasks/{task_id}/complete?user_id=boss_user")
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "COMPLETED"

    # DELETE /tasks/{id}
    del_resp = client.delete(f"/tasks/{task_id}?user_id=boss_user")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "CANCELLED"


def test_04_reminders_rest_endpoints(client):
    # POST /reminders
    create_resp = client.post("/reminders", json={
        "title": "Drink Water",
        "remind_expr": "in 30 minutes",
        "user_id": "boss_user"
    })
    assert create_resp.status_code == 200
    rem = create_resp.json()
    rem_id = rem["reminder_id"]
    assert rem["title"] == "Drink Water"
    assert rem["status"] == "PENDING"

    # GET /reminders
    list_resp = client.get("/reminders?user_id=boss_user")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # GET /reminders/{id}
    get_resp = client.get(f"/reminders/{rem_id}?user_id=boss_user")
    assert get_resp.status_code == 200
    assert get_resp.json()["reminder_id"] == rem_id

    # DELETE /reminders/{id}
    del_resp = client.delete(f"/reminders/{rem_id}?user_id=boss_user")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "CANCELLED"


# =======================================================
# 3. DEMO CONVERSATIONAL FLOWS IN /chat
# =======================================================

def test_05_demo_acceptance_conversational_flows(client):
    # Flow 1: "Vennela, what time is it?"
    r1 = client.post("/chat", json={"message": "Vennela, what time is it?", "user_id": "boss_user"})
    assert r1.status_code == 200
    assert "10:00 AM" in r1.json()["response"]

    # Flow 2: "Vennela, what's today's date?"
    r2 = client.post("/chat", json={"message": "Vennela, what's today's date?", "user_id": "boss_user"})
    assert r2.status_code == 200
    assert "10 September 2026" in r2.json()["response"]

    # Flow 3: "Vennela, what day is tomorrow?"
    r3 = client.post("/chat", json={"message": "Vennela, what day is tomorrow?", "user_id": "boss_user"})
    assert r3.status_code == 200
    assert "Friday" in r3.json()["response"]

    # Flow 4: "Create a task to finish my Vennela project tomorrow."
    r4 = client.post("/chat", json={"message": "Create a task to finish my Vennela project tomorrow.", "user_id": "boss_user"})
    assert r4.status_code == 200
    assert "Task created" in r4.json()["response"]
    assert "finish my Vennela project" in r4.json()["response"]

    # Flow 5: "Show my tasks for tomorrow."
    r5 = client.post("/chat", json={"message": "Show my tasks for tomorrow.", "user_id": "boss_user"})
    assert r5.status_code == 200
    assert "finish my Vennela project" in r5.json()["response"]

    # Flow 6: "Mark my Vennela project task complete."
    r6 = client.post("/chat", json={"message": "Mark my Vennela project task complete.", "user_id": "boss_user"})
    assert r6.status_code == 200
    assert "COMPLETED" in r6.json()["response"]

    # Flow 7: "Remind me at 11 PM to prepare for tomorrow."
    r7 = client.post("/chat", json={"message": "Remind me at 11 PM to prepare for tomorrow.", "user_id": "boss_user"})
    assert r7.status_code == 200
    assert "Reminder set" in r7.json()["response"]
    assert "Prepare For Tomorrow" in r7.json()["response"]

    # Flow 8: "Show my reminders."
    r8 = client.post("/chat", json={"message": "Show my reminders.", "user_id": "boss_user"})
    assert r8.status_code == 200
    assert "Prepare For Tomorrow" in r8.json()["response"]

    # Flow 9: "Cancel my 11 PM reminder."
    r9 = client.post("/chat", json={"message": "Cancel my 11 PM reminder.", "user_id": "boss_user"})
    assert r9.status_code == 200
    assert "Cancelled reminder" in r9.json()["response"]

    # Verify no pending reminders remaining
    r10 = client.post("/chat", json={"message": "Show my reminders.", "user_id": "boss_user"})
    assert r10.status_code == 200
    assert "no pending reminders" in r10.json()["response"].lower()
