class MockAndroidAgent:
    def __init__(self, available: bool = True):
        self.available = available

    def execute(self, action: str) -> dict:
        if not self.available:
            raise RuntimeError("Android agent unavailable")
        results = {"FLASHLIGHT": "flashlight toggled", "DEVICE_STATUS": "device online"}
        if action not in results:
            raise ValueError(f"unknown Android action: {action}")
        return {"action": action, "result": results[action], "executed": True}
