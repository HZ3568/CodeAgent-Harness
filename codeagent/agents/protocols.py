from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from codeagent.agents.bus import MessageBus


@dataclass
class ProtocolState:
    request_id: str
    type: str
    sender: str
    target: str
    status: str
    payload: str
    created_at: float = field(default_factory=time.time)


class ProtocolRegistry:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.pending: dict[str, ProtocolState] = {}

    def new_request_id(self) -> str:
        return f"req_{random.randint(0, 999999):06d}"

    def match_response(self, response_type: str, request_id: str, approve: bool) -> None:
        state = self.pending.get(request_id)
        if not state:
            return
        if state.type == "shutdown" and response_type != "shutdown_response":
            return
        if state.type == "plan_approval" and response_type != "plan_approval_response":
            return
        state.status = "approved" if approve else "rejected"

    def consume_lead_inbox(self, route_protocol: bool = True) -> list[dict]:
        msgs = self.bus.read_inbox("lead")
        if route_protocol:
            for msg in msgs:
                meta = msg.get("metadata", {})
                req_id = meta.get("request_id", "")
                msg_type = msg.get("type", "")
                if req_id and msg_type.endswith("_response"):
                    self.match_response(msg_type, req_id, bool(meta.get("approve", False)))
        return msgs

    def request_shutdown(self, teammate: str) -> str:
        req_id = self.new_request_id()
        self.pending[req_id] = ProtocolState(req_id, "shutdown", "lead", teammate, "pending", "")
        self.bus.send("lead", teammate, "Shut down.", "shutdown_request", {"request_id": req_id})
        return f"Shutdown request sent to {teammate}"

    def request_plan(self, teammate: str, task: str) -> str:
        self.bus.send("lead", teammate, f"Submit plan for: {task}", "message")
        return f"Asked {teammate} to submit a plan"

    def review_plan(self, request_id: str, approve: bool, feedback: str = "") -> str:
        state = self.pending.get(request_id)
        if not state:
            return f"Request {request_id} not found"
        state.status = "approved" if approve else "rejected"
        self.bus.send(
            "lead",
            state.sender,
            feedback or ("Approved" if approve else "Rejected"),
            "plan_approval_response",
            {"request_id": request_id, "approve": approve},
        )
        return f"Plan {'approved' if approve else 'rejected'}"

    def submit_plan_from_teammate(self, from_name: str, plan: str) -> str:
        req_id = self.new_request_id()
        self.pending[req_id] = ProtocolState(req_id, "plan_approval", from_name, "lead", "pending", plan)
        self.bus.send(from_name, "lead", plan, "plan_approval_request", {"request_id": req_id})
        return f"Plan submitted ({req_id})"
