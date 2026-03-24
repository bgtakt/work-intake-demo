"""
User Feedback Tool — floating button + dialog with tabs for
documentation, ticket submission, and ticket viewer.
"""

from __future__ import annotations

import base64
import os
import streamlit as st
import db


# ── PATHS ─────────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
_README_PATH = os.path.join(_DIR, "README.md")

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
_TICKET_TYPES = ["Recommendation", "Fix-it", "Bug Report", "General Feedback"]
_PRIORITIES = ["Low", "Medium", "High", "Critical"]
_STATUSES = ["Open", "In Progress", "Resolved", "Closed"]
_MAX_SCREENSHOT_MB = 5


def _priority_color(p: str) -> str:
    return {"Low": "#00e888", "Medium": "#ffc400", "High": "#ff5555", "Critical": "#ff2222"}.get(p, "#aaa")


def _status_color(s: str) -> str:
    return {"Open": "#00d4ff", "In Progress": "#ffc400", "Resolved": "#00cc77", "Closed": "#1a5060"}.get(s, "#aaa")


def _type_color(t: str) -> str:
    return {
        "Recommendation": "#00d4ff",
        "Fix-it": "#ffc400",
        "Bug Report": "#ff5555",
        "General Feedback": "#00e888",
    }.get(t, "#aaa")


# ── FLOATING BUTTON CSS ──────────────────────────────────────────────────────

FEEDBACK_FAB_CSS = """
<style>
/* Floating feedback button */
.feedback-fab {
    position: fixed;
    bottom: 28px;
    right: 28px;
    z-index: 999999;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: rgba(0,212,255,0.12);
    border: 1px solid #00d4ff;
    color: #00f5ff;
    font-size: 1.3em;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    box-shadow: 0 0 12px rgba(0,245,255,0.15);
}
.feedback-fab:hover {
    background: rgba(0,212,255,0.25);
    box-shadow: 0 0 22px rgba(0,245,255,0.5);
    border-color: #00f5ff;
}
/* Hide FAB when a dialog is open */
[data-testid="stModal"] ~ div .feedback-fab { display: none; }
</style>
"""


# ── DIALOG ────────────────────────────────────────────────────────────────────

@st.dialog("◈ USER FEEDBACK", width="large")
def feedback_dialog():
    """Feedback panel with Documentation, Submit Ticket, and View Tickets tabs."""

    # Dialog styling
    st.markdown(
        '<style>'
        '[data-testid="stModal"] {'
        '  position:fixed !important;'
        '  top:0 !important; left:0 !important;'
        '  width:100% !important; height:100% !important;'
        '  overflow:hidden !important;'
        '}'
        'div[role="dialog"] {'
        '  background:#2F4F4E !important;'
        '  border:2px solid #00f5ff !important;'
        '  box-shadow:0 0 32px rgba(0,245,255,0.22) !important;'
        '  max-height:88vh !important;'
        '  overflow-y:auto !important;'
        '}'
        '</style>',
        unsafe_allow_html=True,
    )

    tab_docs, tab_submit, tab_view = st.tabs([
        "DOCUMENTATION",
        "SUBMIT TICKET",
        "VIEW TICKETS",
    ])

    # ── TAB 1: DOCUMENTATION ──────────────────────────────────────────────────
    with tab_docs:
        _render_documentation()

    # ── TAB 2: SUBMIT TICKET ─────────────────────────────────────────────────
    with tab_submit:
        _render_submit_form()

    # ── TAB 3: VIEW TICKETS ──────────────────────────────────────────────────
    with tab_view:
        _render_ticket_list()


def _render_documentation():
    """Render README.md content."""
    if os.path.exists(_README_PATH):
        with open(_README_PATH, encoding="utf-8") as f:
            content = f.read()
        st.markdown(content)
    else:
        st.markdown(
            '<div style="color:#ffc400;padding:20px;text-align:center">'
            'Documentation file not found.</div>',
            unsafe_allow_html=True,
        )


