from typing import Dict
from pydantic import BaseModel


class Capability(BaseModel):
    name: str
    description: str
    input_contract: str
    output_contract: str
    supports_parallel: bool = True
    requires_verification: bool = False
    retryable: bool = False


CAPABILITY_REGISTRY: Dict[str, Capability] = {
    "memory.read": Capability(name="memory.read", description="Read relevant memory", input_contract="VennelaState", output_contract="memory_context"),
    "web.research": Capability(name="web.research", description="Retrieve structured web evidence", input_contract="CanonicalIntent", output_contract="WebEvidence[]"),
    "pc.battery_status": Capability(name="pc.battery_status", description="Read PC battery", input_contract="CanonicalIntent", output_contract="tool_results.pc", requires_verification=True, retryable=True),
    "pc.open_app": Capability(name="pc.open_app", description="Open a PC application", input_contract="CanonicalIntent", output_contract="tool_results.pc", requires_verification=True, retryable=True),
    "pc.device_time": Capability(name="pc.device_time", description="Read PC time", input_contract="CanonicalIntent", output_contract="tool_results.pc", requires_verification=True, retryable=True),
    "android.flashlight": Capability(name="android.flashlight", description="Toggle Android flashlight", input_contract="CanonicalIntent", output_contract="tool_results.android", requires_verification=True, retryable=True),
    "android.device_status": Capability(name="android.device_status", description="Read Android status", input_contract="CanonicalIntent", output_contract="tool_results.android", requires_verification=True, retryable=True),
    "reasoning.answer": Capability(name="reasoning.answer", description="Synthesize structured context", input_contract="VennelaState", output_contract="reasoning_context"),
    "verification.verify": Capability(name="verification.verify", description="Verify capability results", input_contract="VennelaState", output_contract="verification_results"),
    "response.compose": Capability(name="response.compose", description="Compose an honest response", input_contract="VennelaState", output_contract="response"),
}
