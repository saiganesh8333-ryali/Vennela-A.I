class MockPCAgent:
    def __init__(self, fail: bool = False, fail_times: int = 0):
        self.fail = fail
        self.remaining_failures = fail_times

    def execute(self, action: str) -> dict:
        if self.fail or self.remaining_failures:
            if self.remaining_failures:
                self.remaining_failures -= 1
            raise RuntimeError("PC agent failure")
        results = {"OPEN_APP": "opened calculator", "GET_DEVICE_TIME": "12:00", "BATTERY_STATUS": "battery 87%"}
        if action not in results:
            raise ValueError(f"unknown PC action: {action}")
        return {"action": action, "result": results[action], "executed": True}
