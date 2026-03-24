"""
Jira integration for the coupon-fab-demo app.

Supports both Jira Cloud (API v3) and Jira Server/Data Center (API v2).

Configuration via .streamlit/secrets.toml:

    # ── Jira Cloud ──
    [jira]
    server_type = "cloud"
    base_url    = "https://your-org.atlassian.net"
    email       = "you@example.com"
    api_token   = "your-api-token"
    project_key = "MTE"
    issue_type  = "10005"

    # ── Jira Server / Data Center ──
    [jira]
    server_type = "server"
    base_url    = "http://localhost:8080"
    username    = "admin"
    password    = "admin"
    project_key = "MTE"
    issue_type  = "10005"

All methods fail silently when Jira is not configured or a request fails.
"""

from __future__ import annotations

import os
import requests
from requests.auth import HTTPBasicAuth

try:
    import streamlit as st
    def _cfg():
        cfg = st.secrets.get("jira", {})
        if cfg:
            return cfg
        # Fallback to environment variables (for Docker/K8s deployments)
        return {
            "server_type": os.environ.get("JIRA_SERVER_TYPE", "cloud"),
            "base_url":    os.environ.get("JIRA_BASE_URL", ""),
            "email":       os.environ.get("JIRA_EMAIL", ""),
            "api_token":   os.environ.get("JIRA_API_TOKEN", ""),
            "username":    os.environ.get("JIRA_USERNAME", ""),
            "password":    os.environ.get("JIRA_PASSWORD", ""),
            "project_key": os.environ.get("JIRA_PROJECT_KEY", ""),
            "issue_type":  os.environ.get("JIRA_ISSUE_TYPE", "10001"),
        }
except Exception:
    def _cfg():
        return {}


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_cloud() -> bool:
    return _cfg().get("server_type", "cloud").lower() != "server"

def _auth():
    c = _cfg()
    if _is_cloud():
        return HTTPBasicAuth(c.get("email", ""), c.get("api_token", ""))
    return HTTPBasicAuth(c.get("username", ""), c.get("password", ""))

def _base():
    return _cfg().get("base_url", "").rstrip("/")

def _api():
    """Return the REST API base path for the configured Jira type."""
    return f"{_base()}/rest/api/{'3' if _is_cloud() else '2'}"

def _project():
    return _cfg().get("project_key", "")

def _issue_type_id():
    return _cfg().get("issue_type", "10001")

def _configured():
    c = _cfg()
    has_base = bool(c.get("base_url") and c.get("project_key"))
    if _is_cloud():
        return has_base and bool(c.get("email") and c.get("api_token"))
    return has_base and bool(c.get("username") and c.get("password"))

def _headers():
    return {"Accept": "application/json", "Content-Type": "application/json"}

