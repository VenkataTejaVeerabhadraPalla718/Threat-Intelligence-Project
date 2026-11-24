from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

import rag
import saas
import scanner_bot
from common import db

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    message: str
    session_id: str
    platform: Optional[str] = None
    status: Optional[str] = None

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value):
        return rag.normalize_platform(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        return rag.normalize_status(value)


pending_confirmations: dict[tuple[str, str, str], str] = {}


@router.post("/chat")
def chat_endpoint(req: ChatRequest, user=Depends(saas.current_user)):
    msg = req.message.strip().lower()
    confirmation_key = (user["tenant"], user["sub"], req.session_id)

    if msg == "cancel":
        pending_confirmations.pop(confirmation_key, None)
        return {"reply": "Any pending mitigation commands cancelled."}

    if msg == "scan":
        scan_result = scanner_bot.run_scan(req.platform)
        findings = scan_result["records"]
        if not scan_result["total"]:
            return {
                "reply": (
                    f"Database scan complete for {req.platform or 'all platforms'}. "
                    "No matching MongoDB threat records not marked Resolved were found."
                )
            }

        finding_list = "; ".join(
            f"{finding['id']}: {finding['title']} ({finding['source']})"
            for finding in findings
        )
        return {
            "reply": (
                f"Database scan complete for {req.platform or 'all platforms'}. "
                f"Found {scan_result['total']} matching MongoDB threat records not marked Resolved; "
                f"showing {len(findings)}. Records: {finding_list}. "
                "Type 'fix <vuln_id>' to prepare mitigation."
            )
        }

    if msg.startswith("fix "):
        vuln_id = msg.split(" ", 1)[1].strip()
        pending_confirmations[confirmation_key] = vuln_id
        return {
            "reply": (
                f"Ready to mitigate Threat ID: {vuln_id}. "
                "Type 'yes' to confirm and apply the fix, or 'cancel' to abort."
            )
        }

    if msg == "yes" and confirmation_key in pending_confirmations:
        vuln_id = pending_confirmations.pop(confirmation_key)
        result = scanner_bot.apply_fix(vuln_id)
        return {"reply": result}

    answer = rag.ask_threat_intel(req.message, req.platform, req.status)
    db.chat_history.insert_one(
        {
            "session_id": req.session_id,
            "user": user["sub"],
            "tenant_id": user["tenant"],
            "message": req.message,
            "reply": answer,
            "platform": req.platform,
            "status": req.status,
        }
    )
    return {"reply": answer}
