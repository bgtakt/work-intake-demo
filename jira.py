"""
Jira integration for the coupon-fab-demo app.

Reads connection settings from .streamlit/secrets.toml under [jira]:
    [jira]
    base_url    = "https://your-org.atlassian.net"
    email       = "you@example.com"
    api_token   = "your-api-token"
    project_key = "MTE"
    issue_type  = "10005"    # issue type ID (numeric string)

All methods fail silently when Jira is not configured or a request fails.
"""

from __future__ import annotations

import requests
from requests.auth import HTTPBasicAuth

try:
    import streamlit as st
    def _cfg():
        return st.secrets.get("jira", {})
except Exception:
    def _cfg():
        return {}


# ── helpers ───────────────────────────────────────────────────────────────────

def _auth():
    c = _cfg()
    return HTTPBasicAuth(c.get("email", ""), c.get("api_token", ""))

def _base():
    return _cfg().get("base_url", "").rstrip("/")

def _project():
    return _cfg().get("project_key", "")

def _issue_type_id():
    return _cfg().get("issue_type", "10001")

def _configured():
    c = _cfg()
    return bool(c.get("base_url") and c.get("email") and c.get("api_token") and c.get("project_key"))

def _headers():
    return {"Accept": "application/json", "Content-Type": "application/json"}