def _doc(text: str) -> dict:
    """Wrap plain text into Jira ADF (Atlassian Document Format). Cloud only."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }

def _desc(text: str):
    """Return description/comment body in the correct format for Cloud (ADF) or Server (plain string)."""
    return _doc(text) if _is_cloud() else text


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
            f"{_api()}/issue/{ticket}?fields=labels",
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
            f"{_api()}/issue/{ticket}",
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
                "description": _desc(body),
                "issuetype":   {"id": _issue_type_id()},
                "labels":      [_APP_LABEL, _PHASE_LABEL[1]],
            }
        }

        resp = requests.post(
            f"{_api()}/issue",
            json=payload,
            auth=_auth(),
            headers=_headers(),
            timeout=10,
        )
        if resp.ok:
            key = resp.json().get("key", "")
            # Sync custom fields to the new issue
            if key:
                sync_fields_to_issue(key, data, phase=1)
            return key
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
            f"{_api()}/issue/{ticket}/comment",
            json={"body": _desc(full_comment)},
            auth=_auth(),
            headers=_headers(),
            timeout=10,
        )
        ok = resp.ok

        # Update phase label
        _set_phase_label(ticket, new_phase)

        # Sync phase custom field
        sync_phase_to_issue(ticket, new_phase)

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
            f"{_api()}/issue/{ticket}/transitions",
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
            f"{_api()}/issue/{ticket}/transitions",
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
            f"{_api()}/issue/{ticket}/comment",
            json={"body": _desc(close_text)},
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


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOM FIELD SYNC
# ══════════════════════════════════════════════════════════════════════════════

# Fields to create in Jira, mapped from coupons table.
# Format: (field_key, display_name, jira_field_type)
_TEXTFIELD = "com.atlassian.jira.plugin.system.customfieldtypes:textfield"
_TEXTAREA  = "com.atlassian.jira.plugin.system.customfieldtypes:textarea"

_CUSTOM_FIELDS = [
    ("mte_coupon_id",              "MTE Coupon ID",             _TEXTFIELD),
    ("mte_part_number",            "MTE Part Number",           _TEXTFIELD),
    ("mte_current_phase",          "MTE Current Phase",         _TEXTFIELD),
    ("mte_priority",               "MTE Priority",              _TEXTFIELD),
    ("mte_requesting_stakeholder", "MTE Requesting Stakeholder", _TEXTFIELD),
    ("mte_nx_model_ref",           "MTE NX Model Reference",    _TEXTFIELD),
    ("mte_tc_engineering_item",    "MTE TC Engineering Item",    _TEXTFIELD),
    ("mte_description",            "MTE Description",           _TEXTAREA),
    ("mte_notes",                  "MTE Notes",                 _TEXTAREA),
]

# MTE project screen IDs (create + edit/view)
_MTE_SCREENS = [10004, 10005]

# In-memory cache of field_key → customfield_XXXXX ID
_field_id_cache: dict[str, str] = {}


def _load_field_cache() -> dict[str, str]:
    """Scan existing Jira fields and populate the cache with MTE custom fields."""
    global _field_id_cache
    if _field_id_cache:
        return _field_id_cache
    if not _configured():
        return {}
    try:
        resp = requests.get(
            f"{_api()}/field",
            auth=_auth(), headers=_headers(), timeout=15,
        )
        if not resp.ok:
            return {}
        for f in resp.json():
            if f.get("custom") and f["name"].startswith("MTE "):
                # Map by matching display name to our field_key
                for fk, display_name, _ in _CUSTOM_FIELDS:
                    if f["name"] == display_name:
                        _field_id_cache[fk] = f["id"]
                        break
    except Exception:
        pass
    return _field_id_cache


def _add_field_to_screens(field_id: str) -> bool:
    """Add a custom field to the MTE project create + edit/view screens."""
    ok = True
    for screen_id in _MTE_SCREENS:
        try:
            resp = requests.get(
                f"{_api()}/screens/{screen_id}/tabs",
                auth=_auth(), headers=_headers(), timeout=10,
            )
            if not resp.ok or not resp.json():
                ok = False
                continue
            tab_id = resp.json()[0]["id"]
            resp = requests.post(
                f"{_api()}/screens/{screen_id}/tabs/{tab_id}/fields",
                json={"fieldId": field_id},
                auth=_auth(), headers=_headers(), timeout=10,
            )
            if resp.status_code not in (200, 201):
                ok = False
        except Exception:
            ok = False
    return ok


def ensure_custom_fields() -> dict[str, str]:
    """
    Create MTE custom fields in Jira if they don't exist, and add them to
    the project screens. Returns a dict of field_key → customfield_XXXXX.
    """
    cache = _load_field_cache()
    if not _configured():
        return cache

    for fk, display_name, field_type in _CUSTOM_FIELDS:
        if fk in cache:
            continue
        # Create the field
        try:
            payload = {
                "name": display_name,
                "description": f"MTE Coupon Fab workflow field: {fk}",
                "type": field_type,
                "searcherKey": "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher",
            }
            resp = requests.post(
                f"{_api()}/field",
                json=payload,
                auth=_auth(), headers=_headers(), timeout=10,
            )
            if resp.ok:
                data = resp.json()
                cf_id = data["id"]
                cache[fk] = cf_id
                _add_field_to_screens(cf_id)
        except Exception:
            pass

    return cache


def get_field_map() -> dict[str, str]:
    """Return the field_key → customfield_XXXXX mapping, loading cache if needed."""
    return _load_field_cache()


def sync_fields_to_issue(ticket: str, coupon_data: dict, phase: int | None = None) -> bool:
    """
    Update custom field values on a Jira issue from coupon data.
    Call after create_issue or on phase advance to keep Jira fields in sync.
    """
    if not _configured() or not ticket:
        return False
    cache = get_field_map()
    if not cache:
        return False

    fields_payload = {}

    mapping = {
        "mte_coupon_id":              coupon_data.get("coupon_id", ""),
        "mte_part_number":            coupon_data.get("part_number", ""),
        "mte_priority":               coupon_data.get("priority", ""),
        "mte_requesting_stakeholder": coupon_data.get("requesting_stakeholder", ""),
        "mte_nx_model_ref":           coupon_data.get("nx_model_ref", ""),
        "mte_tc_engineering_item":    coupon_data.get("tc_engineering_item", ""),
        "mte_description":            coupon_data.get("description", ""),
        "mte_notes":                  coupon_data.get("notes", ""),
    }
    if phase is not None:
        phase_name = _PHASE_STATUS.get(phase, f"Phase {phase}")
        mapping["mte_current_phase"] = f"Phase {phase} — {phase_name}"

    # Textarea fields need ADF format
    _textarea_keys = {"mte_description", "mte_notes"}

    for fk, value in mapping.items():
        cf_id = cache.get(fk)
        if cf_id and value:
            fields_payload[cf_id] = _doc(value) if fk in _textarea_keys else value

    if not fields_payload:
        return True

    try:
        resp = requests.put(
            f"{_api()}/issue/{ticket}",
            json={"fields": fields_payload},
            auth=_auth(), headers=_headers(), timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


def sync_phase_to_issue(ticket: str, phase: int) -> bool:
    """Update only the MTE Current Phase field on a Jira issue."""
    if not _configured() or not ticket:
        return False
    cache = get_field_map()
    cf_id = cache.get("mte_current_phase")
    if not cf_id:
        return False
    try:
        phase_name = _PHASE_STATUS.get(phase, f"Phase {phase}")
        resp = requests.put(
            f"{_api()}/issue/{ticket}",
            json={"fields": {cf_id: f"Phase {phase} — {phase_name}"}},
            auth=_auth(), headers=_headers(), timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


def field_sync_status() -> dict:
    """Return a status report of field sync configuration."""
    cache = _load_field_cache()
    result = {"configured": _configured(), "fields": {}}
    for fk, display_name, _ in _CUSTOM_FIELDS:
        result["fields"][fk] = {
            "name": display_name,
            "jira_id": cache.get(fk),
            "synced": fk in cache,
        }
    return result