def _render_submit_form():
    """Ticket submission form."""
    user = st.session_state.get("user") or {}
    username = user.get("username", "anonymous")
    display_name = user.get("display_name", "Anonymous")

    # Check for just-submitted state
    if st.session_state.get("_fb_submitted"):
        tid = st.session_state.get("_fb_ticket_id", "")
        st.markdown(
            f'<div style="padding:18px;border:1px solid #00d4ff;background:#0e2a40;'
            f'border-radius:2px;text-align:center;margin:12px 0">'
            f'<div style="font-size:1.1em;color:#00d4ff;letter-spacing:0.15em">TICKET SUBMITTED</div>'
            f'<div style="color:#c0d8e0;margin-top:6px">Ticket #{tid}</div>'
            f'<div style="color:#5aaccc;font-size:0.83em;margin-top:8px">'
            f'Thank you for your feedback. View it in the "VIEW TICKETS" tab.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Submit Another", key="fb_another"):
            st.session_state.pop("_fb_submitted", None)
            st.session_state.pop("_fb_ticket_id", None)
            st.rerun()
        return

    st.markdown(
        '<div style="color:#00d4ff;font-size:0.82em;letter-spacing:0.1em;margin-bottom:10px">'
        'SUBMIT FEEDBACK OR FIX-IT TICKET</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        ticket_type = st.selectbox("TYPE", _TICKET_TYPES, key="fb_type")
    with col2:
        priority = st.selectbox("PRIORITY", _PRIORITIES, index=1, key="fb_priority")

    title = st.text_input("TITLE *", key="fb_title", placeholder="Brief summary of your feedback…")
    description = st.text_area(
        "DESCRIPTION *", key="fb_desc", height=120,
        placeholder="Detailed description of the issue, recommendation, or feedback…",
    )

    st.markdown(
        '<div style="color:#5aaccc;font-size:0.78em;margin-bottom:4px">SCREENSHOT (optional, max 5MB)</div>',
        unsafe_allow_html=True,
    )
    screenshot = st.file_uploader(
        "screenshot", type=["png", "jpg", "jpeg", "gif"],
        key="fb_screenshot", label_visibility="collapsed",
    )

    if screenshot:
        if screenshot.size > _MAX_SCREENSHOT_MB * 1024 * 1024:
            st.markdown(
                f'<div style="color:#ff5555;font-size:0.85em">'
                f'Screenshot exceeds {_MAX_SCREENSHOT_MB}MB limit.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.image(screenshot, width=300)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("SUBMIT TICKET", key="fb_submit", use_container_width=True):
        if not title.strip():
            st.markdown('<div style="color:#ffc400;font-size:0.85em">Title is required.</div>', unsafe_allow_html=True)
        elif not description.strip():
            st.markdown('<div style="color:#ffc400;font-size:0.85em">Description is required.</div>', unsafe_allow_html=True)
        else:
            # Process screenshot
            ss_b64, ss_name = None, None
            if screenshot and screenshot.size <= _MAX_SCREENSHOT_MB * 1024 * 1024:
                ss_b64 = base64.b64encode(screenshot.read()).decode("utf-8")
                ss_name = screenshot.name

            tid = db.create_feedback_ticket(
                ticket_type=ticket_type,
                title=title.strip(),
                description=description.strip(),
                priority=priority,
                screenshot_b64=ss_b64,
                screenshot_name=ss_name,
                submitted_by=username,
                display_name=display_name,
            )
            st.session_state["_fb_submitted"] = True
            st.session_state["_fb_ticket_id"] = tid
            st.rerun()


def _render_ticket_list():
    """View all submitted feedback tickets."""
    tickets = db.list_feedback_tickets()
    if not tickets:
        st.markdown(
            '<div style="color:#1a5060;padding:20px;text-align:center;font-size:0.9em">'
            'No feedback tickets submitted yet.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div style="color:#00d4ff;font-size:0.82em;letter-spacing:0.1em;margin-bottom:10px">'
        f'FEEDBACK TICKETS &nbsp;'
        f'<span style="color:#5aaccc;font-size:0.9em">[{len(tickets)}]</span></div>',
        unsafe_allow_html=True,
    )

    for t in tickets:
        tc = _type_color(t["ticket_type"])
        pc = _priority_color(t["priority"])
        sc = _status_color(t["status"])
        ts = (t.get("submitted_at") or "")[:16]

        st.markdown(
            f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid {tc};'
            f'padding:10px 14px;margin:6px 0;border-radius:2px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<span style="color:#00d4ff;font-weight:bold">#{t["id"]}</span> &nbsp;'
            f'<span style="color:#c0d8e0">{t["title"]}</span>'
            f'</div>'
            f'<div>'
            f'<span style="background:rgba(0,0,0,0.3);border:1px solid {tc};color:{tc};'
            f'font-size:0.7em;padding:2px 6px;border-radius:2px;margin-right:6px">{t["ticket_type"]}</span>'
            f'<span style="background:rgba(0,0,0,0.3);border:1px solid {pc};color:{pc};'
            f'font-size:0.7em;padding:2px 6px;border-radius:2px;margin-right:6px">{t["priority"]}</span>'
            f'<span style="background:rgba(0,0,0,0.3);border:1px solid {sc};color:{sc};'
            f'font-size:0.7em;padding:2px 6px;border-radius:2px">{t["status"]}</span>'
            f'</div>'
            f'</div>'
            f'<div style="color:#1a5060;font-size:0.75em;margin-top:4px">'
            f'by {t["display_name"]} &nbsp;·&nbsp; {ts}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.expander(f"Details — #{t['id']}", expanded=False):
            st.markdown(f"**Description:**\n\n{t['description']}")

            if t.get("screenshot_b64"):
                st.markdown(
                    f'<div style="color:#5aaccc;font-size:0.78em;margin:8px 0 4px">SCREENSHOT: {t.get("screenshot_name", "image")}</div>',
                    unsafe_allow_html=True,
                )
                st.image(base64.b64decode(t["screenshot_b64"]))

            # Status update
            col1, col2 = st.columns([2, 1])
            with col1:
                new_status = st.selectbox(
                    "Update Status", _STATUSES,
                    index=_STATUSES.index(t["status"]) if t["status"] in _STATUSES else 0,
                    key=f"fb_status_{t['id']}",
                )
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("UPDATE", key=f"fb_update_{t['id']}"):
                    db.update_feedback_status(t["id"], new_status)
                    st.session_state["_fb_status_updated"] = t["id"]
                    st.session_state["_fb_status_updated_to"] = new_status
                    st.rerun()

            # Show notification inline under this ticket's update button
            if st.session_state.get("_fb_status_updated") == t["id"]:
                updated_to = st.session_state.pop("_fb_status_updated_to", "")
                st.session_state.pop("_fb_status_updated", None)
                sc = _status_color(updated_to)
                st.markdown(
                    f'<div style="padding:8px 14px;border:1px solid {sc};background:rgba(0,204,119,0.08);'
                    f'border-left:3px solid {sc};border-radius:2px;margin-top:6px">'
                    f'<span style="color:{sc};font-size:0.85em">✓ Status updated to <strong>{updated_to}</strong></span></div>',
                    unsafe_allow_html=True,
                )