def _doc(text: str) -> dict:
    """Wrap plain text into Jira ADF (Atlassian Document Format)."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


# ── phase → label / status mapping ────────────────────────────────────────────

_PHASE_STATUS = {
    1: "To Do · In Design",
    2: "Alignment Sign-Off",
    3: "NX Design / TC EBOM",
    4: "Procurement",
    5: "Work Instructions",
    6: "Resourcing",
    7: "Material Receiving",
    8: "Work Execution",
    9: "NCR Review",
}

_PHASE_LABEL = {
    1: "phase-1-design-request",
    2: "phase-2-alignment",
    3: "phase-3-design",
    4: "phase-4-procurement",
    5: "phase-5-work-instructions",
    6: "phase-6-resourcing",
    7: "phase-7-receiving",
    8: "phase-8-execution",
    9: "phase-9-ncr",
}

_APP_LABEL = "coupon-fab"


def _set_phase_label(ticket: str, new_phase: int) -> bool:
    """Replace the phase-* label on a ticket with the label for new_phase."""
    if not _configured() or not ticket:
        return False
    try:
        # Fetch current labels
        resp = requests.get(
            f"{_base()}/rest/api/3/issue/{ticket}?fields=labels",
            auth=_auth(), headers=_headers(), timeout=10,
        )
        if not resp.ok:
            return False
        current = resp.json()["fields"].get("labels", [])

        # Remove any existing phase-* labels, keep everything else
        kept = [lbl for lbl in current if not lbl.startswith("phase-")]
        # Add new phase label
        new_label = _PHASE_LABEL.get(new_phase)
        if new_label:
            kept.append(new_label)

        resp = requests.put(
            f"{_base()}/rest/api/3/issue/{ticket}",
            json={"fields": {"labels": kept}},
            auth=_auth(), headers=_headers(), timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


# ── public API ────────────────────────────────────────────────────────────────

def issue_url(ticket: str) -> str:
    """Return a browse URL for the given Jira ticket key."""
    if not ticket:
        return "#"
    base = _base()
    return f"{base}/browse/{ticket}" if base else "#"


def create_issue(data: dict) -> str:
    """
    Create a Jira issue for a new coupon request.
    Returns the issue key (e.g. 'MTE-42') on success, empty string on failure.
    """
    if not _configured():
        return ""
    try:
        coupon_id   = data.get("coupon_id", "")
        part_number = data.get("part_number", "")
        description = data.get("description", "")
        priority    = data.get("priority", "Medium")
        stakeholder = data.get("requesting_stakeholder", "")
        nx_ref      = data.get("nx_model_ref", "")
        tc_item     = data.get("tc_engineering_item", "")
        notes       = data.get("notes", "")

        summary = f"[{coupon_id}] Coupon Fab Request — {part_number}"
        body = (
            f"Work Order: {coupon_id}\n"
            f"Part Number: {part_number}\n"
            f"Priority: {priority}\n"
            f"Requesting Stakeholder: {stakeholder}\n"
            f"NX Model Reference: {nx_ref}\n"
            f"TC Engineering Item: {tc_item}\n"
            f"Description: {description}\n"
        )
        if notes:
            body += f"Notes: {notes}\n"

        payload = {
            "fields": {
                "project":     {"key": _project()},
                "summary":     summary,
                "description": _doc(body),
                "issuetype":   {"id": _issue_type_id()},
                "labels":      [_APP_LABEL, _PHASE_LABEL[1]],
            }
        }

        resp = requests.post(
            f"{_base()}/rest/api/3/issue",
            json=payload,
            auth=_auth(),
            headers=_headers(),
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("key", "")
    except Exception:
        pass
    return ""


def advance_phase(ticket: str, new_phase: int, comment: str = "") -> bool:
    """
    Add a comment to the Jira issue noting the phase advance.
    Transitions to 'In Progress' when Phase 2 completes (new_phase == 3).
    Returns True on success, False on failure.
    """
    if not _configured() or not ticket:
        return False
    try:
        status_label = _PHASE_STATUS.get(new_phase, f"Phase {new_phase}")
        full_comment = f"Phase advanced → {status_label}"
        if comment:
            full_comment += f"\n\n{comment}"

        resp = requests.post(
            f"{_base()}/rest/api/3/issue/{ticket}/comment",
            json={"body": _doc(full_comment)},
            auth=_auth(),
            headers=_headers(),
            timeout=10,
        )
        ok = resp.ok

        # Update phase label
        _set_phase_label(ticket, new_phase)

        # Phase 2 complete → move Jira to In Progress
        if new_phase == 3:
            transition_issue(ticket, "in progress")

        return ok
    except Exception:
        return False


def transition_issue(ticket: str, to_status: str) -> bool:
    """
    Transition a Jira issue to the named status (case-insensitive match).
    Fetches available transitions, finds one whose name contains to_status,
    and executes it. Returns True on success, False on failure.
    """
    if not _configured() or not ticket:
        return False
    try:
        resp = requests.get(
            f"{_base()}/rest/api/3/issue/{ticket}/transitions",
            auth=_auth(),
            headers=_headers(),
            timeout=10,
        )
        if not resp.ok:
            return False
        transitions = resp.json().get("transitions", [])
        target = next(
            (
                t for t in transitions
                if to_status.lower() in t.get("to", {}).get("name", "").lower()
            ),
            None,
        )
        if not target:
            return False
        resp = requests.post(
            f"{_base()}/rest/api/3/issue/{ticket}/transitions",
            json={"transition": {"id": target["id"]}},
            auth=_auth(),
            headers=_headers(),
            timeout=10,
        )
        return resp.ok
    except Exception:
        return False


def close_issue(ticket: str, comment: str = "") -> dict:
    """
    Add a closing comment and transition the Jira issue to Done.
    Returns a dict with keys label_ok, comment_ok, transition_ok.
    """
    result = {"label_ok": False, "comment_ok": False, "transition_ok": False}
    if not _configured() or not ticket:
        return result

    # Add closing comment
    try:
        close_text = comment or "Work order closed."
        resp = requests.post(
            f"{_base()}/rest/api/3/issue/{ticket}/comment",
            json={"body": _doc(close_text)},
            auth=_auth(),
            headers=_headers(),
            timeout=10,
        )
        result["comment_ok"] = resp.ok
    except Exception:
        pass

    # Transition to Done (looks up transition by name, works from any state)
    ok = transition_issue(ticket, "done")
    result["transition_ok"] = ok
    result["label_ok"] = ok

    return result
