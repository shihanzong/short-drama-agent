#!/usr/bin/env python3
"""
人工确认流程 - Approval Workflow
"""

import json
from pathlib import Path
from datetime import datetime

SKILL_ROOT = Path(__file__).parent.parent

STAGES = [
    {"id": "topic_review", "name": "选题确认", "order": 1},
    {"id": "script_review", "name": "脚本确认", "order": 2},
    {"id": "copy_review", "name": "文案确认", "order": 3},
    {"id": "production_review", "name": "制作确认", "order": 4},
    {"id": "publish_review", "name": "发布确认", "order": 5},
]


class ApprovalWorkflow:
    """人工确认流程管理器"""
    
    def __init__(self, approval_dir: str = None):
        if approval_dir is None:
            approval_dir = SKILL_ROOT / 'approvals'
        self.approval_dir = Path(approval_dir)
        self.approval_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, session_id: str = None, topic: str = "",
                       source: str = "") -> dict:
        if session_id is None:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            session_id = f"session_{ts}"
        
        session = {
            "session_id": session_id,
            "topic": topic,
            "source": source,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "stages": [
                {"stage_id": s["id"], "stage_name": s["name"], "order": s["order"],
                 "status": "pending", "submitted_at": None,
                 "approved_by": None, "approved_at": None, "notes": ""}
                for s in STAGES
            ]
        }
        self._save(session)
        return session
    
    def get_session(self, session_id: str):
        fp = self.approval_dir / f"{session_id}.json"
        if fp.exists():
            return json.loads(fp.read_text(encoding='utf-8'))
        return None
    
    def approve(self, session_id: str, stage_id: str, approver: str = "user",
                notes: str = "") -> dict:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在：{session_id}")
        for stage in session["stages"]:
            if stage["stage_id"] == stage_id:
                stage["status"] = "approved"
                stage["approved_by"] = approver
                stage["approved_at"] = datetime.now().isoformat()
                stage["notes"] = notes
                session["updated_at"] = datetime.now().isoformat()
                break
        self._save(session)
        return session
    
    def reject(self, session_id: str, stage_id: str, approver: str = "user",
               notes: str = "") -> dict:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在：{session_id}")
        for stage in session["stages"]:
            if stage["stage_id"] == stage_id:
                stage["status"] = "rejected"
                stage["approved_by"] = approver
                stage["approved_at"] = datetime.now().isoformat()
                stage["notes"] = notes
                session["updated_at"] = datetime.now().isoformat()
                break
        self._save(session)
        return session
    
    def get_progress(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        if not session:
            return {"error": "会话不存在"}
        
        total = len(session["stages"])
        approved = sum(1 for s in session["stages"] if s["status"] == "approved")
        rejected = sum(1 for s in session["stages"] if s["status"] == "rejected")
        pending = sum(1 for s in session["stages"] if s["status"] == "pending")
        
        return {
            "session_id": session_id,
            "topic": session["topic"],
            "total": total, "approved": approved,
            "rejected": rejected, "pending": pending,
            "progress_percent": round(approved / total * 100, 1) if total > 0 else 0,
            "stages": session["stages"]
        }
    
    def format_progress(self, progress: dict) -> str:
        lines = ["=" * 40, "人工确认进度", "=" * 40 + "\n"]
        lines.append(f"会话：{progress.get('session_id', 'N/A')}")
        lines.append(f"主题：{progress.get('topic', 'N/A')}")
        lines.append(f"进度：{progress.get('progress_percent', 0)}% ({progress.get('approved', 0)}/{progress.get('total', 0)})\n")
        
        status_map = {"approved": "✅ 已确认", "rejected": "❌ 已拒绝", "pending": "⏳ 待确认"}
        for stage in progress.get("stages", []):
            status = status_map.get(stage["status"], "❓ 未知")
            lines.append(f"  [{status}] {stage['stage_name']}")
            if stage.get("approved_by"):
                lines.append(f"       确认人：{stage['approved_by']}")
            if stage.get("notes"):
                lines.append(f"       备注：{stage['notes']}")
        
        return "\n".join(lines)
    
    def _save(self, session: dict):
        fp = self.approval_dir / f"{session['session_id']}.json"
        fp.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding='utf-8')


def create_approval_session(topic: str = "", source: str = "") -> dict:
    workflow = ApprovalWorkflow()
    return workflow.create_session(topic=topic, source=source)
