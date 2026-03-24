import streamlit as st
import json
import os
import base64
import db
import viz
import jira as jira_api
import feedback

st.set_page_config(
    page_title="WORK INTAKE | MTE",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

db.init_db()

# ── PHASE / ROLE METADATA ────────────────────────────────────────────────────
PHASE_META = {
    1: dict(name="Initiate Design Request",          roles="Stakeholder · DE · ME · Weld Engineer", page="phase1"),
    2: dict(name="Align on Design, Fab & MFG",       roles="DE · ME · Weld Engineer",               page="phase2"),
    3: dict(name="NX Design + TC EBOM Creation",     roles="DE",                                    page="phase3"),
    4: dict(name="Procurement / Scheduling",         roles="Supply Chain",                          page="phase4"),
    5: dict(name="Work Instructions",                roles="ME · Weld Engineer · QE",               page="phase5"),
    6: dict(name="Resourcing / Work Allocation",     roles="IE",                                    page="phase6"),
    7: dict(name="Material Receiving",               roles="Supply Chain · QE · Warehouse/MMO",     page="phase7"),
    8: dict(name="WORK EXECUTION",                   roles="Mechanic · ME · QE",                    page="phase8"),
    9: dict(name="Non-Conformance (NCR)",            roles="QE · ME · Mechanic",                    page="phase9"),
}

ROLE_PHASES = {
    "Stakeholder":   [1],
    "DE":            [1, 2, 3],
    "ME":            [1, 2, 3, 5],
    "Weld Engineer": [1, 2, 5],
    "Supply Chain":  [4, 7],
    "IE":            [6],
    "QE":            [5, 7, 8, 9],
    "Warehouse/MMO": [7],
    "Mechanic":      [8],
}

# ── SESSION STATE ────────────────────────────────────────────────────────────
_DEFAULTS = dict(auth=False, user=None, page="mode_select", coupon_id=None, errs={}, nav_phase=None, mode=None, show_feedback=False)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── QUERY PARAM NAV (handles ?nav=N from SVG node clicks & arrow keys) ───────
_qp_nav = st.query_params.get("nav")
_is_preview_nav = st.session_state.get("mode") == "preview"
if _qp_nav and (st.session_state.auth or _is_preview_nav):
    _phase_num = int(_qp_nav)
    st.query_params.clear()
    if _is_preview_nav:
        # Preview mode: route directly to any phase page, no coupon lookup required
        st.session_state.page = f"phase{_phase_num}"
        st.session_state.nav_phase = _phase_num
    else:
        # Demo mode: enforce coupon-aware routing
        if _phase_num == 1:
            st.session_state.page = "phase1"
        elif 2 <= _phase_num <= 9:
            _match = next((c for c in db.list_coupons() if c["current_phase"] == _phase_num), None)
            if _match:
                st.session_state.coupon_id = _match["coupon_id"]
                st.session_state.page = f"phase{_phase_num}"
            elif st.session_state.coupon_id:
                st.session_state.page = f"phase{_phase_num}"
            else:
                st.session_state.page = f"phase{_phase_num}"
                st.session_state.nav_phase = _phase_num
    st.session_state.errs = {}
    st.rerun()


# ── TRON CSS ─────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');

html, body, .stApp { background-color: #0c192b !important; }
#MainMenu, footer, header, .stDeployButton { visibility: hidden; display: none; }

* { font-family: 'Share Tech Mono', 'Courier New', monospace !important; }

h1, h2, h3 {
    color: #00f5ff !important;
    letter-spacing: 0.15em !important;
    text-shadow: 0 0 12px rgba(0,245,255,0.45) !important;
}

/* Inputs */
.stTextInput input, .stTextArea textarea {
    background: #0c1f2e !important;
    border: 1px solid #1e5068 !important;
    color: #d8eef5 !important;
    border-radius: 2px !important;
}

/* Textarea — brighter background to distinguish from notification messages */
.stTextArea textarea {
}
/* Password eye icon — keep placeholder text from overlapping the toggle button */
.stTextInput input[type="password"] {
    padding-right: 2.5rem !important;
}
/* Hide "Press Enter to submit form" tooltip on focused inputs */
[data-testid="InputInstructions"] { display: none !important; }
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #00f5ff !important;
    box-shadow: none !important;
}

/* Selectbox / date input */
.stSelectbox > div > div,
.stDateInput input {
    background: #0c1f2e !important;
    border: 1px solid #1e5068 !important;
    color: #d8eef5 !important;
    border-radius: 2px !important;
}

/* Buttons */
.stButton > button {
    background: rgba(0,212,255,0.06) !important;
    border: 1px solid #00d4ff !important;
    color: #00f5ff !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    border-radius: 2px !important;
    transition: all 0.15s ease !important;
    text-shadow: 0 0 8px rgba(0,245,255,0.6) !important;
}
.stButton > button:hover {
    background: rgba(0,245,255,0.15) !important;
    border-color: #00f5ff !important;
    box-shadow: 0 0 18px rgba(0,245,255,0.6) !important;
    text-shadow: 0 0 12px rgba(0,245,255,1) !important;
}

/* Checkbox */
.stCheckbox label { color: #d8eef5 !important; }

/* Progress bar */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #00aacc, #00f5ff) !important;
    box-shadow: 0 0 8px rgba(0,245,255,0.5) !important;
}

/* Jira badge */
@keyframes jira-pulse {
    0%, 100% { box-shadow: 0 0 6px rgba(0,102,238,0.5); }
    50%       { box-shadow: 0 0 14px rgba(0,102,238,0.95), 0 0 4px #fff; }
}
a.jira-badge {
    animation: jira-pulse 2s ease-in-out infinite;
    cursor: pointer !important;
    transition: background 0.15s, transform 0.12s !important;
}
a.jira-badge:hover {
    background: #1a7fff !important;
    transform: translateY(-1px) !important;
    animation: none !important;
    box-shadow: 0 0 16px rgba(0,140,255,0.8) !important;
}

[data-testid="stIconMaterial"] {
    font-size: 0 !important;
    display: inline-block;
}

[data-testid="stIconMaterial"]::after {
   content: "▶";
   font-size: 16px;
   display: inline-block;
   transition: transform 0.2s;
}

[aria-expanded="true"] [data-testid="stIconMaterial"]::after {
   content: "▼"
}

/* Divider */
hr { border-color: #1e4060 !important; margin: 8px 0 !important; }

/* Metric */
[data-testid="stMetricValue"] {
    color: #00f5ff !important;
    text-shadow: 0 0 10px rgba(0,245,255,0.5) !important;
}

/* Amber gap highlighting */
.err-msg {
    color: #ffc400;
    font-size: 0.78em;
    margin-top: -10px;
    margin-bottom: 6px;
    display: block;
    text-shadow: 0 0 6px rgba(255,196,0,0.5);
}
.err-label { color: #ffc400 !important; }

/* Amber border on inputs that follow an .err-label div */
div:has(> .err-label) + div .stTextInput input,
div:has(> .err-label) + div .stTextArea textarea {
    border-color: #ffc400 !important;
    box-shadow: 0 0 8px rgba(255,196,0,0.35) !important;
}
/* Amber border wrapper — applied directly via data-err attr */
[data-err="true"] input,
[data-err="true"] textarea {
    border-color: #ffc400 !important;
    box-shadow: 0 0 10px rgba(255,196,0,0.4) !important;
}
/* Comment / advance-comment indent (100px) */
.cmt-indent { margin-left: 100px !important; }
</style>
"""

# ── PREVIEW MODE ──────────────────────────────────────────────────────────────
PREVIEW_COUPON = {
    "coupon_id": "CPN-20260317-042",
    "jira_ticket": "MTE-7",
    "part_number": "SUB-CPN-0042",
    "description": "Hull coupon — weld test specimen for rib-to-shell joint qualification",
    "priority": "High",
    "requesting_stakeholder": "Alex Torres",
    "nx_model_ref": "NX-Model-HullCPN-v3.2",
    "tc_engineering_item": "TC-10045-B",
    "notes": "Critical path item. Material: HY-100 steel. Weld per WPS-042-A.",
    "current_phase": 1,
    "jira_status": "New Request",
    "created_at": "2026-03-17 08:00:00",
    "created_by": "stakeholder",
    "p1_submitted_at": "2026-03-17 08:00:00",
    "p1_submitted_by": "stakeholder",
    "p2_completed_at": None,
    "p3_tc_ebom": None,
    "p3_completed_at": None,
    "p3_completed_by": None,
}


def is_preview():
    return st.session_state.get("mode") == "preview"


def get_coupon_or_preview():
    if is_preview():
        return PREVIEW_COUPON
    return db.get_coupon(st.session_state.get("coupon_id") or "")


def preview_banner():
    st.markdown(
        '<div style="background:rgba(255,196,0,0.07);border:1px solid #ffc400;border-left:4px solid #ffc400;'
        'padding:10px 16px;border-radius:2px;margin:12px 0">'
        '<span style="color:#ffc400;font-size:0.88em;letter-spacing:0.08em">'
        '⚡ PREVIEW MODE — submits &amp; sign-offs disabled. Switch to <strong>Demo Mode</strong> to execute the live workflow.'
        '</span></div>',
        unsafe_allow_html=True,
    )


@st.dialog("◈ PHASE PREVIEW", width="large")
def phase_preview_dialog():
    phase_num = st.session_state.get("preview_dialog", 1)
    meta      = PHASE_META[phase_num]
    pv        = PREVIEW_COUPON

    # ── Bright dialog background + border ─────────────────────────────────────
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

    # ── Phase header ──────────────────────────────────────────────────────────
    st.markdown(
        f'<span style="background:rgba(0,212,255,0.12);border:1px solid #00d4ff;color:#00d4ff;'
        f'padding:3px 10px;font-size:0.82em;letter-spacing:0.1em">PHASE {phase_num}</span>'
        f'&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.08em">{meta["name"].upper()}</span>'
        f'<div style="color:#5aaccc;font-size:0.75em;margin-top:3px">ROLES: {meta["roles"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="background:rgba(255,196,0,0.10);border-left:3px solid #ffc400;'
        'padding:6px 12px;margin:8px 0;font-size:0.78em;color:#ffc400">'
        '⚡ PREVIEW MODE — actions disabled</div>',
        unsafe_allow_html=True,
    )

    # ── Compact work order card ───────────────────────────────────────────────
    st.markdown(
        f'<div style="background:#163248;border:1px solid #2a8ab0;border-left:3px solid #00d4ff;'
        f'padding:8px 12px;margin-bottom:12px;border-radius:2px;font-size:0.82em;'
        f'display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">'
        f'<div><span style="color:#5aaccc">WORK ORDER</span><br>'
        f'<span style="color:#00d4ff">{pv["coupon_id"]}</span></div>'
        f'<div><span style="color:#5aaccc">PART NO.</span><br>'
        f'<span style="color:#c0d8e0">{pv["part_number"]}</span></div>'
        f'<div><span style="color:#5aaccc">PRIORITY</span><br>'
        f'<span style="color:#ff5555">{pv["priority"]}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _flag(key):
        return st.session_state.get(f"pd_done_{phase_num}_{key}", False)

    def _set_flag(key):
        st.session_state[f"pd_done_{phase_num}_{key}"] = True

    def _success_card(title, sub=""):
        st.markdown(
            f'<div style="padding:18px;border:1px solid #00d4ff;background:#0e2a40;'
            f'border-radius:2px;text-align:center;margin:12px 0">'
            f'<div style="font-size:1.1em;color:#00d4ff;letter-spacing:0.15em">{title}</div>'
            + (f'<div style="color:#5aaccc;font-size:0.83em;margin-top:8px">{sub}</div>' if sub else '')
            + '</div>',
            unsafe_allow_html=True,
        )

    def _signoff_row(r_label, btn_label, flag_key, border="#00d4ff", sub_text="", cmt_placeholder="Add context for downstream phases…"):
        if _flag(flag_key):
            st.markdown(
                f'<div style="background:rgba(0,160,80,0.08);border-left:3px solid #00b464;'
                f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                f'<span style="color:#00cc77">✓ {r_label}</span>'
                f'<span style="color:#2a8060;font-size:0.78em;margin-left:12px">Signed · preview</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="background:rgba(0,212,255,0.04);border-left:3px solid {border};'
                f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                f'<span style="color:#00d4ff">⟶ Sign-off required: {r_label}</span>'
                + (f'<span style="color:#5aaccc;font-size:0.78em;margin-left:10px">({sub_text})</span>' if sub_text else '')
                + '</div>',
                unsafe_allow_html=True,
            )
            _, _cmt_col = st.columns([1, 20])
            with _cmt_col:
                st.text_area("Comment (optional)", key=f"pd_cmt_{phase_num}_{flag_key}", height=60, placeholder=cmt_placeholder, label_visibility="visible")
                _btn_clicked = st.button(btn_label, key=f"pd_btn_{phase_num}_{flag_key}")
            if _btn_clicked:
                _set_flag(flag_key)
                st.rerun()
    render_phase_history(pv["coupon_id"], pv)
    render_comments(pv["coupon_id"])
    # ── Phase-specific form content ───────────────────────────────────────────
    if phase_num == 1:
        st.markdown("**REQUEST DETAILS**")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("PART NUMBER *",           value=pv["part_number"],          key="pd_pn")
            st.text_input("NX MODEL REFERENCE *",    value=pv["nx_model_ref"],         key="pd_nx")
            st.text_input("TC ENGINEERING ITEM # *", value=pv["tc_engineering_item"],  key="pd_tc")
        with c2:
            st.text_area("DESCRIPTION *",            value=pv["description"],          key="pd_desc", height=80)
            st.text_input("PRIORITY",                value=pv["priority"],             key="pd_pri")
            st.text_input("REQUESTING STAKEHOLDER *",value=pv["requesting_stakeholder"],key="pd_stk")
        st.text_area("NOTES",                        value=pv["notes"],                key="pd_nts", height=60)
        if _flag("submit"):
            _success_card(
                f"✓ REQUEST SUBMITTED — {pv['coupon_id']}",
                "Advancing to Phase 2 — multi-role alignment sign-off required.",
            )
        else:
            if st.button("⟶ SUBMIT REQUEST", key="pd_p1_submit"):
                _set_flag("submit")
                st.rerun()

    elif phase_num == 2:
        st.markdown("**ALIGNMENT SIGN-OFF** — 3 roles must confirm")
        roles_p2 = [
            ("Design Engineer (DE)",        "DE",           "#00d4ff", "e.g. NX model reviewed, design intent confirmed, no conflicts with fab requirements…"),
            ("Manufacturing Engineer (ME)", "ME",           "#00d4ff", "e.g. Fabrication approach feasible, tooling and process reviewed, no open issues…"),
            ("Weld Engineer",               "WeldEngineer", "#00d4ff", "e.g. Weld joint design acceptable, process applicability confirmed, no concerns…"),
        ]
        for r_label, r_key, border, cmt_ph in roles_p2:
            _signoff_row(r_label, f"✓ CONFIRM ALIGNMENT — {r_label.upper()}", r_key, border, cmt_placeholder=cmt_ph)
        signed = sum(_flag(k) for _, k, _, _ in roles_p2)
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(signed / 3, text=f"SIGN-OFF PROGRESS: {signed} / 3")
        if _flag("advance"):
            _success_card("✓ ALL ROLES ALIGNED — PHASE 2 COMPLETE", "Advancing to Phase 3 · DE must proceed.")
        elif signed == 3:
            _, _adv_col = st.columns([1, 20])
            with _adv_col:
                st.text_area("Advance Comment (optional)", key="pd_adv_cmt_2", height=60,
                             placeholder="e.g. All roles aligned, proceeding to NX design + TC EBOM creation…", label_visibility="visible")
                _adv_clicked_2 = st.button("⟶ ADVANCE TO PHASE 3", key="pd_p2_adv")
            if _adv_clicked_2:
                _set_flag("advance")
                st.rerun()

    elif phase_num == 3:
        st.markdown("**NX DESIGN CONFIRMATION**")
        st.checkbox("NX model design is complete and checked in to Teamcenter", value=True, key="pd_nx_chk")
        st.markdown("**TC ITEM REFERENCE**")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("TC ITEM REFERENCE # *", value=pv["tc_engineering_item"], key="pd_ebom")
        with c2:
            st.text_area("COMPLETION NOTES", value="Design finalized per drawing rev B.", key="pd_p3n", height=68)
        if _flag("advance"):
            _success_card("✓ NX DESIGN COMPLETE — ADVANCING", "Phase 4 / 5 / 6 now active in parallel.")
        else:
            if st.button("⟶ ADVANCE TO PHASE 4 / 5 / 6", key="pd_p3_adv"):
                _set_flag("advance")
                st.rerun()

    elif phase_num == 4:
        st.markdown("**PROCUREMENT DETAILS**")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("PR NUMBER *",                value="PR-2026-0042",          key="pd_pr")
            st.text_input("VENDOR / SUPPLIER *",        value="Titanium Forge Inc.",   key="pd_vnd")
            st.date_input("ESTIMATED DELIVERY DATE *",                                  key="pd_del")
        with c2:
            st.text_input("RFQ REFERENCE",              value="RFQ-2026-0088",         key="pd_rfq")
            st.text_input("PO NUMBER",                  value="PO-2026-0088",          key="pd_po")
            st.text_area("PROCUREMENT NOTES",           value="12-week lead time.",     key="pd_p4n", height=68)
        if _flag("submit"):
            _success_card("✓ PROCUREMENT DETAILS SAVED", "Awaiting Phase 7 material receiving.")
        else:
            if st.button("✓ SUBMIT PROCUREMENT", key="pd_p4_submit"):
                _set_flag("submit")
                st.rerun()

    elif phase_num == 5:
        st.markdown("**WORK INSTRUCTIONS SIGN-OFF** — 3 roles must confirm")
        roles_p5 = [
            ("Manufacturing Engineer (ME)", "ME",           "WI Doc Ref",          "e.g. WI-2024-042 / BOP-Rev-B",   "e.g. Work instructions cover all fab steps, bill of process complete and approved…"),
            ("Weld Engineer",               "WeldEngineer", "WPS / Weld Proc Ref", "e.g. WPS-AWS-D1.1-Rev2",         "e.g. WPS reviewed and applicable to joint design, preheat and filler requirements confirmed…"),
            ("Quality Engineer (QE)",       "QE",           "Inspection Plan Ref", "e.g. QIP-CPN-0042-Rev1",         "e.g. Inspection checkpoints defined for all critical dims, acceptance criteria documented…"),
        ]
        for r_label, r_key, ref_label, ref_ph, cmt_ph in roles_p5:
            _signoff_row(r_label, f"✓ CONFIRM — {r_label[:35]}…", r_key, sub_text=f"{ref_label}: {ref_ph}", cmt_placeholder=cmt_ph)
        signed = sum(_flag(k) for _, k, _, _, _ in roles_p5)
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(signed / 3, text=f"SIGN-OFF PROGRESS: {signed} / 3")
        if _flag("advance"):
            _success_card("✓ WORK INSTRUCTIONS APPROVED — PHASE 5 COMPLETE", "Advancing to Phase 6.")
        elif signed == 3:
            _, _adv_col = st.columns([1, 20])
            with _adv_col:
                st.text_area("Advance Comment (optional)", key="pd_adv_cmt_5", height=60,
                             placeholder="e.g. Work package complete, advancing to resource allocation and scheduling…", label_visibility="visible")
                _adv_clicked_5 = st.button("⟶ ADVANCE TO PHASE 6", key="pd_p5_adv")
            if _adv_clicked_5:
                _set_flag("advance")
                st.rerun()

    elif phase_num == 6:
        st.markdown("**WORK ALLOCATION**")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("ASSIGNED TECHNICIAN *",      value="Chris Martinez",        key="pd_tech")
            st.date_input("SCHEDULED START DATE *",                                     key="pd_start")
            st.date_input("SCHEDULED END DATE *",                                       key="pd_end")
        with c2:
            st.text_input("SHIFT / CREW",               value="Day Shift A",           key="pd_shft")
            st.text_input("WORK PACKAGE REFERENCE",     value="WP-2026-0042",          key="pd_wp")
            st.text_area("RESOURCING NOTES",            value="Aligned with production schedule.", key="pd_p6n", height=68)
        if _flag("submit"):
            _success_card("✓ WORK ALLOCATION SAVED", "Work package issued to technician.")
        else:
            if st.button("✓ SUBMIT WORK ALLOCATION", key="pd_p6_submit"):
                _set_flag("submit")
                st.rerun()

    elif phase_num == 7:
        st.markdown("**MATERIAL RECEIVING SIGN-OFF** — 3 roles must confirm")
        roles_p7 = [
            ("Supply Chain",    "SC", "PO / Packing Slip Ref",  "e.g. PO-2024-1187 / PS-00342", "e.g. All line items received, quantities match PO, certs and documentation on file…"),
            ("Quality Engineer","QE", "Inspection Record Ref",  "e.g. IIR-2024-0089",            "e.g. Incoming inspection passed, material certs verified, no non-conformances noted…"),
            ("Warehouse / MMO", "WH", "Storage Location / Bin", "e.g. Rack B-12 / Bin 04",       "e.g. Material stowed in designated location, tagged, barcoded and traceable in MMO system…"),
        ]
        for r_label, r_key, ref_label, ref_ph, cmt_ph in roles_p7:
            _signoff_row(r_label, f"✓ CONFIRM — {r_label}", r_key, sub_text=f"{ref_label}: {ref_ph}", cmt_placeholder=cmt_ph)
        signed = sum(_flag(k) for _, k, _, _, _ in roles_p7)
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(signed / 3, text=f"SIGN-OFF PROGRESS: {signed} / 3")
        if _flag("advance"):
            _success_card("✓ MATERIAL RECEIVED — PHASE 7 COMPLETE", "Advancing to Phase 8 — Work Execution.")
        elif signed == 3:
            _, _adv_col = st.columns([1, 20])
            with _adv_col:
                st.text_area("Advance Comment (optional)", key="pd_adv_cmt_7", height=60,
                             placeholder="e.g. All materials confirmed on hand and inspected, cleared for work execution…", label_visibility="visible")
                _adv_clicked_7 = st.button("⟶ ADVANCE TO PHASE 8 — WORK EXECUTION", key="pd_p7_adv")
            if _adv_clicked_7:
                _set_flag("advance")
                st.rerun()

    elif phase_num == 8:
        st.markdown("**EXECUTION SIGN-OFF** — MECHANIC convergence node")
        roles_p8 = [
            ("Mechanic (Mfg Tech)",    "Mech", "Work Completion Notes / Redline Ref", "#00f5ff", "e.g. All steps completed per WI-2024-042, redlines attached as-built Rev A…",      "e.g. Fabrication complete, all work order steps executed, redlines submitted for DE review…"),
            ("Manufacturing Engineer", "ME",   "ME Sign-Off Notes",                   "#00d4ff", "e.g. As-built reviewed, dimensional check passed, redlines accepted…",              "e.g. Fabrication meets drawing requirements, redlines reviewed and accepted, no open actions…"),
            ("Quality Engineer (QE)", "QE",   "Inspection Record / QC Ref",           "#00d4ff", "e.g. QCR-2024-0112 / Final inspection report attached…",                           "e.g. Final inspection complete, all dimensions within tolerance, quality record filed…"),
        ]
        for r_label, r_key, ref_label, border, ref_ph, cmt_ph in roles_p8:
            _signoff_row(r_label, f"✓ CONFIRM — {r_label[:40]}…", r_key, border=border, sub_text=f"{ref_label}: {ref_ph}", cmt_placeholder=cmt_ph)
        signed = sum(_flag(k) for _, k, _, _, _, _ in roles_p8)
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(signed / 3, text=f"EXECUTION SIGN-OFF PROGRESS: {signed} / 3")
        if _flag("advance"):
            _success_card("✓ EXECUTION COMPLETE — PHASE 8 COMPLETE", "Advancing to Phase 9 — NCR Assessment.")
        elif signed == 3:
            _, _adv_col = st.columns([1, 20])
            with _adv_col:
                st.text_area("Advance Comment (optional)", key="pd_adv_cmt_8", height=60,
                             placeholder="e.g. Execution confirmed by all roles, advancing to NCR review and close-out…", label_visibility="visible")
                _adv_clicked_8 = st.button("⟶ ADVANCE TO PHASE 9 — NON-CONFORMANCE (NCR)", key="pd_p8_adv")
            if _adv_clicked_8:
                _set_flag("advance")
                st.rerun()

    elif phase_num == 9:
        st.markdown("**NCR ASSESSMENT** — QE initiates")
        ncr = st.checkbox("Non-conformance identified — NCR required", value=False, key="pd_ncr")
        if not ncr:
            st.markdown(
                '<div style="border-left:3px solid #00b464;padding:8px 12px;background:rgba(0,160,80,0.08);'
                'margin:6px 0;font-size:0.85em;color:#50c090">No non-conformance — cleared for closure</div>',
                unsafe_allow_html=True,
            )
        if _flag("qe_submit"):
            _success_card("✓ NCR ASSESSMENT SUBMITTED", "Disposition sign-off required.")
        else:
            if st.button("✓ SUBMIT NCR ASSESSMENT", key="pd_p9_qe"):
                _set_flag("qe_submit")
                st.rerun()
        st.markdown("**DISPOSITION CONFIRMATION**")
        roles_p9 = [("Manufacturing Engineer (ME)", "ME"), ("Mechanic", "Mech")]
        for r_label, r_key in roles_p9:
            _signoff_row(r_label, f"✓ CONFIRM DISPOSITION — {r_label.upper()}", r_key)
        signed = sum(_flag(k) for _, k in roles_p9)
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(signed / 2, text=f"DISPOSITION SIGN-OFF: {signed} / 2")
        if _flag("close"):
            _success_card("✓ WORK ORDER CLOSED", "All phases complete — coupon fab cycle finished.")
        elif signed == 2:
            if st.button("✓ CLOSE WORK ORDER", key="pd_p9_close"):
                _set_flag("close")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✕  CLOSE PREVIEW", use_container_width=True, key="pd_close"):
        # clear all preview flags for this phase
        for k in [k for k in st.session_state if k.startswith(f"pd_done_{phase_num}_")]:
            del st.session_state[k]
        del st.session_state["preview_dialog"]
        st.rerun()


def page_mode_select():
    st.markdown(CSS, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;margin-bottom:36px">'
            '<div style="font-size:2.4em;color:#00d4ff;letter-spacing:0.35em">◈ WORK INTAKE</div>'
            '<div style="color:#00d4ff;font-size:0.8em;letter-spacing:0.2em;margin-top:4px">'
            'MTE MANUFACTURING EXECUTION &nbsp;//&nbsp; V1</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="color:#2a8eab;font-size:0.75em;letter-spacing:0.15em;text-align:center;margin-bottom:28px">'
            'SELECT OPERATING MODE</div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                '<div style="background:#0a1520;border:1px solid #1e4a62;border-top:3px solid #00d4ff;'
                'padding:20px 16px;border-radius:2px;text-align:center;margin-bottom:12px;min-height:148px">'
                '<div style="color:#00d4ff;font-size:1.05em;letter-spacing:0.15em">⟡ PREVIEW</div>'
                '<div style="color:#2a8eab;font-size:0.75em;margin-top:10px;line-height:1.9">'
                'All 9 phases visible<br>All nodes clickable<br>Forms shown instantly<br>'
                'No login · No role gates<br><span style="color:#2a8eab">Submits disabled</span>'
                '</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("⟶  ENTER PREVIEW", key="btn_preview", use_container_width=True):
                st.session_state.mode = "preview"
                st.session_state.auth = True
                st.session_state.user = {
                    "username": "preview",
                    "role": "Preview",
                    "display_name": "Preview Mode",
                }
                st.session_state.page = "dashboard"
                st.rerun()
        with c2:
            st.markdown(
                '<div style="background:#0a1520;border:1px solid #1e4a62;border-top:3px solid #ffc400;'
                'padding:20px 16px;border-radius:2px;text-align:center;margin-bottom:12px;min-height:148px">'
                '<div style="color:#ffc400;font-size:1.05em;letter-spacing:0.15em">⟡ DEMO</div>'
                '<div style="color:#2a8eab;font-size:0.75em;margin-top:10px;line-height:1.9">'
                'Enforced workflow<br>Login · Role-based access<br>Submit &amp; sign-off enabled<br>'
                'Live Jira triggers<br><span style="color:#2a8eab">Full execution</span>'
                '</div></div>',
                unsafe_allow_html=True,
            )
            if st.button("⟶  ENTER DEMO", key="btn_demo", use_container_width=True):
                st.session_state.mode = "demo"
                st.session_state.page = "login"
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        _docs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "presentation.html")
        try:
            with open(_docs_path, "rb") as _f:
                _docs_b64 = base64.b64encode(_f.read()).decode()
            st.components.v1.html(
                f"""
                <div style="text-align:center">
                  <a id="docs-link"
                     style="cursor:pointer;color:#00d4ff;font-size:0.82em;letter-spacing:0.1em;
                            text-decoration:none;border:1px solid #1e4a62;padding:8px 20px;
                            border-radius:2px;background:rgba(0,212,255,0.06);display:inline-block">
                    DOCUMENTATION
                  </a>
                </div>
                <script>
                  document.getElementById('docs-link').addEventListener('click', function() {{
                    var b64 = "{_docs_b64}";
                    var bin = atob(b64);
                    var bytes = new Uint8Array(bin.length);
                    for (var i = 0; i < bin.length; i++) {{ bytes[i] = bin.charCodeAt(i); }}
                    var blob = new Blob([bytes], {{type:'text/html;charset=utf-8'}});
                    var url = URL.createObjectURL(blob);
                    window.open(url, '_blank');
                  }});
                </script>
                """,
                height=50,
            )
        except FileNotFoundError:
            pass


# ── HELPERS ───────────────────────────────────────────────────────────────────
def go(page, coupon_id=None, nav_phase=None):
    st.session_state.page = page
    st.session_state.errs = {}
    if coupon_id is not None:
        st.session_state.coupon_id = coupon_id
    if nav_phase is not None:
        st.session_state.nav_phase = nav_phase
    st.rerun()


def role():
    return st.session_state.user["role"] if st.session_state.user else ""


def uname():
    return st.session_state.user["username"] if st.session_state.user else ""


def udisp():
    return st.session_state.user["display_name"] if st.session_state.user else ""


def field_lbl(label, key, required=True):
    has_err = key in st.session_state.errs
    cls = "err-label" if has_err else ""
    star = ' <span style="color:#ffc400">*</span>' if required else ""
    return (
        f'<div class="{cls}" style="font-size:0.8em;letter-spacing:0.1em;'
        f'color:{"#ffc400" if has_err else "#3a8898"};margin-bottom:2px">'
        f"{label}{star}</div>"
    )


def err_msg(key, text="Required field"):
    if key in st.session_state.errs:
        st.markdown(f'<span class="err-msg">▲ {text}</span>', unsafe_allow_html=True)


def jira_badge(ticket, status):
    url = jira_api.issue_url(ticket) if ticket else "#"
    return (
        f'<a href="{url}" target="_blank" class="jira-badge" '
        f'style="background:#0066ee;color:#fff;padding:2px 9px 2px 7px;'
        f'border-radius:3px;font-size:0.82em;margin-right:8px;'
        f'text-decoration:underline;text-underline-offset:2px;'
        f'border:1px solid rgba(255,255,255,0.35)">{ticket} ↗</a>'
        f'<span style="color:#00d4ff;font-size:0.82em">{status}</span>'
    )


def priority_color(p):
    return {"High": "#ff5555", "Medium": "#ffc400", "Low": "#00e888"}.get(p, "#aaa")


def _build_jira_comment(coupon_id: str, phase: int, summary: str, adv_comment: str = "") -> str:
    """Build a rich Jira comment with sign-off details and user comments for a phase."""
    lines = [summary, ""]

    # Sign-off details (for multi-role phases)
    sigs = db.get_signoffs(coupon_id, phase)
    if sigs:
        lines.append("Sign-offs:")
        for s in sigs:
            entry = f"  - {s['display_name']} ({s['role']})"
            if s.get("notes"):
                entry += f" | {s['notes']}"
            lines.append(entry)
        lines.append("")

    # User comments from this phase
    all_comments = db.get_phase_comments(coupon_id)
    phase_comments = [c for c in all_comments if c["phase"] == phase and c.get("comment")]
    if phase_comments:
        lines.append("Comments:")
        for c in phase_comments:
            lines.append(f"  - [{c['action']}] {c['display_name']}: {c['comment']}")
        lines.append("")

    # Advance comment
    if adv_comment and adv_comment.strip():
        lines.append(f"Advance note: {adv_comment.strip()}")

    return "\n".join(lines)


# ── DEMO MODE: PHASE ACTION MODAL ─────────────────────────────────────────────
@st.dialog("◈ PHASE ACTION", width="large")
def phase_action_dialog():
    """Demo-mode inline phase action — replaces full-page navigation from dashboard."""
    phase     = st.session_state.get("modal_phase")
    coupon_id = st.session_state.get("modal_coupon_id")
    coupon    = db.get_coupon(coupon_id) if coupon_id else None

    # ── Styling (matches phase_preview_dialog) ────────────────────────────────
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

    meta = PHASE_META[phase]
    st.markdown(
        f'<span style="background:rgba(0,212,255,0.12);border:1px solid #00d4ff;color:#00d4ff;'
        f'padding:3px 10px;font-size:0.82em;letter-spacing:0.1em">PHASE {phase}</span>'
        f'&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.08em">{meta["name"].upper()}</span>'
        f'<div style="color:#5aaccc;font-size:0.75em;margin-top:3px">ROLES: {meta["roles"]}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        viz.workflow_svg(current_phase=phase, clickable=False),
        unsafe_allow_html=True,
    )

    if coupon:
        st.markdown(
            f'<div style="background:#163248;border:1px solid #2a8ab0;border-left:3px solid #00d4ff;'
            f'padding:8px 12px;margin:10px 0;border-radius:2px;font-size:0.82em;'
            f'display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">'
            f'<div><span style="color:#5aaccc">WORK ORDER</span><br>'
            f'<span style="color:#00d4ff">{coupon["coupon_id"]}</span></div>'
            f'<div><span style="color:#5aaccc">PART NO.</span><br>'
            f'<span style="color:#c0d8e0">{coupon["part_number"]}</span></div>'
            f'<div><span style="color:#5aaccc">PRIORITY</span><br>'
            f'<span style="color:{priority_color(coupon["priority"])}">{coupon["priority"]}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        render_phase_nav(coupon, phase)
        render_phase_history(coupon_id, coupon)
        render_comments(coupon_id)

    def _close():
        st.session_state.pop("modal_phase", None)
        st.session_state.pop("modal_coupon_id", None)
        st.session_state.pop("modal_errs", None)
        for _k in ["mp1_submitted", "mp1_new_cid", "mp1_jira", "mp1_priority", "mp1_part"]:
            st.session_state.pop(_k, None)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1 — New Request
    # ══════════════════════════════════════════════════════════════════════════
    if phase == 1:
        if st.session_state.get("mp1_submitted"):
            # ── Success card ──
            new_cid    = st.session_state.get("mp1_new_cid", "")
            jira_ticket = st.session_state.get("mp1_jira", "")
            priority   = st.session_state.get("mp1_priority", "")
            part_number = st.session_state.get("mp1_part", "")
            jira_note = (
                f'<div style="margin-top:6px">{jira_badge(jira_ticket, "To Do · In Design")}</div>'
                if jira_ticket else
                '<div style="color:#1a5060;font-size:0.8em;margin-top:4px">No Jira ticket — check integration settings.</div>'
            )
            st.markdown(
                f'<div style="padding:18px;border:1px solid #00d4ff;background:#0e2a40;'
                f'border-radius:2px;text-align:center;margin:12px 0">'
                f'<div style="font-size:1.1em;color:#00d4ff;letter-spacing:0.15em">✓ REQUEST SUBMITTED — {new_cid}</div>'
                f'<div style="color:#c0d8e0;margin-top:6px">Part: {part_number} &nbsp;·&nbsp; {priority}</div>'
                f'{jira_note}'
                f'<div style="color:#5aaccc;font-size:0.83em;margin-top:8px">Advancing to Phase 2 — alignment sign-off required.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✕ CLOSE", key="mp1_close_btn", use_container_width=True):
                _close()
                st.rerun()
        else:
            # ── Input form ──
            errs = st.session_state.get("modal_errs", {})
            if errs:
                n = len(errs)
                st.markdown(
                    f'<div style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;'
                    f'border-left:4px solid #ffb300;padding:10px 16px;border-radius:2px;margin-bottom:12px">'
                    f'<span style="color:#ffb300;font-size:0.88em;">'
                    f'⚠ &nbsp;{n} REQUIRED FIELD{"S" if n!=1 else ""} MISSING</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with st.form("modal_phase1_form"):
                st.markdown("**REQUEST DETAILS**")
                st.markdown("<hr>", unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f'<div style="color:{"#ffc400" if "part_number" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">PART NUMBER <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                    part_number = st.text_input("pn", key="mp1_pn", placeholder="e.g. SUB-CPN-0042", label_visibility="collapsed")
                    if "part_number" in errs:
                        st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                    st.markdown(f'<div style="color:{"#ffc400" if "nx_model_ref" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">NX MODEL REFERENCE <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                    nx_model_ref = st.text_input("nx", key="mp1_nx", placeholder="e.g. NX-Model-v3.2", label_visibility="collapsed")
                    if "nx_model_ref" in errs:
                        st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                    st.markdown(f'<div style="color:{"#ffc400" if "tc_engineering_item" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">TC ENGINEERING ITEM # <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                    tc_item = st.text_input("tc", key="mp1_tc", placeholder="e.g. TC-10045", label_visibility="collapsed")
                    if "tc_engineering_item" in errs:
                        st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                with col2:
                    st.markdown(f'<div style="color:{"#ffc400" if "description" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">DESCRIPTION <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                    description = st.text_area("desc", key="mp1_desc", placeholder="Describe the coupon fabrication requirement…", height=80, label_visibility="collapsed")
                    if "description" in errs:
                        st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                    st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">PRIORITY</div>', unsafe_allow_html=True)
                    priority = st.selectbox("pri", ["High", "Medium", "Low"], index=1, key="mp1_pri", label_visibility="collapsed")
                    st.markdown(f'<div style="color:{"#ffc400" if "requesting_stakeholder" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">REQUESTING STAKEHOLDER <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                    stakeholder = st.text_input("stk", key="mp1_stk", placeholder="Name / Organization", value=udisp(), label_visibility="collapsed")
                    if "requesting_stakeholder" in errs:
                        st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                st.markdown("<hr>", unsafe_allow_html=True)
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">NOTES / SPECIAL REQUIREMENTS</div>', unsafe_allow_html=True)
                notes = st.text_area("nts", key="mp1_notes", placeholder="Additional context, constraints, or requirements…", height=60, label_visibility="collapsed")
                st.markdown("<br>", unsafe_allow_html=True)
                cb, _, cs = st.columns([1, 3, 1])
                with cb:
                    cancel_p1 = st.form_submit_button("✕ CANCEL", use_container_width=True)
                with cs:
                    submit_p1 = st.form_submit_button("⟶  SUBMIT REQUEST", use_container_width=True)
            if cancel_p1:
                _close()
                st.rerun()
            if submit_p1:
                required = {
                    "part_number": part_number,
                    "description": description,
                    "nx_model_ref": nx_model_ref,
                    "tc_engineering_item": tc_item,
                    "requesting_stakeholder": stakeholder,
                }
                missing = {k for k, v in required.items() if not v.strip()}
                if missing:
                    st.session_state["modal_errs"] = {k: True for k in missing}
                    st.rerun()
                else:
                    data = {
                        "part_number": part_number.strip(), "description": description.strip(),
                        "priority": priority, "requesting_stakeholder": stakeholder.strip(),
                        "nx_model_ref": nx_model_ref.strip(), "tc_engineering_item": tc_item.strip(),
                        "notes": notes.strip(),
                    }
                    new_cid = db.generate_coupon_id()
                    with st.spinner("Creating Jira ticket…"):
                        jira_ticket = jira_api.create_issue(dict(data, coupon_id=new_cid)) or ""
                    db.create_coupon(data, uname(), coupon_id=new_cid, jira_ticket=jira_ticket)
                    st.session_state.pop("modal_errs", None)
                    st.session_state["mp1_submitted"] = True
                    st.session_state["mp1_new_cid"]   = new_cid
                    st.session_state["mp1_jira"]      = jira_ticket
                    st.session_state["mp1_priority"]  = priority
                    st.session_state["mp1_part"]      = data["part_number"]
                    st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # PHASES 2, 5, 7, 8 — Multi-role sign-off
    # ══════════════════════════════════════════════════════════════════════════
    elif phase in (2, 5, 7, 8):
        # roles tuple: (r_key, r_label, ref_label, textarea_ref, btn_label, ref_placeholder, cmt_placeholder)
        _SIGNOFF_CFG = {
            2: {
                "title": "ALIGNMENT SIGN-OFF",
                "roles": [
                    ("DE",            "Design Engineer",       None, False, "✓ CONFIRM ALIGNMENT — DESIGN ENGINEER",
                     None, "e.g. NX model reviewed, design intent confirmed, no conflicts with fab requirements…"),
                    ("ME",            "Manufacturing Engineer", None, False, "✓ CONFIRM ALIGNMENT — MANUFACTURING ENGINEER",
                     None, "e.g. Fabrication approach feasible, tooling and process reviewed, no open issues…"),
                    ("Weld Engineer", "Weld Engineer",          None, False, "✓ CONFIRM ALIGNMENT — WELD ENGINEER",
                     None, "e.g. Weld joint design acceptable, process applicability confirmed, no concerns…"),
                ],
                "complete_fn":   db.phase2_complete,
                "complete_msg":  "✓ ALL ROLES ALIGNED — PHASE 2 COMPLETE",
                "advance_to":    3,
                "advance_roles": {"DE"},
                "advance_btn":   "⟶ ADVANCE TO PHASE 3",
                "adv_placeholder": "e.g. All roles aligned, proceeding to NX design + TC EBOM creation…",
            },
            5: {
                "title": "WORK INSTRUCTIONS SIGN-OFF",
                "roles": [
                    ("ME",            "Manufacturing Engineer", "WI Doc Ref",          False, "✓ CONFIRM — Work instructions and bill of process…",
                     "e.g. WI-2024-042 / BOP-Rev-B", "e.g. Work instructions cover all fab steps, bill of process complete and approved…"),
                    ("Weld Engineer", "Weld Engineer",          "WPS / Weld Proc Ref", False, "✓ CONFIRM — Welding process document defined…",
                     "e.g. WPS-AWS-D1.1-Rev2", "e.g. WPS reviewed and applicable to joint design, preheat and filler requirements confirmed…"),
                    ("QE",            "Quality Engineer",       "Inspection Plan Ref", False, "✓ CONFIRM — Inspection plan and quality checklist…",
                     "e.g. QIP-CPN-0042-Rev1", "e.g. Inspection checkpoints defined for all critical dims, acceptance criteria documented…"),
                ],
                "complete_fn":   db.phase5_complete,
                "complete_msg":  "✓ ALL ROLES CONFIRMED — PHASE 5 COMPLETE",
                "advance_to":    8,
                "advance_roles": {"ME"},
                "advance_btn":   "⟶ ADVANCE TO PHASE 8 — WORK EXECUTION",
                "adv_placeholder": "e.g. Work package complete, advancing to work execution (awaiting phases 6 and 7)…",
            },
            7: {
                "title": "MATERIAL CONFIRMATION",
                "roles": [
                    ("Supply Chain",  "Supply Chain",    "PO / Packing Slip Ref",  False, "✓ CONFIRM RECEIPT — SUPPLY CHAIN",
                     "e.g. PO-2024-1187 / PS-00342", "e.g. All materials received per PO, quantities verified…"),
                    ("QE",            "Quality Engineer","Inspection Record Ref",   False, "✓ CONFIRM INSPECTION — QUALITY ENGINEER",
                     "e.g. IIR-2024-0089", "e.g. Incoming inspection complete, no non-conformances noted…"),
                    ("Warehouse/MMO", "Warehouse / MMO", "Storage Location / Bin",  False, "✓ CONFIRM STOWAGE — WAREHOUSE / MMO",
                     "e.g. Rack B-12 / Bin 04", "e.g. Material stowed and tagged in MMO system…"),
                ],
                "complete_fn":   db.phase7_complete,
                "complete_msg":  "✓ ALL CONFIRMED — MATERIALS READY FOR EXECUTION",
                "advance_to":    8,
                "advance_roles": {"Supply Chain"},
                "advance_btn":   "⟶ CONFIRM MATERIALS READY — ADVANCE TO PHASE 8",
                "adv_placeholder": "e.g. All materials confirmed on hand and inspected, cleared for work execution…",
            },
            8: {
                "title": "EXECUTION CONFIRMATION",
                "roles": [
                    ("Mechanic", "Mechanic (Mfg Tech)",    "Work Completion Notes / Redline Ref", True,  "⚙ CONFIRM EXECUTION COMPLETE — MECHANIC",
                     "e.g. All steps completed per WI-2024-042, redlines attached as-built Rev A…",
                     "e.g. Fabrication complete, all work order steps executed, redlines submitted for DE review…"),
                    ("ME",       "Manufacturing Engineer", "ME Review Notes",                     True,  "✓ CONFIRM — MANUFACTURING ENGINEER",
                     "e.g. As-built reviewed, dimensional check passed, redlines accepted…",
                     "e.g. Fabrication meets drawing requirements, redlines reviewed and accepted, no open actions…"),
                    ("QE",       "Quality Engineer",       "Inspection Record / QC Ref",          True,  "✓ CONFIRM — QUALITY ENGINEER",
                     "e.g. QCR-2024-0112 / Final inspection report attached…",
                     "e.g. Final inspection complete, all dimensions within tolerance, quality record filed…"),
                ],
                "complete_fn":   db.phase8_complete,
                "complete_msg":  "⚙ EXECUTION CONFIRMED — ALL ROLES COMPLETE",
                "advance_to":    9,
                "advance_roles": {"Mechanic", "ME"},
                "advance_btn":   "⟶ ADVANCE TO PHASE 9 — NCR / CLOSE-OUT",
                "adv_placeholder": "e.g. Execution confirmed by all roles, advancing to NCR review and close-out…",
            },
        }[phase]

        signoffs     = db.get_signoffs(coupon_id, phase)
        signed_roles = {s["role"] for s in signoffs}
        current_role = role()

        st.markdown(f"**{_SIGNOFF_CFG['title']}**")

        for r_key, r_label, ref_label, textarea_ref, btn_label, ref_placeholder, cmt_placeholder in _SIGNOFF_CFG["roles"]:
            if r_key in signed_roles:
                rec = next(s for s in signoffs if s["role"] == r_key)
                is_mine = (r_key == current_role)
                if is_mine:
                    bg       = "rgba(0,220,100,0.14)"
                    border_c = "#00e87a"
                    lbl_c    = "#00ff99"
                    meta_c   = "#5adba0"
                    ref_c    = "#00f5ff"
                    tag      = "✓ YOU CONFIRMED"
                else:
                    bg       = "rgba(0,160,80,0.08)"
                    border_c = "#00b464"
                    lbl_c    = "#00cc77"
                    meta_c   = "#2a8060"
                    ref_c    = "#00aacc"
                    tag      = "✓"
                ref_html = (
                    f'<span style="color:{meta_c};font-size:0.78em;display:block;margin-top:2px">'
                    f'{ref_label}: <span style="color:{ref_c}">{rec["notes"] or "—"}</span></span>'
                ) if ref_label else ""
                st.markdown(
                    f'<div style="background:{bg};border-left:3px solid {border_c};'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                    f'<span style="color:{lbl_c};font-weight:bold">{tag} {r_label}</span>'
                    f'<span style="color:{meta_c};font-size:0.78em;margin-left:12px">'
                    f'{rec["display_name"]} · {rec["signed_at"][:16]}</span>'
                    f'{ref_html}</div>',
                    unsafe_allow_html=True,
                )
            elif current_role == r_key:
                border = "#00f5ff" if (phase == 8 and r_key == "Mechanic") else "#00d4ff"
                st.markdown(
                    f'<div style="background:rgba(0,212,255,0.06);border-left:3px solid {border};'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                    f'<span style="color:{border}">⟶ Your confirmation required: {r_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                ref_val = ""
                _, _cmt_col = st.columns([1, 20])
                with _cmt_col:
                    if ref_label:
                        if textarea_ref:
                            ref_val = st.text_area(ref_label, key=f"md_ref_{phase}_{r_key}", height=60, placeholder=ref_placeholder or "")
                        else:
                            ref_val = st.text_input(ref_label, key=f"md_ref_{phase}_{r_key}", placeholder=ref_placeholder or "")
                    cmt_val = st.text_area(
                        "Comment (optional)", key=f"md_cmt_{phase}_{r_key}",
                        height=60, placeholder=cmt_placeholder or "Add context for downstream phases…", label_visibility="visible",
                    )
                    _sign_clicked = st.button(btn_label, key=f"md_sign_{phase}_{r_key}")
                if _sign_clicked:
                    db.add_signoff(coupon_id, phase, r_key, uname(), udisp(), notes=ref_val)
                    db.add_phase_comment(coupon_id, phase, "signoff", uname(), udisp(), cmt_val)
                    st.rerun()
            else:
                role_keys = {e[0] for e in _SIGNOFF_CFG["roles"]}
                hint = "" if current_role in role_keys else " &nbsp;<span style='color:#1a3040;font-size:0.75em'>(role required)</span>"
                st.markdown(
                    f'<div style="background:rgba(255,196,0,0.05);border-left:3px solid #7a5800;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#c8960a">'
                    f"○ {r_label} — awaiting sign-off{hint}</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)
        signed_count = len(signed_roles & {e[0] for e in _SIGNOFF_CFG["roles"]})
        total = len(_SIGNOFF_CFG["roles"])
        st.progress(signed_count / total, text=f"SIGN-OFF PROGRESS: {signed_count} / {total}")

        if _SIGNOFF_CFG["complete_fn"](coupon_id):
            st.markdown(
                f'<div style="padding:14px;border:1px solid #00d4ff;background:#0e2a40;'
                f'text-align:center;margin-top:12px;border-radius:2px">'
                f'<div style="color:#00d4ff;letter-spacing:0.1em">{_SIGNOFF_CFG["complete_msg"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            _active_ph = json.loads(coupon.get("active_phases") or f'[{coupon["current_phase"]}]')
            if current_role in _SIGNOFF_CFG["advance_roles"] and phase in _active_ph:
                st.markdown("<br>", unsafe_allow_html=True)
                _, _adv_col = st.columns([1, 20])
                with _adv_col:
                    adv_cmt = st.text_area(
                        "Advance Comment (optional)", key=f"md_adv_{phase}",
                        height=60, placeholder=_SIGNOFF_CFG.get("adv_placeholder", f"Notes for Phase {_SIGNOFF_CFG['advance_to']}…"), label_visibility="visible",
                    )
                    _adv_clicked = st.button(_SIGNOFF_CFG["advance_btn"], key=f"md_advance_{phase}")
                if _adv_clicked:
                    db.add_phase_comment(coupon_id, phase, "advance", uname(), udisp(), adv_cmt)
                    db.phase_complete(coupon_id, phase, [_SIGNOFF_CFG["advance_to"]])
                    if coupon.get("jira_ticket"):
                        sigs = db.get_signoffs(coupon_id, phase)
                        names = ", ".join(s["display_name"] for s in sigs)
                        jira_comment = _build_jira_comment(
                            coupon_id, phase,
                            f"Phase {phase} COMPLETE — confirmed by: {names}. Advancing to Phase {_SIGNOFF_CFG['advance_to']}.",
                            adv_cmt,
                        )
                        with st.spinner("Updating Jira…"):
                            jira_api.advance_phase(
                                coupon["jira_ticket"],
                                new_phase=_SIGNOFF_CFG["advance_to"],
                                comment=jira_comment,
                            )
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<hr style="border-color:#1e5068">', unsafe_allow_html=True)
        if st.button("✕ CANCEL", key=f"md_cancel_{phase}", use_container_width=True):
            _close()
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3 — NX Design + TC EBOM
    # ══════════════════════════════════════════════════════════════════════════
    elif phase == 3:
        errs = st.session_state.get("modal_errs", {})
        if errs:
            missing_names = []
            if "tc_ebom" in errs:
                missing_names.append("TC item reference")
            if "nx_model" in errs:
                missing_names.append("NX model reference")
            st.markdown(
                f'<div style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;'
                f'border-left:4px solid #ffb300;padding:10px 16px;border-radius:2px;margin-bottom:12px">'
                f'<span style="color:#ffb300;font-size:0.88em;">⚠ &nbsp;REQUIRED: {" · ".join(missing_names)}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with st.form("modal_phase3_form"):
            st.markdown("**ENGINEERING DATA INPUT**")
            st.markdown("<hr>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f'<div style="color:{"#ffc400" if "nx_model" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">NX MODEL REFERENCE <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                nx_model = st.text_input("nxm", key="mp3_nx", placeholder="e.g. NX-CPN-10045-Rev-A", label_visibility="collapsed")
                if "nx_model" in errs:
                    st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                st.markdown(f'<div style="color:{"#ffc400" if "tc_ebom" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">TC ITEM REFERENCE # <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                tc_ebom = st.text_input("ebom", key="mp3_ebom", placeholder="e.g. TC-EBOM-10045-A", label_visibility="collapsed")
                if "tc_ebom" in errs:
                    st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
            with col2:
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">MATERIAL SPECIFICATION</div>', unsafe_allow_html=True)
                material_spec = st.text_input("mspec", key="mp3_matspec", placeholder="e.g. Ti-6Al-4V AMS 4928", label_visibility="collapsed")
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">DESIGN NOTES</div>', unsafe_allow_html=True)
                p3_notes = st.text_area("p3n", key="mp3_notes", placeholder="Design decisions, deviations, or references…", height=68, label_visibility="collapsed")
            st.markdown(
                '<div style="padding:9px 12px;background:#060e18;border:1px solid #0d3040;'
                'border-left:3px solid #0d6080;border-radius:2px;font-size:0.78em;color:#2a7090;margin:10px 0">'
                '⟶ On submit, unlocks in parallel: <span style="color:#00aacc">Phase 4 (Procurement) · Phase 5 (Instructions) · Phase 6 (Resourcing)</span></div>',
                unsafe_allow_html=True,
            )
            p3_comment = st.text_area("SUBMISSION COMMENT (OPTIONAL)", key="mp3_comment", placeholder="Notes for downstream phases…", height=50, label_visibility="visible")
            cb, _, cs = st.columns([1, 3, 1])
            with cb:
                cancel_p3 = st.form_submit_button("✕ CANCEL", use_container_width=True)
            with cs:
                submit_p3 = st.form_submit_button("⟶  SUBMIT PHASE 3", use_container_width=True)
        if cancel_p3:
            _close()
            st.rerun()
        if submit_p3:
            errs_new = {}
            if not nx_model.strip():
                errs_new["nx_model"] = True
            if not tc_ebom.strip():
                errs_new["tc_ebom"] = True
            if errs_new:
                st.session_state["modal_errs"] = errs_new
                st.rerun()
            else:
                db.complete_phase3(coupon_id, tc_ebom.strip(), uname())
                db.add_phase_comment(coupon_id, 3, "submit", uname(), udisp(), p3_comment)
                st.session_state.pop("modal_errs", None)
                if coupon.get("jira_ticket"):
                    jira_comment = _build_jira_comment(
                        coupon_id, 3,
                        f"Phase 3 COMPLETE — Engineering data submitted.\n"
                        f"NX Model: {nx_model.strip()} | TC EBOM: {tc_ebom.strip()}\n"
                        f"Submitted by: {udisp()} ({uname()})\n"
                        f"Unlocking parallel: Phase 4 (Procurement) · Phase 5 (Instructions) · Phase 6 (Resourcing).",
                    )
                    with st.spinner("Updating Jira…"):
                        jira_api.advance_phase(coupon["jira_ticket"], new_phase=4, comment=jira_comment)
                _close()
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 4 — Procurement / Scheduling
    # ══════════════════════════════════════════════════════════════════════════
    elif phase == 4:
        errs = st.session_state.get("modal_errs", {})
        if errs:
            st.markdown(
                f'<div style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;'
                f'border-left:4px solid #ffb300;padding:10px 16px;border-radius:2px;margin-bottom:12px">'
                f'<span style="color:#ffb300;font-size:0.88em;">⚠ &nbsp;{len(errs)} REQUIRED FIELD{"S" if len(errs)!=1 else ""} MISSING</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with st.form("modal_phase4_form"):
            st.markdown("**PROCUREMENT DETAILS**")
            st.markdown("<hr>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f'<div style="color:{"#ffc400" if "pr_number" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">PR NUMBER <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                pr_number = st.text_input("pr", key="mp4_pr", placeholder="e.g. PR-2026-0042", label_visibility="collapsed")
                if "pr_number" in errs:
                    st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                st.markdown(f'<div style="color:{"#ffc400" if "vendor" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">VENDOR / SUPPLIER <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                vendor = st.text_input("vnd", key="mp4_vendor", placeholder="e.g. Titanium Forge Inc.", label_visibility="collapsed")
                if "vendor" in errs:
                    st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">ESTIMATED DELIVERY DATE</div>', unsafe_allow_html=True)
                delivery_date = st.date_input("del", key="mp4_delivery", label_visibility="collapsed")
            with col2:
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">RFQ REFERENCE</div>', unsafe_allow_html=True)
                rfq_ref = st.text_input("rfq", key="mp4_rfq", placeholder="e.g. RFQ-2026-0088 (optional)", label_visibility="collapsed")
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">PO NUMBER</div>', unsafe_allow_html=True)
                po_number = st.text_input("po", key="mp4_po", placeholder="e.g. PO-2026-0088 (if issued)", label_visibility="collapsed")
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">PROCUREMENT NOTES</div>', unsafe_allow_html=True)
                p4_notes = st.text_area("p4n", key="mp4_notes", placeholder="Scheduling constraints, lead time notes…", height=80, label_visibility="collapsed")
            st.markdown(
                '<div style="padding:9px 12px;background:#060e18;border:1px solid #0d3040;'
                'border-left:3px solid #0d6080;border-radius:2px;font-size:0.78em;color:#2a7090;margin:10px 0">'
                '⟶ On submit, Jira will update: <span style="color:#00aacc">Procurement → Receiving</span></div>',
                unsafe_allow_html=True,
            )
            p4_comment = st.text_area("SUBMISSION COMMENT (OPTIONAL)", key="mp4_comment", placeholder="Notes for Phase 7 / Material Receiving…", height=50, label_visibility="visible")
            cb, _, cs = st.columns([1, 3, 1])
            with cb:
                cancel_p4 = st.form_submit_button("✕ CANCEL", use_container_width=True)
            with cs:
                submit_p4 = st.form_submit_button("⟶  SUBMIT TO PROCUREMENT", use_container_width=True)
        if cancel_p4:
            _close()
            st.rerun()
        if submit_p4:
            missing = {k for k, v in {"pr_number": pr_number, "vendor": vendor}.items() if not v.strip()}
            if missing:
                st.session_state["modal_errs"] = {k: True for k in missing}
                st.rerun()
            else:
                data = {
                    "pr_number": pr_number.strip(), "vendor": vendor.strip(),
                    "delivery_date": str(delivery_date), "rfq_ref": rfq_ref.strip(),
                    "po_number": po_number.strip(), "notes": p4_notes.strip(),
                }
                db.save_phase_submission(coupon_id, 4, uname(), data)
                db.phase_complete(coupon_id, 4, [7])
                db.add_phase_comment(coupon_id, 4, "submit", uname(), udisp(), p4_comment)
                st.session_state.pop("modal_errs", None)
                if coupon.get("jira_ticket"):
                    jira_comment = _build_jira_comment(
                        coupon_id, 4,
                        f"Phase 4 COMPLETE — Procurement submitted by {udisp()}.\n"
                        f"PR: {pr_number.strip()} | Vendor: {vendor.strip()} | Delivery: {delivery_date}\n"
                        f"Advancing to Phase 7: Material Receiving.",
                    )
                    with st.spinner("Updating Jira…"):
                        jira_api.advance_phase(coupon["jira_ticket"], new_phase=7, comment=jira_comment)
                st.markdown(
                    f'<div style="padding:18px;border:1px solid #00d4ff;background:#0e2a40;'
                    f'border-radius:2px;text-align:center;margin:12px 0">'
                    f'<div style="font-size:1.1em;color:#00d4ff;letter-spacing:0.15em">✓ PHASE 4 COMPLETE</div>'
                    f'<div style="color:#c0d8e0;margin-top:6px">PR: <strong style="color:#00d4ff">{pr_number.strip()}</strong> &nbsp;·&nbsp; Vendor: {vendor.strip()}</div>'
                    f'<div style="color:#5aaccc;font-size:0.83em;margin-top:6px">Advancing to Phase 7: Material Receiving.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 6 — Resourcing / Work Allocation
    # ══════════════════════════════════════════════════════════════════════════
    elif phase == 6:
        errs = st.session_state.get("modal_errs", {})
        if errs:
            st.markdown(
                f'<div style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;'
                f'border-left:4px solid #ffb300;padding:10px 16px;border-radius:2px;margin-bottom:12px">'
                f'<span style="color:#ffb300;font-size:0.88em;">⚠ &nbsp;{len(errs)} REQUIRED FIELD{"S" if len(errs)!=1 else ""} MISSING</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with st.form("modal_phase6_form"):
            st.markdown("**WORK ALLOCATION**")
            st.markdown("<hr>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f'<div style="color:{"#ffc400" if "technician" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">ASSIGNED TECHNICIAN <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                technician = st.text_input("tech", key="mp6_tech", placeholder="e.g. Chris Martinez", label_visibility="collapsed")
                if "technician" in errs:
                    st.markdown('<span class="err-msg">▲ Required</span>', unsafe_allow_html=True)
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">SCHEDULED START DATE</div>', unsafe_allow_html=True)
                start_date = st.date_input("start", key="mp6_start", label_visibility="collapsed")
                st.markdown(f'<div style="color:{"#ffc400" if "end_date" in errs else "#5aaccc"};font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">SCHEDULED END DATE <span style="color:#ffc400">*</span></div>', unsafe_allow_html=True)
                end_date = st.date_input("end", key="mp6_end", label_visibility="collapsed")
                if "end_date" in errs:
                    st.markdown('<span class="err-msg">▲ End date must be after start date</span>', unsafe_allow_html=True)
            with col2:
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">SHIFT / CREW</div>', unsafe_allow_html=True)
                shift = st.text_input("shft", key="mp6_shift", placeholder="e.g. Day Shift A", label_visibility="collapsed")
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">WORK PACKAGE REFERENCE</div>', unsafe_allow_html=True)
                wp_ref = st.text_input("wp", key="mp6_wp", placeholder="e.g. WP-2026-0042", label_visibility="collapsed")
                st.markdown('<div style="color:#5aaccc;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">RESOURCING NOTES</div>', unsafe_allow_html=True)
                p6_notes = st.text_area("p6n", key="mp6_notes", placeholder="Constraints, dependencies, special requirements…", height=80, label_visibility="collapsed")
            st.markdown(
                '<div style="padding:9px 12px;background:#060e18;border:1px solid #0d3040;'
                'border-left:3px solid #0d6080;border-radius:2px;font-size:0.78em;color:#2a7090;margin:10px 0">'
                '⟶ On submit, Jira will update: <span style="color:#00aacc">Resourcing → Execution</span></div>',
                unsafe_allow_html=True,
            )
            p6_comment = st.text_area("SUBMISSION COMMENT (OPTIONAL)", key="mp6_comment", placeholder="Notes for Phase 8 / Work Execution…", height=50, label_visibility="visible")
            cb, _, cs = st.columns([1, 3, 1])
            with cb:
                cancel_p6 = st.form_submit_button("✕ CANCEL", use_container_width=True)
            with cs:
                submit_p6 = st.form_submit_button("⟶  SUBMIT WORK ALLOCATION", use_container_width=True)
        if cancel_p6:
            _close()
            st.rerun()
        if submit_p6:
            missing = {k for k, v in {"technician": technician}.items() if not v.strip()}
            if start_date >= end_date:
                missing.add("end_date")
            if missing:
                st.session_state["modal_errs"] = {k: True for k in missing}
                st.rerun()
            else:
                data = {
                    "technician": technician.strip(), "start_date": str(start_date),
                    "end_date": str(end_date), "shift": shift.strip(),
                    "wp_ref": wp_ref.strip(), "notes": p6_notes.strip(),
                }
                db.save_phase_submission(coupon_id, 6, uname(), data)
                db.phase_complete(coupon_id, 6, [8])
                db.add_phase_comment(coupon_id, 6, "submit", uname(), udisp(), p6_comment)
                st.session_state.pop("modal_errs", None)
                if coupon.get("jira_ticket"):
                    jira_comment = _build_jira_comment(
                        coupon_id, 6,
                        f"Phase 6 COMPLETE — Work allocation submitted by {udisp()}.\n"
                        f"Technician: {technician.strip()} | Start: {start_date} | End: {end_date}\n"
                        f"Converging to Phase 8: Work Execution.",
                    )
                    with st.spinner("Updating Jira…"):
                        jira_api.advance_phase(coupon["jira_ticket"], new_phase=8, comment=jira_comment)
                st.markdown(
                    f'<div style="padding:18px;border:1px solid #00d4ff;background:#0e2a40;'
                    f'border-radius:2px;text-align:center;margin:12px 0">'
                    f'<div style="font-size:1.1em;color:#00d4ff;letter-spacing:0.15em">✓ PHASE 6 COMPLETE</div>'
                    f'<div style="color:#c0d8e0;margin-top:6px">Technician: <strong style="color:#00d4ff">{technician.strip()}</strong> &nbsp;·&nbsp; {start_date} → {end_date}</div>'
                    f'<div style="color:#5aaccc;font-size:0.83em;margin-top:6px">Work allocation submitted. Phase 8 unlocks when phases 5 and 7 also complete.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 9 — NCR / Close
    # ══════════════════════════════════════════════════════════════════════════
    elif phase == 9:
        signoffs     = db.get_signoffs(coupon_id, 9)
        signed_roles = {s["role"] for s in signoffs}
        current_role = role()
        qe_signed    = "QE" in signed_roles

        st.markdown("**NCR ASSESSMENT**")
        if qe_signed:
            rec = next(s for s in signoffs if s["role"] == "QE")
            st.markdown(
                f'<div style="background:rgba(0,160,80,0.10);border-left:3px solid #00cc77;'
                f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                f'<span style="color:#00ff99;font-weight:bold">✓ QE Assessment Complete</span>'
                f'<span style="color:#5adba0;font-size:0.78em;margin-left:12px">'
                f'By {rec["display_name"]} · {rec["signed_at"][:16]}</span>'
                f'<span style="color:#5adba0;font-size:0.78em;display:block;margin-top:2px">'
                f'Assessment: <span style="color:#00f5ff">{rec["notes"] or "—"}</span></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        elif current_role == "QE":
            st.markdown(
                '<div style="background:rgba(0,212,255,0.04);border-left:3px solid #00d4ff;'
                'padding:10px 14px;margin:5px 0;border-radius:2px">'
                '<span style="color:#00d4ff">⟶ QE: Initiate NCR assessment</span></div>',
                unsafe_allow_html=True,
            )
            ncr_required = st.checkbox("Non-conformance identified — NCR required", key="mp9_ncr_flag")
            if ncr_required:
                col1, col2 = st.columns(2)
                with col1:
                    ncr_number = st.text_input("NCR Number", key="mp9_ncr_num", placeholder="e.g. NCR-2026-0042")
                    ncr_disposition = st.selectbox("Disposition", ["Use As Is", "Rework", "Repair", "Return to Vendor", "Scrap"], key="mp9_disp")
                with col2:
                    ncr_desc = st.text_area("Non-Conformance Description", key="mp9_ncr_desc", height=80, placeholder="Describe the non-conformance…")
                assessment_notes = f"NCR REQUIRED · {ncr_number or 'TBD'} · Disposition: {ncr_disposition} · {ncr_desc}"
            else:
                assessment_notes = "NO NCR — Work conforms to all requirements. Cleared for closure."
            p9_qe_comment = st.text_area("Comment (optional)", key="mp9_qe_cmt", height=50, placeholder="Additional context…", label_visibility="visible")
            if st.button("✓ SUBMIT NCR ASSESSMENT", key="mp9_qe_sign"):
                db.add_signoff(coupon_id, 9, "QE", uname(), udisp(), notes=assessment_notes)
                db.add_phase_comment(coupon_id, 9, "signoff", uname(), udisp(), p9_qe_comment)
                st.rerun()
        else:
            hint = "" if current_role in ("ME", "Mechanic") else " &nbsp;<span style='color:#4a8090;font-size:0.75em'>(log in as qe_user)</span>"
            st.markdown(
                f'<div style="background:rgba(255,179,0,0.07);border-left:3px solid #7a6020;'
                f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#c8a040">'
                f"⏳ QE Assessment — awaiting sign-off{hint}</div>",
                unsafe_allow_html=True,
            )

        if qe_signed:
            st.markdown("**DISPOSITION CONFIRMATION**")
            for r_key, r_label in [("ME", "Manufacturing Engineer"), ("Mechanic", "Mechanic (Mfg Tech)")]:
                if r_key in signed_roles:
                    rec = next(s for s in signoffs if s["role"] == r_key)
                    is_mine = (r_key == current_role)
                    lbl_c = "#00ff99" if is_mine else "#00cc77"
                    meta_c = "#5adba0" if is_mine else "#2a8060"
                    tag = "✓ YOU CONFIRMED" if is_mine else "✓"
                    st.markdown(
                        f'<div style="background:rgba(0,160,80,0.10);border-left:3px solid #00cc77;'
                        f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                        f'<span style="color:{lbl_c};font-weight:bold">{tag} {r_label}</span>'
                        f'<span style="color:{meta_c};font-size:0.78em;margin-left:12px">'
                        f'{rec["display_name"]} · {rec["signed_at"][:16]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                elif current_role == r_key:
                    st.markdown(
                        f'<div style="background:rgba(0,212,255,0.04);border-left:3px solid #00d4ff;'
                        f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                        f'<span style="color:#00d4ff">⟶ Your confirmation required: {r_label}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    cmt_val = st.text_area("Comment (optional)", key=f"mp9_cmt_{r_key}", height=50, placeholder="Disposition notes…", label_visibility="visible")
                    if st.button(f"✓ CONFIRM DISPOSITION — {r_label.upper()}", key=f"mp9_sign_{r_key}"):
                        db.add_signoff(coupon_id, 9, r_key, uname(), udisp())
                        db.add_phase_comment(coupon_id, 9, "signoff", uname(), udisp(), cmt_val)
                        st.rerun()
                else:
                    hint = "" if current_role in {"QE", "ME", "Mechanic"} else f" &nbsp;<span style='color:#4a8090;font-size:0.75em'>(log in as me_user / mechanic)</span>"
                    st.markdown(
                        f'<div style="background:rgba(255,179,0,0.07);border-left:3px solid #7a6020;'
                        f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#c8a040">'
                        f"⏳ {r_label} — awaiting confirmation{hint}</div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("<br>", unsafe_allow_html=True)
        signed_count = len(signed_roles & {"QE", "ME", "Mechanic"})
        st.progress(signed_count / 3, text=f"DISPOSITION SIGN-OFF: {signed_count} / 3")

        if db.phase9_complete(coupon_id):
            st.markdown(
                '<div style="padding:14px;border:1px solid #00d4ff;background:#0e2a40;'
                'text-align:center;margin-top:12px;border-radius:2px">'
                '<div style="color:#00d4ff;letter-spacing:0.1em">✓ NCR REVIEW COMPLETE — READY TO CLOSE</div>'
                '<div style="color:#5aaccc;font-size:0.82em;margin-top:4px">'
                'All roles confirmed. QE must close the work order.</div></div>',
                unsafe_allow_html=True,
            )
            if current_role == "QE":
                st.markdown("<br>", unsafe_allow_html=True)
                p9_close_comment = st.text_area(
                    "Closing Comment (optional)", key="mp9_close_cmt",
                    height=50, placeholder="Final notes for the work order record…", label_visibility="visible",
                )
                if st.button("✓ CLOSE WORK ORDER", key="mp9_close"):
                    db.add_phase_comment(coupon_id, 9, "close", uname(), udisp(), p9_close_comment)
                    db.close_work_order(coupon_id, uname())
                    jira_ok = {"label_ok": True, "comment_ok": True, "transition_ok": True}
                    if coupon.get("jira_ticket"):
                        jira_comment = _build_jira_comment(
                            coupon_id, 9,
                            f"Work order CLOSED — Phase 9 NCR review complete.\nClosed by: {udisp()} ({uname()})",
                        )
                        with st.spinner("Closing Jira ticket…"):
                            jira_ok = jira_api.close_issue(coupon["jira_ticket"], comment=jira_comment)
                    st.markdown(
                        f'<div style="padding:18px;border:1px solid #00d4ff;background:#0e2a40;'
                        f'border-radius:2px;text-align:center;margin:12px 0">'
                        f'<div style="font-size:1.2em;color:#00d4ff;letter-spacing:0.15em">✓ WORK ORDER CLOSED</div>'
                        f'<div style="color:#c0d8e0;margin-top:6px">Work Order: <strong style="color:#00d4ff">{coupon_id}</strong></div>'
                        f'<div style="color:#5aaccc;font-size:0.82em;margin-top:6px">Closed by {udisp()} · {coupon["part_number"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<hr style="border-color:#1e5068">', unsafe_allow_html=True)
        if st.button("✕ CANCEL", key="md_cancel_9", use_container_width=True):
            _close()
            st.rerun()


# ── HEADER ────────────────────────────────────────────────────────────────────
def header():
    # ── Feedback dialog trigger (must be before any columns) ──────────────────
    if st.session_state.get("show_feedback"):
        feedback.feedback_dialog()

    _mode_label = "PREVIEW" if is_preview() else "DEMO"
    _mode_color = "#00d4ff" if is_preview() else "#ffc400"
    c1, _, c2, c3, c4 = st.columns([5, 0.5, 1, 1, 1])
    with c1:
        st.markdown(
            f'<div style="font-size:1.05em;color:#00f5ff;letter-spacing:0.2em;text-shadow:0 0 14px rgba(0,245,255,0.55)">'
            f'◈ WORK INTAKE <span style="color:#2a7090">// MTE</span>'
            f'&nbsp;&nbsp;<span style="background:rgba(0,0,0,0.4);border:1px solid {_mode_color};'
            f'color:{_mode_color};font-size:0.52em;padding:2px 8px;border-radius:2px;'
            f'letter-spacing:0.12em;vertical-align:middle">{_mode_label}</span></div>'
            f'<div style="font-size:0.72em;color:#2a7080;letter-spacing:0.1em">'
            f'SESSION: <span style="color:#00d4ff">{udisp()}</span> [{role()}]</div>',
            unsafe_allow_html=True,
        )
    with c2:
        if st.button("✉ FEEDBACK", key="hdr_feedback"):
            st.session_state["show_feedback"] = True
            st.session_state.pop("_fb_submitted", None)
            st.session_state.pop("_fb_ticket_id", None)
            st.rerun()
    with c3:
        if st.button("⇄ SWITCH", key="hdr_switch"):
            for k, v in _DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()
    with c4:
        if st.button("⏻ LOGOUT", key="hdr_logout"):
            for k, v in _DEFAULTS.items():
                st.session_state[k] = v
            st.rerun()
    st.markdown("<hr>", unsafe_allow_html=True)


# ── PAGE: LOGIN ───────────────────────────────────────────────────────────────
def page_login():
    st.markdown(CSS, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;margin-bottom:28px">'
            '<div style="font-size:2.4em;color:#00d4ff;letter-spacing:0.35em">◈ WORK INTAKE</div>'
            '<div style="color:#00d4ff;font-size:0.8em;letter-spacing:0.2em;margin-top:4px">'
            "MTE MANUFACTURING EXECUTION &nbsp;//&nbsp; V1</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        with st.form("login"):
            username = st.text_input("USERNAME", placeholder="username")
            password = st.text_input("PASSWORD", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("⟶  AUTHENTICATE", use_container_width=True)

        if submitted:
            user = db.authenticate(username, password)
            if user:
                st.session_state.auth = True
                st.session_state.user = user
                st.session_state.page = "dashboard"
                for _k in ["modal_phase", "modal_coupon_id", "modal_errs",
                           "mp1_submitted", "mp1_new_cid", "mp1_jira", "mp1_priority", "mp1_part"]:
                    st.session_state.pop(_k, None)
                st.rerun()
            else:
                st.markdown(
                    '<p style="color:#ff4444;text-align:center;font-size:0.88em">⚠ AUTHENTICATION FAILED</p>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            '<div style="margin-top:20px;padding:14px 16px;border:1px solid #00f5ff;'
            'background:rgba(0,245,255,0.06);border-left:3px solid #00f5ff;'
            'font-size:0.82em;color:#7dd8e8;line-height:2;border-radius:2px">'
            '<span style="color:#00f5ff;letter-spacing:0.12em;font-size:0.9em">⬡ DEMO CREDENTIALS</span>'
            ' &nbsp;—&nbsp; all passwords: <span style="color:#ffc400;font-weight:bold">demo</span><br>'
            '<span style="color:#a0cfe0">stakeholder &nbsp;·&nbsp; de_user &nbsp;·&nbsp; me_user &nbsp;·&nbsp; weld_eng</span><br>'
            '<span style="color:#a0cfe0">supply_chain &nbsp;·&nbsp; ie_user &nbsp;·&nbsp; qe_user &nbsp;·&nbsp; warehouse &nbsp;·&nbsp; mechanic</span>'
            "</div>"
            '<div style="margin-top:14px;padding:14px 16px;border:1px solid #1a3a4a;'
            'background:rgba(0,20,40,0.6);border-left:3px solid #1e6080;'
            'font-size:0.78em;line-height:1;border-radius:2px">'
            '<div style="color:#00f5ff;letter-spacing:0.12em;margin-bottom:10px;font-size:0.9em">◈ THE 9-PHASE PROCESS</div>'
            '<table style="width:100%;border-collapse:collapse">'
            '<tr style="border-bottom:1px solid #0d2030">'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 1</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">Initiate design request — NX model + TC engineering item</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">stakeholder, de_user, me_user, weld_eng</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid #0d2030">'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 2</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">Align on design, fabrication &amp; manufacturing processes</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">de_user, me_user, weld_eng</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid #0d2030">'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 3</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">DE creates NX design + TC EBOM</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">de_user</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid #0d2030">'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 4</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">Procurement / scheduling — PR / RFQ / PO</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">supply_chain</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid #0d2030">'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 5</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">Work instructions — fabrication / assembly / quality</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">me_user, weld_eng, qe_user</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid #0d2030">'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 6</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">Resourcing / work allocation</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">ie_user</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid #0d2030">'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 7</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">Material receiving</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">supply_chain, qe_user, warehouse</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid #0d2030">'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 8</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">WORK EXECUTION — all branches converge</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">mechanic, me_user, qe_user</td>'
            '</tr>'
            '<tr>'
            '<td style="padding:5px 8px 5px 0;color:#00d4ff;font-weight:bold;white-space:nowrap;vertical-align:top">Ph 9</td>'
            '<td style="padding:5px 8px;color:#c0dde8;vertical-align:top">Non-conformance review (NCR)</td>'
            '<td style="padding:5px 0 5px 8px;color:#7aabb8;font-size:0.9em;vertical-align:top;white-space:nowrap">qe_user, me_user, mechanic</td>'
            '</tr>'
            '</table>'
            '</div>',
            unsafe_allow_html=True,
        )


def render_phase_history(coupon_id: str, coupon: dict):
    """Expandable section showing all completed phase outputs for context."""
    if is_preview():
        pv = coupon
        p1_time = pv.get("p1_submitted_at", pv.get("created_at", "2026-03-17 09:00"))[:16]
        preview_rows = [("1", "INITIATE", [
            ("Part Number",           pv.get("part_number", "—")),
            ("NX Model Ref",          pv.get("nx_model_ref", "—")),
            ("TC Engineering Item",   pv.get("tc_engineering_item", "—")),
            ("Description",           pv.get("description", "—")),
            ("Priority",              pv.get("priority", "—")),
            ("Requesting Stakeholder",pv.get("requesting_stakeholder", "—")),
            ("Notes",                 pv.get("notes") or "—"),
        ], f"Submitted {p1_time}")]
        with st.expander("◈  PHASE HISTORY — click to expand", expanded=False):
            for ph_num, ph_name, fields, timestamp in preview_rows:
                st.markdown(
                    f'<div style="margin-bottom:10px">'
                    f'<span style="background:rgba(0,212,255,0.12);border:1px solid #00d4ff;color:#00d4ff;'
                    f'padding:2px 8px;font-size:0.78em;letter-spacing:0.08em;border-radius:2px">PHASE {ph_num} · {ph_name}</span>'
                    f'<span style="color:#5ab8cc;font-size:0.72em;margin-left:10px">{timestamp}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                cols = st.columns(2)
                for i, (label, value) in enumerate(fields):
                    with cols[i % 2]:
                        st.markdown(
                            f'<div style="margin-bottom:6px;font-size:0.82em">'
                            f'<span style="color:#7ac8d8">{label}</span><br>'
                            f'<span style="color:#e0f2fa">{value}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                st.markdown('<hr style="border-color:#1a3a4a;margin:8px 0">', unsafe_allow_html=True)
        return

    rows = []

    # Phase 1 — always present
    p1_time = coupon.get("p1_submitted_at", coupon.get("created_at", ""))[:16]
    rows.append(("1", "INITIATE", [
        ("Part Number",           coupon.get("part_number", "—")),
        ("NX Model Ref",          coupon.get("nx_model_ref", "—")),
        ("TC Engineering Item",   coupon.get("tc_engineering_item", "—")),
        ("Description",           coupon.get("description", "—")),
        ("Priority",              coupon.get("priority", "—")),
        ("Requesting Stakeholder",coupon.get("requesting_stakeholder", "—")),
        ("Notes",                 coupon.get("notes") or "—"),
    ], f"Submitted {p1_time}"))

    # Phase 2 — signoffs
    p2_sigs = db.get_signoffs(coupon_id, 2)
    if p2_sigs:
        fields = [(s["display_name"], f"Signed {s['signed_at'][:16]}") for s in p2_sigs]
        rows.append(("2", "ALIGN", fields, f"Completed {(coupon.get('p2_completed_at') or '')[:16]}"))

    # Phase 3 — tc_ebom
    if coupon.get("p3_tc_ebom"):
        rows.append(("3", "NX DESIGN", [
            ("TC EBOM Reference", coupon["p3_tc_ebom"]),
            ("Completed By",      coupon.get("p3_completed_by") or "—"),
        ], f"Completed {(coupon.get('p3_completed_at') or '')[:16]}"))

    # Phase 4 — procurement submission
    p4 = db.get_phase_submission(coupon_id, 4)
    if p4:
        d = p4["data"]
        rows.append(("4", "PROCUREMENT", [
            ("PR Number",          d.get("pr_number", "—")),
            ("Vendor / Supplier",  d.get("vendor", "—")),
            ("Est. Delivery Date", d.get("delivery_date", "—")),
            ("RFQ Reference",      d.get("rfq_ref") or "—"),
            ("PO Number",          d.get("po_number") or "—"),
            ("Notes",              d.get("notes") or "—"),
        ], f"Submitted {p4['submitted_at'][:16]}"))

    # Phase 5 — WI signoffs
    p5_sigs = db.get_signoffs(coupon_id, 5)
    if p5_sigs:
        ref_labels = {"ME": "WI Doc Ref", "Weld Engineer": "WPS / Weld Proc Ref", "QE": "Inspection Plan Ref"}
        fields = []
        for s in p5_sigs:
            label = ref_labels.get(s["role"], s["role"])
            fields.append((f"{s['display_name']} ({s['role']})", f"{label}: {s['notes'] or '—'} · {s['signed_at'][:16]}"))
        rows.append(("5", "WORK INSTRUCTIONS", fields, "Sign-offs complete"))

    # Phase 6 — resourcing submission
    p6 = db.get_phase_submission(coupon_id, 6)
    if p6:
        d = p6["data"]
        rows.append(("6", "RESOURCING", [
            ("Assigned Technician",   d.get("technician", "—")),
            ("Scheduled Start",       d.get("start_date", "—")),
            ("Scheduled End",         d.get("end_date", "—")),
            ("Shift / Crew",          d.get("shift") or "—"),
            ("Work Package Ref",      d.get("wp_ref") or "—"),
            ("Notes",                 d.get("notes") or "—"),
        ], f"Submitted {p6['submitted_at'][:16]}"))

    # Phase 7 — receiving signoffs
    p7_sigs = db.get_signoffs(coupon_id, 7)
    if p7_sigs:
        ref_labels = {"Supply Chain": "PO / Packing Slip Ref", "QE": "Inspection Record Ref", "Warehouse/MMO": "Storage Location / Bin"}
        fields = []
        for s in p7_sigs:
            label = ref_labels.get(s["role"], s["role"])
            fields.append((f"{s['display_name']} ({s['role']})", f"{label}: {s['notes'] or '—'} · {s['signed_at'][:16]}"))
        rows.append(("7", "MATERIAL RECEIVING", fields, "Sign-offs complete"))

    # Phase 8 — execution signoffs
    p8_sigs = db.get_signoffs(coupon_id, 8)
    if p8_sigs:
        ref_labels = {"Mechanic": "Work Completion Notes", "ME": "ME Sign-Off Notes", "QE": "Inspection Record / QC Ref"}
        fields = []
        for s in p8_sigs:
            label = ref_labels.get(s["role"], s["role"])
            fields.append((f"{s['display_name']} ({s['role']})", f"{label}: {s['notes'] or '—'} · {s['signed_at'][:16]}"))
        rows.append(("8", "EXECUTION", fields, "Sign-offs complete"))

    if not rows:
        return

    with st.expander("📋 PHASE HISTORY — click to expand", expanded=False):
        for ph_num, ph_name, fields, timestamp in rows:
            st.markdown(
                f'<div style="margin-bottom:10px">'
                f'<span style="background:rgba(0,212,255,0.12);border:1px solid #00d4ff;color:#00d4ff;'
                f'padding:2px 8px;font-size:0.78em;letter-spacing:0.08em;border-radius:2px">PHASE {ph_num} · {ph_name}</span>'
                f'<span style="color:#5ab8cc;font-size:0.72em;margin-left:10px">{timestamp}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            cols = st.columns(2)
            for i, (label, value) in enumerate(fields):
                with cols[i % 2]:
                    st.markdown(
                        f'<div style="margin-bottom:6px;font-size:0.82em">'
                        f'<span style="color:#7ac8d8">{label}</span><br>'
                        f'<span style="color:#e0f2fa">{value}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            st.markdown('<hr style="border-color:#1a3a4a;margin:8px 0">', unsafe_allow_html=True)


def render_comments(coupon_id: str):
    """Expandable comment history for this work order."""
    if is_preview():
        with st.expander("◇  COMMENTS & HISTORY (0)", expanded=False):
            st.markdown(
                '<div style="color:#4a8090;font-size:0.82em;padding:6px 0">'
                'No comments — submits disabled in preview mode.</div>',
                unsafe_allow_html=True,
            )
        return
    comments = db.get_phase_comments(coupon_id)
    if not comments:
        return
    with st.expander(f"💬 COMMENTS & HISTORY ({len(comments)})", expanded=False):
        for c in comments:
            st.markdown(
                f'<div style="border-left:3px solid #2a6080;padding:6px 12px;margin:4px 0;font-size:0.82em">'
                f'<span style="color:#00d4ff;font-weight:bold">{c["display_name"]}</span>'
                f'<span style="color:#4a90a0;margin-left:8px">Phase {c["phase"]} · {c["action"].upper()}</span>'
                f'<span style="color:#3a7080;margin-left:8px">{c["posted_at"][:16]}</span>'
                f'<div style="color:#d0eaf5;margin-top:4px">{c["comment"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_phase_nav(coupon: dict, current_phase: int):
    """Compact phase progress strip shown in each phase's work order card."""
    closed = bool(coupon.get("closed_at"))
    completed = set(json.loads(coupon.get("completed_phases") or "[]"))
    cp = coupon.get("current_phase", current_phase)
    active = set(json.loads(coupon.get("active_phases") or f"[{cp}]"))

    # Phases before the earliest active phase are implicitly done —
    # covers phase 1 (never goes through phase_complete) and old records
    # that predate the completed_phases column.
    min_active = min(active) if active else cp + 1

    pills = []
    for n in range(1, 10):
        is_done   = closed or (n in completed) or (n < min_active and n not in active)
        is_active = (not is_done) and (n in active)

        if is_done:
            col, bg = "#00cc77", "rgba(0,160,80,0.15)"
            sym = "✓"
        elif is_active:
            col, bg = "#00f5ff", "rgba(0,245,255,0.12)"
            sym = "●"
        else:
            col, bg = "#1a4050", "rgba(0,0,0,0)"
            sym = str(n)

        border = f"border:1px solid {col};" if (is_done or is_active) else "border:1px solid #0d2030;"
        pills.append(
            f'<span style="display:inline-block;{border}background:{bg};'
            f'color:{col};padding:2px 7px;border-radius:2px;font-size:0.72em;'
            f'margin-right:3px;letter-spacing:0.04em">{sym} P{n}</span>'
        )
    st.markdown(
        '<div style="margin-top:8px">' + "".join(pills) + '</div>',
        unsafe_allow_html=True,
    )


# ── PAGE: DASHBOARD ───────────────────────────────────────────────────────────
def page_dashboard():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    # ── Dialogs must be triggered before any columns/containers ───────────────
    if not is_preview() and st.session_state.get("modal_phase"):
        phase_action_dialog()
    if is_preview() and st.session_state.get("preview_dialog"):
        phase_preview_dialog()

    st.markdown(viz.workflow_svg(current_phase=0, highlight_all=True, phase_counts=db.count_by_phase(), clickable=False), unsafe_allow_html=True)
    if not is_preview():
        inject_keyboard_nav(1)
    st.markdown("<br>", unsafe_allow_html=True)

    if is_preview():
        # ── Phase selector buttons ─────────────────────────────────────────────
        st.markdown(
            '<style>'
            'div[data-testid="stVerticalBlockBorderWrapper"] button[kind="secondary"] {'
            '  font-size:0.36em !important; padding:1px 0px !important;'
            '  min-height:14px !important; line-height:1.0 !important;'
            '  background:rgba(0,212,255,0.12) !important; color:#00d4ff !important;'
            '  border:1px solid rgba(0,212,255,0.4) !important;'
            '}'
            'div[data-testid="stVerticalBlockBorderWrapper"] button[kind="secondary"]:hover {'
            '  background:rgba(0,212,255,0.25) !important; border-color:#00d4ff !important;'
            '}'
            '</style>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.markdown(
                '<div style="color:#00d4ff;font-size:0.68em;letter-spacing:0.12em;margin-bottom:4px">'
                'SELECT PHASE TO PREVIEW</div>',
                unsafe_allow_html=True,
            )
            btn_cols = st.columns(9, gap="small")
            for _ph in range(1, 10):
                with btn_cols[_ph - 1]:
                    _meta = PHASE_META[_ph]
                    if st.button(
                        f"Phase {_ph}",
                        key=f"prev_phase_btn_{_ph}",
                        help=f"Phase {_ph} — {_meta['name']}",
                        use_container_width=True,
                    ):
                        st.session_state["preview_dialog"] = _ph
                        st.rerun()
    c1, c2 = st.columns([1, 5])
    with c1:
        if is_preview() or role() in ("Stakeholder", "DE", "ME", "Weld Engineer"):
            if st.button("◈ NEW REQUEST", key="new_req"):
                if is_preview():
                    go("phase1")
                else:
                    st.session_state["modal_phase"] = 1
                    st.session_state["modal_coupon_id"] = None
                    st.rerun()

    # ── ROLE CONTEXT CARD ───────────────────────────────────────────────────────
    my_phases = ROLE_PHASES.get(role(), list(range(1, 10)) if is_preview() else [])
    if my_phases:
        coupons_all = db.list_coupons()
        phase_items = []
        for ph in my_phases:
            meta = PHASE_META[ph]
            # Count work orders currently at this phase
            active = [c for c in coupons_all if c["current_phase"] == ph]
            if active:
                badge_col = "#00d4ff"
                badge_txt = f"{len(active)} ACTIVE"
            else:
                badge_col = "#1a4050"
                badge_txt = "NONE"
            phase_items.append(
                f'<div style="display:inline-block;margin-right:16px;margin-bottom:4px">'
                f'<span style="color:#368fa9;font-size:0.75em">PH{ph}</span> '
                f'<span style="color:#c0d8e0;font-size:0.8em">{meta["name"]}</span> '
                f'<span style="background:rgba(0,0,0,0.3);border:1px solid {badge_col};color:{badge_col};'
                f'font-size:0.7em;padding:1px 6px;border-radius:2px;margin-left:4px">{badge_txt}</span>'
                f'</div>'
            )
        phases_html = "".join(phase_items)
        st.markdown(
            f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00d4ff;'
            f'padding:10px 14px;margin-bottom:12px;border-radius:2px">'
            f'<div style="color:#00aacc;font-size:0.72em;letter-spacing:0.12em;margin-bottom:6px">'
            f'YOUR ROLE: <span style="color:#00aacc">{role().upper()}</span>'
            f' &nbsp;·&nbsp; YOUR PHASES</div>'
            f'{phases_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<hr>", unsafe_allow_html=True)
    coupons = db.list_coupons()
    if is_preview() and not coupons:
        coupons = [PREVIEW_COUPON]
    if not coupons:
        st.markdown(
            '<div style="color:#1a5060;font-size:0.88em;padding:16px 0">'
            "No active work orders. Submit a Phase 1 request to begin.</div>",
            unsafe_allow_html=True,
        )
        return

    active  = [c for c in coupons if not c.get("closed_at")]
    closed  = [c for c in coupons if c.get("closed_at")]

    role_map = {
        2: {"DE", "ME", "Weld Engineer"},
        3: {"DE"},
        4: {"Supply Chain"},
        5: {"ME", "Weld Engineer", "QE"},
        6: {"IE"},
        7: {"Supply Chain", "QE", "Warehouse/MMO"},
        8: {"Mechanic", "ME", "QE"},
        9: {"QE", "ME", "Mechanic"},
    }
    label_map = {2: "✓ SIGN OFF", 3: "◉ TO COMPLETE", 4: "▶ SUBMIT", 5: "✓ SIGN OFF", 6: "▶ SUBMIT",
                 7: "✓ RECEIVE", 8: "⚙ EXECUTE", 9: "◉ NCR / CLOSE"}
    page_map  = {2: "phase2", 3: "phase3", 4: "phase4", 5: "phase5", 6: "phase6",
                 7: "phase7", 8: "phase8", 9: "phase9"}

    # ── ACTIVE WORK ORDERS ────────────────────────────────────────────────────
    st.markdown(
        f'<div style="color:#00d4ff;letter-spacing:0.15em;font-size:0.9em;margin-bottom:12px">'
        f'ACTIVE WORK ORDERS'
        f'<span style="color:#1a5060;font-size:0.8em;margin-left:10px">[{len(active)}]</span></div>',
        unsafe_allow_html=True,
    )

    if not active:
        st.markdown(
            '<div style="color:#1a5060;font-size:0.88em;padding:8px 0 16px">'
            "No active work orders. Submit a Phase 1 request to begin.</div>",
            unsafe_allow_html=True,
        )
    for c in active:
        cols = st.columns([2, 3, 1, 2, 1.5])
        with cols[0]:
            st.markdown(
                f'<div style="color:#00d4ff;font-weight:bold">{c["coupon_id"]}</div>'
                f'<div style="color:#1a5060;font-size:0.75em">{jira_badge(c["jira_ticket"], c["jira_status"])}</div>',
                unsafe_allow_html=True,
            )
        with cols[1]:
            desc_short = (c["description"] or "")[:55]
            st.markdown(
                f'<div style="color:#c0d8e0;font-size:0.88em">{c["part_number"] or "—"}</div>'
                f'<div style="color:#666;font-size:0.78em">{desc_short}</div>',
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(
                f'<div style="color:{priority_color(c["priority"])};font-size:0.83em">{c["priority"]}</div>',
                unsafe_allow_html=True,
            )
        with cols[3]:
            _active_disp = json.loads(c.get("active_phases") or f'[{c["current_phase"]}]')
            _phase_str = "·".join(str(p) for p in _active_disp)
            st.markdown(
                f'<div style="color:#00aacc;font-size:0.8em">PHASE {_phase_str}</div>'
                f'<div style="color:#1a5060;font-size:0.75em">{c["jira_status"]}</div>',
                unsafe_allow_html=True,
            )
        with cols[4]:
            _active_disp = json.loads(c.get("active_phases") or f'[{c["current_phase"]}]')
            _my_phases = [p for p in _active_disp if is_preview() or role() in role_map.get(p, set())]
            if _my_phases:
                for _ph in _my_phases:
                    _btn_label = f"{label_map.get(_ph, '◎ VIEW')} P{_ph}" if len(_my_phases) > 1 else label_map.get(_ph, "◎ VIEW")
                    if st.button(_btn_label, key=f"act_{c['coupon_id']}_{_ph}", use_container_width=True):
                        if is_preview():
                            st.session_state["preview_dialog"] = _ph
                        else:
                            st.session_state["modal_phase"] = _ph
                            st.session_state["modal_coupon_id"] = c["coupon_id"]
                        st.rerun()
            else:
                st.markdown(
                    f'<div style="color:#1a5060;font-size:0.78em">Phase {_phase_str}</div>',
                    unsafe_allow_html=True,
                )
        st.markdown('<hr style="margin:4px 0;border-color:#0a1a22">', unsafe_allow_html=True)

    # ── CLOSED WORK ORDERS ────────────────────────────────────────────────────
    if closed:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div style="color:#00cc77;letter-spacing:0.15em;font-size:0.9em;margin-bottom:12px">'
            f'CLOSED WORK ORDERS'
            f'<span style="color:#1a5060;font-size:0.8em;margin-left:10px">[{len(closed)}]</span></div>',
            unsafe_allow_html=True,
        )
        for c in closed:
            closed_ts = (c.get("closed_at") or "")[:16]
            closed_by = c.get("closed_by") or "—"
            cols = st.columns([2, 3, 1, 2, 1.5])
            with cols[0]:
                st.markdown(
                    f'<div style="color:#3a7a5a;font-weight:bold">{c["coupon_id"]}</div>'
                    f'<div style="color:#1a5060;font-size:0.75em">{jira_badge(c["jira_ticket"], "Done")}</div>',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                desc_short = (c["description"] or "")[:55]
                st.markdown(
                    f'<div style="color:#4a7060;font-size:0.88em">{c["part_number"] or "—"}</div>'
                    f'<div style="color:#2a4030;font-size:0.78em">{desc_short}</div>',
                    unsafe_allow_html=True,
                )
            with cols[2]:
                st.markdown(
                    f'<div style="color:#2a5040;font-size:0.83em">{c["priority"]}</div>',
                    unsafe_allow_html=True,
                )
            with cols[3]:
                st.markdown(
                    f'<div style="color:#00cc77;font-size:0.8em">✓ CLOSED</div>'
                    f'<div style="color:#1a5060;font-size:0.75em">{closed_ts}</div>',
                    unsafe_allow_html=True,
                )
            with cols[4]:
                st.markdown(
                    f'<div style="color:#1a5060;font-size:0.75em">by {closed_by}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<hr style="margin:4px 0;border-color:#071510">', unsafe_allow_html=True)



# ── PAGE: PHASE 1 ─────────────────────────────────────────────────────────────
def page_phase1():
    st.markdown(CSS, unsafe_allow_html=True)
    header()
    st.markdown(viz.workflow_svg(current_phase=1, highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(1)
    st.markdown("<br>", unsafe_allow_html=True)
    if is_preview():
        preview_banner()

    st.markdown(
        '<span style="background:rgba(0,212,255,0.08);border:1px solid #00d4ff;color:#00d4ff;'
        'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE 1</span>'
        '&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">INITIATE DESIGN REQUEST</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:16px">'
        "ROLES: Stakeholder · DE · ME · Weld Engineer</div>",
        unsafe_allow_html=True,
    )

    errs = st.session_state.errs

    if errs:
        n = len(errs)
        st.markdown(
            f'<div style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;'
            f'border-left:4px solid #ffb300;padding:10px 16px;border-radius:2px;margin-bottom:12px">'
            f'<span style="color:#ffb300;font-size:0.88em;letter-spacing:0.05em">'
            f'⚠ &nbsp;{n} REQUIRED FIELD{"S" if n!=1 else ""} MISSING — highlighted in amber below</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    _pv = PREVIEW_COUPON if is_preview() else {}
    with st.form("phase1_form"):
        st.markdown("**REQUEST DETAILS**")
        st.markdown("<hr>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(field_lbl("PART NUMBER", "part_number"), unsafe_allow_html=True)
            part_number = st.text_input("pn", key="p1_pn", placeholder="e.g. SUB-CPN-0042", value=_pv.get("part_number", ""), label_visibility="collapsed")
            err_msg("part_number")

            st.markdown(field_lbl("NX MODEL REFERENCE", "nx_model_ref"), unsafe_allow_html=True)
            nx_model_ref = st.text_input("nx", key="p1_nx", placeholder="e.g. NX-Model-v3.2", value=_pv.get("nx_model_ref", ""), label_visibility="collapsed")
            err_msg("nx_model_ref")

            st.markdown(field_lbl("TC ENGINEERING ITEM #", "tc_engineering_item"), unsafe_allow_html=True)
            tc_item = st.text_input("tc", key="p1_tc", placeholder="e.g. TC-10045", value=_pv.get("tc_engineering_item", ""), label_visibility="collapsed")
            err_msg("tc_engineering_item")

        with col2:
            st.markdown(field_lbl("DESCRIPTION", "description"), unsafe_allow_html=True)
            description = st.text_area("desc", key="p1_desc", placeholder="Describe the coupon fabrication requirement…", value=_pv.get("description", ""), height=80, label_visibility="collapsed")
            err_msg("description")

            st.markdown(field_lbl("PRIORITY", "priority", required=False), unsafe_allow_html=True)
            _pri_opts = ["High", "Medium", "Low"]
            _pri_idx = _pri_opts.index(_pv["priority"]) if is_preview() else 1
            priority = st.selectbox("pri", _pri_opts, index=_pri_idx, key="p1_pri", label_visibility="collapsed")

            st.markdown(field_lbl("REQUESTING STAKEHOLDER", "requesting_stakeholder"), unsafe_allow_html=True)
            stakeholder = st.text_input("stk", key="p1_stk", placeholder="Name / Organization", value=_pv.get("requesting_stakeholder", udisp()), label_visibility="collapsed")
            err_msg("requesting_stakeholder")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(field_lbl("NOTES / SPECIAL REQUIREMENTS", "notes", required=False), unsafe_allow_html=True)
        notes = st.text_area("nts", key="p1_notes", placeholder="Additional context, constraints, or requirements…", value=_pv.get("notes", ""), height=70, label_visibility="collapsed")

        st.markdown("<br>", unsafe_allow_html=True)
        cb, _, cs = st.columns([1, 3, 1])
        with cb:
            back = st.form_submit_button("← BACK", use_container_width=True)
        with cs:
            submit = st.form_submit_button("⟶  SUBMIT REQUEST", use_container_width=True)

    if back:
        go("dashboard")

    if submit and is_preview():
        preview_banner()
        return

    if submit:
        required = {
            "part_number": part_number,
            "description": description,
            "nx_model_ref": nx_model_ref,
            "tc_engineering_item": tc_item,
            "requesting_stakeholder": stakeholder,
        }
        missing = {k for k, v in required.items() if not v.strip()}
        if missing:
            st.session_state.errs = {k: True for k in missing}
            st.rerun()
        else:
            data = {
                "part_number": part_number.strip(),
                "description": description.strip(),
                "priority": priority,
                "requesting_stakeholder": stakeholder.strip(),
                "nx_model_ref": nx_model_ref.strip(),
                "tc_engineering_item": tc_item.strip(),
                "notes": notes.strip(),
            }

            # Pre-generate one coupon_id so Jira summary and DB record are in sync
            coupon_id = db.generate_coupon_id()
            jira_payload = dict(data, coupon_id=coupon_id)

            with st.spinner("Creating Jira ticket…"):
                jira_ticket = jira_api.create_issue(jira_payload) or ""

            db.create_coupon(data, uname(), coupon_id=coupon_id, jira_ticket=jira_ticket)
            st.session_state.errs = {}

            jira_ok = bool(jira_ticket)
            jira_note = (
                f'<div style="margin-top:6px">{jira_badge(jira_ticket, "To Do · In Design")}</div>'
                if jira_ok else
                '<div style="color:#ffb300;font-size:0.8em;margin-top:6px">⚠ Jira ticket could not be created — check connectivity</div>'
            )
            st.markdown(
                f'<div style="padding:22px;border:1px solid #00d4ff;background:#001520;'
                f'border-radius:2px;text-align:center;margin:16px 0">'
                f'<div style="font-size:1.3em;color:#00d4ff;letter-spacing:0.2em">✓ REQUEST SUBMITTED</div>'
                f'<div style="color:#c0d8e0;margin-top:8px">Work Order: <strong style="color:#00d4ff">{coupon_id}</strong></div>'
                f'{jira_note}'
                f'<div style="color:#1a5060;font-size:0.83em;margin-top:10px">'
                f"Advancing to Phase 2 — multi-role alignment sign-off required.</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            c1, c2, _ = st.columns([1, 1, 3])
            with c1:
                if st.button("⟶ ADVANCE TO PHASE 2", key="p1_to_p2"):
                    go("phase2", coupon_id)
            with c2:
                if st.button("↩ DASHBOARD", key="p1_dash"):
                    go("dashboard")


# ── PAGE: PHASE 2 ─────────────────────────────────────────────────────────────
def page_phase2():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    coupon = get_coupon_or_preview()
    coupon_id = coupon["coupon_id"] if coupon else None
    if not coupon:
        go("dashboard")
        return

    st.markdown(viz.workflow_svg(current_phase=2, highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(2)
    if is_preview():
        preview_banner()
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        '<span style="background:rgba(0,212,255,0.08);border:1px solid #00d4ff;color:#00d4ff;'
        'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE 2</span>'
        '&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">ALIGN ON DESIGN, FAB & MFG PROCESSES</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:14px">'
        "MULTI-ROLE SIGN-OFF REQUIRED: DE · ME · Weld Engineer</div>",
        unsafe_allow_html=True,
    )

    # Work order card
    st.markdown(
        f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00d4ff;'
        f'padding:14px;margin-bottom:16px;border-radius:2px">'
        f'<div style="color:#00d4ff;font-size:1.05em">{coupon_id}</div>'
        f'<div style="margin-top:4px">{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}</div>'
        f'<div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;font-size:0.82em">'
        f'<div><span style="color:#5aaccc">PART NO.</span><br><span style="color:#c0d8e0">{coupon["part_number"]}</span></div>'
        f'<div><span style="color:#5aaccc">NX MODEL</span><br><span style="color:#c0d8e0">{coupon["nx_model_ref"]}</span></div>'
        f'<div><span style="color:#5aaccc">TC ITEM</span><br><span style="color:#c0d8e0">{coupon["tc_engineering_item"]}</span></div>'
        f'<div><span style="color:#5aaccc">PRIORITY</span><br>'
        f'<span style="color:{priority_color(coupon["priority"])}">{coupon["priority"]}</span></div>'
        f'</div>'
        f'<div style="margin-top:8px;font-size:0.82em"><span style="color:#5aaccc">DESCRIPTION</span><br>'
        f'<span style="color:#c0d8e0">{coupon["description"]}</span></div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    render_phase_nav(coupon, 2)
    render_phase_history(coupon_id, coupon)
    render_comments(coupon_id)
    signoffs    = [] if is_preview() else db.get_signoffs(coupon_id, 2)
    signed_roles = {s["role"] for s in signoffs}
    required_roles = [("DE", "Design Engineer"), ("ME", "Manufacturing Engineer"), ("Weld Engineer", "Weld Engineer")]
    current_role = role() if not is_preview() else "DE"

    st.markdown("**ALIGNMENT SIGN-OFF**", unsafe_allow_html=False)

    for r_key, r_label in required_roles:
        if r_key in signed_roles:
            rec = next(s for s in signoffs if s["role"] == r_key)
            st.markdown(
                f'<div style="background:rgba(0,160,80,0.08);border-left:3px solid #00b464;'
                f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                f'<span style="color:#00cc77">✓ {r_label}</span>'
                f'<span style="color:#1a5060;font-size:0.78em;margin-left:12px">'
                f'Signed by {rec["display_name"]} · {rec["signed_at"][:16]}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            if current_role == r_key:
                st.markdown(
                    f'<div style="background:rgba(0,212,255,0.04);border-left:3px solid #00d4ff;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                    f'<span style="color:#00d4ff">⟶ Your sign-off required: {r_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.text_area("Comment (optional)", key=f"p2_cmt_{r_key}", height=60, placeholder="Add context for downstream phases…", label_visibility="visible")
                if st.button(f"✓ CONFIRM ALIGNMENT — {r_label.upper()}", key=f"sign_{r_key}"):
                    if is_preview():
                        preview_banner()
                    else:
                        db.add_signoff(coupon_id, 2, r_key, uname(), udisp())
                        db.add_phase_comment(coupon_id, 2, "signoff", uname(), udisp(), st.session_state.get(f"p2_cmt_{r_key}", ""))
                        if db.phase2_complete(coupon_id) and coupon.get("jira_ticket"):
                            with st.spinner("Updating Jira…"):
                                jira_api.transition_issue(coupon["jira_ticket"], "In Design")
                        st.rerun()
            else:
                hint = ""
                if current_role not in {k for k, _ in required_roles}:
                    hint = " &nbsp;<span style='color:#1a3040;font-size:0.75em'>(log in as de_user / me_user / weld_eng)</span>"
                st.markdown(
                    f'<div style="background:rgba(255,196,0,0.05);border-left:3px solid #7a5800;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#c8960a">'
                    f"○ {r_label} — awaiting sign-off{hint}</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)
    signed_count = len(signed_roles & {k for k, _ in required_roles})
    st.progress(signed_count / 3, text=f"SIGN-OFF PROGRESS: {signed_count} / 3")

    if db.phase2_complete(coupon_id):
        st.markdown(
            '<div style="padding:16px;border:1px solid #00d4ff;background:#001520;'
            'text-align:center;margin-top:14px;border-radius:2px">'
            '<div style="color:#00d4ff;letter-spacing:0.1em">✓ ALL ROLES ALIGNED — PHASE 2 COMPLETE</div>'
            '<div style="color:#1a5060;font-size:0.82em;margin-top:4px">'
            "Ready to advance to Phase 3 · DE must proceed.</div></div>",
            unsafe_allow_html=True,
        )
        if current_role == "DE" or is_preview():
            st.markdown("<br>", unsafe_allow_html=True)
            adv_comment_p2 = st.text_area("Advance Comment (optional)", key="p2_adv_cmt", height=60, placeholder="Notes for Phase 3…", label_visibility="visible")
            if st.button("⟶ ADVANCE TO PHASE 3", key="p2_advance"):
              if is_preview():
                preview_banner()
              else:
                db.add_phase_comment(coupon_id, 2, "advance", uname(), udisp(), adv_comment_p2)
                db.advance_to_phase3(coupon_id)
                if coupon.get("jira_ticket"):
                    signoffs = db.get_signoffs(coupon_id, 2)
                    names = ", ".join(s["display_name"] for s in signoffs)
                    jira_comment = _build_jira_comment(
                        coupon_id, 2,
                        f"Phase 2 COMPLETE — Alignment sign-offs received from: {names}. "
                        f"Advancing to Phase 3: NX Design + TC EBOM creation.",
                    )
                    with st.spinner("Updating Jira…"):
                        jira_api.transition_issue(coupon["jira_ticket"], "In Design")
                        jira_api.advance_phase(
                            coupon["jira_ticket"],
                            new_phase=3,
                            comment=jira_comment,
                        )
                go("phase3", coupon_id)
        else:
            st.markdown(
                '<div style="color:#1a5060;font-size:0.8em;margin-top:8px">'
                "Log in as <strong style='color:#00aacc'>de_user</strong> to advance.</div>",
                unsafe_allow_html=True,
            )

    

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← DASHBOARD", key="p2_back"):
        go("dashboard")


# ── PAGE: PHASE 3 ─────────────────────────────────────────────────────────────
def page_phase3():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    coupon = get_coupon_or_preview()
    coupon_id = coupon["coupon_id"] if coupon else None
    if not coupon:
        go("dashboard")
        return

    st.markdown(viz.workflow_svg(current_phase=3, highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(3)
    st.markdown("<br>", unsafe_allow_html=True)
    if is_preview():
        preview_banner()

    st.markdown(
        '<span style="background:rgba(0,212,255,0.08);border:1px solid #00d4ff;color:#00d4ff;'
        'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE 3</span>'
        '&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">NX DESIGN + TC EBOM CREATION</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:14px">ROLE: Design Engineer (DE)</div>',
        unsafe_allow_html=True,
    )

    if role() != "DE" and not is_preview():
        st.markdown(
            '<div style="padding:14px;border:1px solid #3a2000;background:#120900;border-radius:2px">'
            '<span style="color:#ffb300">⚠ DE access required for Phase 3.</span>'
            '<span style="color:#1a5060;display:block;margin-top:4px;font-size:0.83em">'
            "Log in as <strong style='color:#00aacc'>de_user</strong> to complete this phase.</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← DASHBOARD", key="p3_back_no_role"):
            go("dashboard")
        return

    # Work order summary
    st.markdown(
        f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00d4ff;'
        f'padding:12px 14px;margin-bottom:14px;border-radius:2px;font-size:0.85em">'
        f'<span style="color:#00d4ff">{coupon_id}</span>'
        f'&nbsp;&nbsp;{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}'
        f'&nbsp;&nbsp;<span style="color:#888">{coupon["part_number"]}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    render_phase_nav(coupon, 3)
    render_phase_history(coupon_id, coupon)
    render_comments(coupon_id)

    errs = st.session_state.errs

    if errs:
        missing = []
        if "nx_model" in errs:
            missing.append("NX model reference")
        if "tc_ebom" in errs:
            missing.append("TC item reference")
        st.markdown(
            f'<div style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;'
            f'border-left:4px solid #ffb300;padding:10px 16px;border-radius:2px;margin-bottom:12px">'
            f'<span style="color:#ffb300;font-size:0.88em;letter-spacing:0.05em">'
            f'⚠ &nbsp;REQUIRED: {" · ".join(missing)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with st.form("phase3_form"):
        st.markdown("**ENGINEERING DATA INPUT**")
        st.markdown("<hr>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(field_lbl("NX MODEL REFERENCE", "nx_model"), unsafe_allow_html=True)
            nx_model = st.text_input("nxm", key="p3_nx", placeholder="e.g. NX-CPN-10045-Rev-A", label_visibility="collapsed")
            err_msg("nx_model")
            st.markdown(field_lbl("TC ITEM REFERENCE #", "tc_ebom"), unsafe_allow_html=True)
            tc_ebom = st.text_input("ebom", key="p3_ebom", placeholder="e.g. TC-EBOM-10045-A", label_visibility="collapsed")
            err_msg("tc_ebom")
        with col2:
            st.markdown('<div style="color:#1a5060;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">MATERIAL SPECIFICATION</div>', unsafe_allow_html=True)
            material_spec = st.text_input("mspec", key="p3_matspec", placeholder="e.g. Ti-6Al-4V AMS 4928", label_visibility="collapsed")
            st.markdown('<div style="color:#1a5060;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">DESIGN NOTES</div>', unsafe_allow_html=True)
            p3_notes = st.text_area("p3n", key="p3_notes", placeholder="Design decisions, deviations, or references…", height=68, label_visibility="collapsed")

        # Jira update preview
        st.markdown(
            '<div style="padding:9px 12px;background:#06090e;border:1px solid #0d2030;'
            'border-radius:2px;font-size:0.78em;color:#1a5060;margin:12px 0">'
            '⟶ On submit, unlocks in parallel: '
            '<span style="color:#00aacc">Phase 4 (Procurement) · Phase 5 (Instructions) · Phase 6 (Resourcing)</span></div>',
            unsafe_allow_html=True,
        )

        p3_comment = st.text_area("SUBMISSION COMMENT (OPTIONAL)", key="p3_comment", placeholder="Notes for downstream phases…", height=60, label_visibility="visible")

        cb, _, cs = st.columns([1, 3, 1])
        with cb:
            back = st.form_submit_button("← BACK", use_container_width=True)
        with cs:
            submit = st.form_submit_button("⟶  SUBMIT PHASE 3", use_container_width=True)

    if back:
        go("dashboard")

    if submit and is_preview():
        preview_banner()
        return

    if submit:
        errs_new = {}
        if not nx_model.strip():
            errs_new["nx_model"] = True
        if not tc_ebom.strip():
            errs_new["tc_ebom"] = True
        if errs_new:
            st.session_state.errs = errs_new
            st.rerun()
        else:
            db.complete_phase3(coupon_id, tc_ebom.strip(), uname())
            db.add_phase_comment(coupon_id, 3, "submit", uname(), udisp(), p3_comment)
            st.session_state.errs = {}
            if coupon.get("jira_ticket"):
                jira_comment = _build_jira_comment(
                    coupon_id, 3,
                    f"Phase 3 COMPLETE — Engineering data submitted.\n"
                    f"NX Model: {nx_model.strip()} | TC EBOM: {tc_ebom.strip()}\n"
                    f"Submitted by: {udisp()} ({uname()})\n"
                    f"Unlocking parallel: Phase 4 (Procurement) · Phase 5 (Instructions) · Phase 6 (Resourcing).",
                )
                with st.spinner("Updating Jira…"):
                    jira_api.advance_phase(coupon["jira_ticket"], new_phase=4, comment=jira_comment)
            st.markdown(
                f'<div style="padding:22px;border:1px solid #00d4ff;background:#001520;'
                f'border-radius:2px;text-align:center;margin:16px 0">'
                f'<div style="font-size:1.3em;color:#00d4ff;letter-spacing:0.2em">✓ PHASE 3 COMPLETE</div>'
                f'<div style="color:#c0d8e0;margin-top:8px">{coupon_id} &nbsp;·&nbsp; '
                f'TC EBOM: <span style="color:#00d4ff">{tc_ebom.strip()}</span></div>'
                f'<div style="margin-top:6px">{jira_badge(coupon["jira_ticket"], "Procurement")}</div>'
                f'<div style="color:#1a5060;font-size:0.83em;margin-top:10px">'
                f"Unlocked in parallel: Phase 4 (Procurement) · Phase 5 (Instructions) · Phase 6 (Resourcing).</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("↩ DASHBOARD", key="p3_done"):
                go("dashboard")


# ── PAGE: PHASE 4 — PROCUREMENT / SCHEDULING ─────────────────────────────────
def page_phase4():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    coupon = get_coupon_or_preview()
    coupon_id = coupon["coupon_id"] if coupon else None
    if not coupon:
        go("dashboard")
        return

    st.markdown(viz.workflow_svg(current_phase=coupon["current_phase"], highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(4)
    if is_preview():
        preview_banner()
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        '<span style="background:rgba(0,212,255,0.08);border:1px solid #00d4ff;color:#00d4ff;'
        'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE 4</span>'
        '&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">PROCUREMENT / SCHEDULING</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:14px">ROLE: Supply Chain</div>',
        unsafe_allow_html=True,
    )

    if role() != "Supply Chain" and not is_preview():
        st.markdown(
            '<div style="padding:14px;border:1px solid #3a2000;background:#120900;border-radius:2px">'
            '<span style="color:#ffb300">⚠ Supply Chain access required for Phase 4.</span>'
            '<span style="color:#1a5060;display:block;margin-top:4px;font-size:0.83em">'
            "Log in as <strong style='color:#00aacc'>supply_chain</strong> to complete this phase.</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("← DASHBOARD", key="p4_back_no_role"):
            go("dashboard")
        return

    # Work order summary
    st.markdown(
        f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00d4ff;'
        f'padding:12px 14px;margin-bottom:14px;border-radius:2px;font-size:0.85em">'
        f'<span style="color:#00d4ff">{coupon_id}</span>'
        f'&nbsp;&nbsp;{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}'
        f'&nbsp;&nbsp;<span style="color:#888">{coupon["part_number"]}</span>'
        f'&nbsp;&nbsp;<span style="color:{priority_color(coupon["priority"])}">{coupon["priority"]}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    render_phase_nav(coupon, 4)
    render_phase_history(coupon_id, coupon)
    render_comments(coupon_id)

    errs = st.session_state.errs
    if errs:
        st.markdown(
            f'<div style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;'
            f'border-left:4px solid #ffb300;padding:10px 16px;border-radius:2px;margin-bottom:12px">'
            f'<span style="color:#ffb300;font-size:0.88em">⚠ &nbsp;{len(errs)} REQUIRED FIELD{"S" if len(errs)!=1 else ""} MISSING</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with st.form("phase4_form"):
        st.markdown("**PROCUREMENT DETAILS**")
        st.markdown("<hr>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(field_lbl("PR NUMBER", "pr_number"), unsafe_allow_html=True)
            pr_number = st.text_input("pr", key="p4_pr", placeholder="e.g. PR-2026-0042", label_visibility="collapsed")
            err_msg("pr_number")

            st.markdown(field_lbl("VENDOR / SUPPLIER", "vendor"), unsafe_allow_html=True)
            vendor = st.text_input("vnd", key="p4_vendor", placeholder="e.g. Titanium Forge Inc.", label_visibility="collapsed")
            err_msg("vendor")

            st.markdown(field_lbl("ESTIMATED DELIVERY DATE", "delivery_date"), unsafe_allow_html=True)
            delivery_date = st.date_input("del", key="p4_delivery", label_visibility="collapsed")

        with col2:
            st.markdown(field_lbl("RFQ REFERENCE", "rfq_ref", required=False), unsafe_allow_html=True)
            rfq_ref = st.text_input("rfq", key="p4_rfq", placeholder="e.g. RFQ-2026-0088 (optional)", label_visibility="collapsed")

            st.markdown(field_lbl("PO NUMBER", "po_number", required=False), unsafe_allow_html=True)
            po_number = st.text_input("po", key="p4_po", placeholder="e.g. PO-2026-0088 (if issued)", label_visibility="collapsed")

            st.markdown('<div style="color:#1a5060;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">PROCUREMENT NOTES</div>', unsafe_allow_html=True)
            p4_notes = st.text_area("p4n", key="p4_notes", placeholder="Scheduling constraints, lead time notes…", height=80, label_visibility="collapsed")

        st.markdown(
            '<div style="padding:9px 12px;background:#06090e;border:1px solid #0d2030;'
            'border-radius:2px;font-size:0.78em;color:#1a5060;margin:12px 0">'
            '⟶ On submit, Jira will update: <span style="color:#00aacc">Procurement → Receiving</span></div>',
            unsafe_allow_html=True,
        )

        p4_comment = st.text_area("SUBMISSION COMMENT (OPTIONAL)", key="p4_comment", placeholder="Notes for Phase 7 / Material Receiving…", height=60, label_visibility="visible")

        cb, _, cs = st.columns([1, 3, 1])
        with cb:
            back = st.form_submit_button("← BACK", use_container_width=True)
        with cs:
            submit = st.form_submit_button("⟶  SUBMIT TO PROCUREMENT", use_container_width=True)

    if back:
        go("dashboard")

    if submit and is_preview():
        preview_banner()
        return

    if submit:
        missing = {k for k, v in {"pr_number": pr_number, "vendor": vendor}.items() if not v.strip()}
        if missing:
            st.session_state.errs = {k: True for k in missing}
            st.rerun()
        else:
            data = {
                "pr_number": pr_number.strip(),
                "vendor": vendor.strip(),
                "delivery_date": str(delivery_date),
                "rfq_ref": rfq_ref.strip(),
                "po_number": po_number.strip(),
                "notes": p4_notes.strip(),
            }
            db.save_phase_submission(coupon_id, 4, uname(), data)
            db.phase_complete(coupon_id, 4, [7])
            db.add_phase_comment(coupon_id, 4, "submit", uname(), udisp(), p4_comment)
            st.session_state.errs = {}
            if coupon.get("jira_ticket"):
                jira_comment = _build_jira_comment(
                    coupon_id, 4,
                    f"Phase 4 COMPLETE — Procurement submitted by {udisp()}.\n"
                    f"PR: {pr_number.strip()} | Vendor: {vendor.strip()} | Delivery: {delivery_date}\n"
                    f"Advancing to Phase 7: Material Receiving.",
                )
                with st.spinner("Updating Jira…"):
                    jira_api.advance_phase(coupon["jira_ticket"], new_phase=7, comment=jira_comment)
            st.markdown(
                f'<div style="padding:22px;border:1px solid #00d4ff;background:#001520;'
                f'border-radius:2px;text-align:center;margin:16px 0">'
                f'<div style="font-size:1.3em;color:#00d4ff;letter-spacing:0.2em">✓ PHASE 4 COMPLETE</div>'
                f'<div style="color:#c0d8e0;margin-top:8px">PR: <strong style="color:#00d4ff">{pr_number.strip()}</strong>'
                f' &nbsp;·&nbsp; Vendor: {vendor.strip()}</div>'
                f'<div style="margin-top:6px">{jira_badge(coupon["jira_ticket"], "Receiving")}</div>'
                f'<div style="color:#1a5060;font-size:0.83em;margin-top:10px">'
                f"Advancing to Phase 7: Material Receiving.</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("↩ DASHBOARD", key="p4_done"):
                go("dashboard")


# ── PAGE: PHASE 5 — WORK INSTRUCTIONS ────────────────────────────────────────
def page_phase5():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    coupon = get_coupon_or_preview()
    coupon_id = coupon["coupon_id"] if coupon else None
    if not coupon:
        go("dashboard")
        return

    st.markdown(viz.workflow_svg(current_phase=coupon["current_phase"], highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(5)
    if is_preview():
        preview_banner()
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        '<span style="background:rgba(0,212,255,0.08);border:1px solid #00d4ff;color:#00d4ff;'
        'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE 5</span>'
        '&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">WORK INSTRUCTIONS — FAB / ASSEMBLY / QUALITY</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:14px">'
        'MULTI-ROLE SIGN-OFF REQUIRED: ME · Weld Engineer · QE</div>',
        unsafe_allow_html=True,
    )

    # Work order card
    st.markdown(
        f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00d4ff;'
        f'padding:14px;margin-bottom:16px;border-radius:2px">'
        f'<div style="color:#00d4ff;font-size:1.05em">{coupon_id}</div>'
        f'<div style="margin-top:4px">{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}</div>'
        f'<div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;font-size:0.82em">'
        f'<div><span style="color:#5aaccc">PART NO.</span><br><span style="color:#c0d8e0">{coupon["part_number"]}</span></div>'
        f'<div><span style="color:#5aaccc">NX MODEL</span><br><span style="color:#c0d8e0">{coupon["nx_model_ref"]}</span></div>'
        f'<div><span style="color:#5aaccc">TC ITEM</span><br><span style="color:#c0d8e0">{coupon["tc_engineering_item"]}</span></div>'
        f'<div><span style="color:#5aaccc">PRIORITY</span><br><span style="color:{priority_color(coupon["priority"])}">{coupon["priority"]}</span></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    render_phase_nav(coupon, 5)
    render_phase_history(coupon_id, coupon)
    render_comments(coupon_id)

    signoffs     = [] if is_preview() else db.get_signoffs(coupon_id, 5)
    signed_roles = {s["role"] for s in signoffs}
    required_roles = [
        ("ME",            "Manufacturing Engineer",  "Work instructions and bill of process defined",  "WI Doc Ref"),
        ("Weld Engineer", "Weld Engineer",           "Welding process document defined",               "WPS / Weld Proc Ref"),
        ("QE",            "Quality Engineer",        "Inspection plan and quality checklist ready",    "Inspection Plan Ref"),
    ]
    current_role = role() if not is_preview() else "ME"

    st.markdown("**WORK INSTRUCTIONS SIGN-OFF**", unsafe_allow_html=False)

    for r_key, r_label, r_confirm_text, r_ref_label in required_roles:
        if r_key in signed_roles:
            rec = next(s for s in signoffs if s["role"] == r_key)
            doc_ref = rec["notes"] or "—"
            st.markdown(
                f'<div style="background:rgba(0,160,80,0.08);border-left:3px solid #00b464;'
                f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                f'<span style="color:#00cc77">✓ {r_label}</span>'
                f'<span style="color:#1a5060;font-size:0.78em;margin-left:12px">'
                f'Signed by {rec["display_name"]} · {rec["signed_at"][:16]}</span>'
                f'<span style="color:#1a5060;font-size:0.78em;display:block;margin-top:2px">'
                f'{r_ref_label}: <span style="color:#00aacc">{doc_ref}</span></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            if current_role == r_key:
                st.markdown(
                    f'<div style="background:rgba(0,212,255,0.04);border-left:3px solid #00d4ff;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                    f'<span style="color:#00d4ff">⟶ Your sign-off required: {r_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                doc_ref_val = st.text_input(
                    f"{r_ref_label}", key=f"p5_ref_{r_key}",
                    placeholder=f"e.g. WI-{coupon_id}-001",
                )
                st.text_area("Comment (optional)", key=f"p5_cmt_{r_key}", height=60, placeholder="Add context for downstream phases…", label_visibility="visible")
                if st.button(f"✓ CONFIRM — {r_confirm_text[:40]}…", key=f"p5_sign_{r_key}"):
                    if is_preview():
                        preview_banner()
                    else:
                        db.add_signoff(coupon_id, 5, r_key, uname(), udisp(), notes=doc_ref_val)
                        db.add_phase_comment(coupon_id, 5, "signoff", uname(), udisp(), st.session_state.get(f"p5_cmt_{r_key}", ""))
                        st.rerun()
            else:
                hint = ""
                if current_role not in {k for k, *_ in required_roles}:
                    hint = " &nbsp;<span style='color:#1a3040;font-size:0.75em'>(log in as me_user / weld_eng / qe_user)</span>"
                st.markdown(
                    f'<div style="background:rgba(255,196,0,0.05);border-left:3px solid #7a5800;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#c8960a">'
                    f"○ {r_label} — awaiting sign-off{hint}</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)
    signed_count = len(signed_roles & {k for k, *_ in required_roles})
    st.progress(signed_count / 3, text=f"SIGN-OFF PROGRESS: {signed_count} / 3")

    if db.phase5_complete(coupon_id):
        st.markdown(
            '<div style="padding:16px;border:1px solid #00d4ff;background:#001520;'
            'text-align:center;margin-top:14px;border-radius:2px">'
            '<div style="color:#00d4ff;letter-spacing:0.1em">✓ ALL ROLES CONFIRMED — PHASE 5 COMPLETE</div>'
            '<div style="color:#1a5060;font-size:0.82em;margin-top:4px">'
            "Ready to advance to Phase 8 · ME must proceed.</div></div>",
            unsafe_allow_html=True,
        )
        if current_role == "ME" or is_preview():
            st.markdown("<br>", unsafe_allow_html=True)
            adv_comment_p5 = st.text_area("Advance Comment (optional)", key="p5_adv_cmt", height=60, placeholder="Notes for Phase 8 / Work Execution…", label_visibility="visible")
            if st.button("⟶ ADVANCE TO PHASE 8 — WORK EXECUTION", key="p5_advance"):
              if is_preview():
                preview_banner()
              else:
                db.add_phase_comment(coupon_id, 5, "advance", uname(), udisp(), adv_comment_p5)
                db.phase_complete(coupon_id, 5, [8])
                if coupon.get("jira_ticket"):
                    sigs = db.get_signoffs(coupon_id, 5)
                    names = ", ".join(s["display_name"] for s in sigs)
                    jira_comment = _build_jira_comment(
                        coupon_id, 5,
                        f"Phase 5 COMPLETE — Work instructions confirmed by: {names}. Converging to Phase 8: Work Execution.",
                    )
                    with st.spinner("Updating Jira…"):
                        jira_api.advance_phase(coupon["jira_ticket"], new_phase=8, comment=jira_comment)
                go("dashboard")
        else:
            st.markdown(
                '<div style="color:#1a5060;font-size:0.8em;margin-top:8px">'
                "Log in as <strong style='color:#00aacc'>me_user</strong> to advance.</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← DASHBOARD", key="p5_back"):
        go("dashboard")


# ── PAGE: PHASE 6 — RESOURCING / WORK ALLOCATION ─────────────────────────────
def page_phase6():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    coupon = get_coupon_or_preview()
    coupon_id = coupon["coupon_id"] if coupon else None
    if not coupon:
        go("dashboard")
        return

    st.markdown(viz.workflow_svg(current_phase=coupon["current_phase"], highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(6)
    if is_preview():
        preview_banner()
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        '<span style="background:rgba(0,212,255,0.08);border:1px solid #00d4ff;color:#00d4ff;'
        'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE 6</span>'
        '&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">RESOURCING / WORK ALLOCATION</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:14px">ROLE: Industrial Engineer (IE)</div>',
        unsafe_allow_html=True,
    )

    if role() != "IE" and not is_preview():
        st.markdown(
            '<div style="padding:14px;border:1px solid #3a2000;background:#120900;border-radius:2px">'
            '<span style="color:#ffb300">⚠ IE access required for Phase 6.</span>'
            '<span style="color:#1a5060;display:block;margin-top:4px;font-size:0.83em">'
            "Log in as <strong style='color:#00aacc'>ie_user</strong> to complete this phase.</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("← DASHBOARD", key="p6_back_no_role"):
            go("dashboard")
        return

    # Work order summary
    st.markdown(
        f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00d4ff;'
        f'padding:12px 14px;margin-bottom:14px;border-radius:2px;font-size:0.85em">'
        f'<span style="color:#00d4ff">{coupon_id}</span>'
        f'&nbsp;&nbsp;{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}'
        f'&nbsp;&nbsp;<span style="color:#888">{coupon["part_number"]}</span>'
        f'&nbsp;&nbsp;<span style="color:{priority_color(coupon["priority"])}">{coupon["priority"]}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    render_phase_nav(coupon, 6)
    render_phase_history(coupon_id, coupon)
    render_comments(coupon_id)

    errs = st.session_state.errs
    if errs:
        st.markdown(
            f'<div style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;'
            f'border-left:4px solid #ffb300;padding:10px 16px;border-radius:2px;margin-bottom:12px">'
            f'<span style="color:#ffb300;font-size:0.88em">⚠ &nbsp;{len(errs)} REQUIRED FIELD{"S" if len(errs)!=1 else ""} MISSING</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with st.form("phase6_form"):
        st.markdown("**WORK ALLOCATION**")
        st.markdown("<hr>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(field_lbl("ASSIGNED TECHNICIAN", "technician"), unsafe_allow_html=True)
            technician = st.text_input("tech", key="p6_tech", placeholder="e.g. Chris Martinez", label_visibility="collapsed")
            err_msg("technician")

            st.markdown(field_lbl("SCHEDULED START DATE", "start_date"), unsafe_allow_html=True)
            start_date = st.date_input("start", key="p6_start", label_visibility="collapsed")

            st.markdown(field_lbl("SCHEDULED END DATE", "end_date"), unsafe_allow_html=True)
            end_date = st.date_input("end", key="p6_end", label_visibility="collapsed")

        with col2:
            st.markdown(field_lbl("SHIFT / CREW", "shift", required=False), unsafe_allow_html=True)
            shift = st.text_input("shft", key="p6_shift", placeholder="e.g. Day Shift A", label_visibility="collapsed")

            st.markdown(field_lbl("WORK PACKAGE REFERENCE", "wp_ref", required=False), unsafe_allow_html=True)
            wp_ref = st.text_input("wp", key="p6_wp", placeholder="e.g. WP-2026-0042", label_visibility="collapsed")

            st.markdown('<div style="color:#1a5060;font-size:0.8em;letter-spacing:0.1em;margin-bottom:2px">RESOURCING NOTES</div>', unsafe_allow_html=True)
            p6_notes = st.text_area("p6n", key="p6_notes", placeholder="Constraints, dependencies, special requirements…", height=80, label_visibility="collapsed")

        st.markdown(
            '<div style="padding:9px 12px;background:#06090e;border:1px solid #0d2030;'
            'border-radius:2px;font-size:0.78em;color:#1a5060;margin:12px 0">'
            '⟶ On submit, Jira will update: <span style="color:#00aacc">Resourcing → Receiving</span></div>',
            unsafe_allow_html=True,
        )

        p6_comment = st.text_area("SUBMISSION COMMENT (OPTIONAL)", key="p6_comment", placeholder="Notes for Phase 7 / Material Receiving…", height=60, label_visibility="visible")

        cb, _, cs = st.columns([1, 3, 1])
        with cb:
            back = st.form_submit_button("← BACK", use_container_width=True)
        with cs:
            submit = st.form_submit_button("⟶  SUBMIT RESOURCING", use_container_width=True)

    if back:
        go("dashboard")

    if submit and is_preview():
        preview_banner()
        return

    if submit:
        missing = {k for k, v in {"technician": technician}.items() if not v.strip()}
        if start_date >= end_date:
            missing.add("end_date")
        if missing:
            st.session_state.errs = {k: True for k in missing}
            st.rerun()
        else:
            data = {
                "technician": technician.strip(),
                "start_date": str(start_date),
                "end_date": str(end_date),
                "shift": shift.strip(),
                "wp_ref": wp_ref.strip(),
                "notes": p6_notes.strip(),
            }
            db.save_phase_submission(coupon_id, 6, uname(), data)
            db.phase_complete(coupon_id, 6, [8])
            db.add_phase_comment(coupon_id, 6, "submit", uname(), udisp(), p6_comment)
            st.session_state.errs = {}
            if coupon.get("jira_ticket"):
                with st.spinner("Updating Jira…"):
                    jira_comment = _build_jira_comment(
                        coupon_id, 6,
                        f"Phase 6 COMPLETE — Work allocation submitted by {udisp()}.\n"
                        f"Technician: {technician.strip()} | Start: {start_date} | End: {end_date}\n"
                        f"Converging to Phase 8: Work Execution.",
                    )
                    jira_api.advance_phase(coupon["jira_ticket"], new_phase=8, comment=jira_comment)
            st.markdown(
                f'<div style="padding:22px;border:1px solid #00d4ff;background:#001520;'
                f'border-radius:2px;text-align:center;margin:16px 0">'
                f'<div style="font-size:1.3em;color:#00d4ff;letter-spacing:0.2em">✓ PHASE 6 COMPLETE</div>'
                f'<div style="color:#c0d8e0;margin-top:8px">Technician: <strong style="color:#00d4ff">{technician.strip()}</strong>'
                f' &nbsp;·&nbsp; {start_date} → {end_date}</div>'
                f'<div style="margin-top:6px">{jira_badge(coupon["jira_ticket"], "Execution")}</div>'
                f'<div style="color:#1a5060;font-size:0.83em;margin-top:10px">'
                f"Work allocation submitted. Phase 8 unlocks when phases 5 and 7 also complete.</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("↩ DASHBOARD", key="p6_done"):
                go("dashboard")


# ── KEYBOARD NAV ─────────────────────────────────────────────────────────────
def inject_keyboard_nav(current_phase: int):
    """Inject arrow-key navigation via a script in the Streamlit DOM."""
    prev_p = max(1, current_phase - 1)
    next_p = min(9, current_phase + 1)
    st.markdown(
        f"""<script>
(function() {{
  if (window.__wf_kbd) return;
  window.__wf_kbd = true;
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowRight') {{ window.location.href = '?nav={next_p}'; }}
    if (e.key === 'ArrowLeft')  {{ window.location.href = '?nav={prev_p}'; }}
  }});
}})();
</script>""",
        unsafe_allow_html=True,
    )


# ── PAGE: PHASE LOCKED (4–9) ──────────────────────────────────────────────────
def page_phase_locked():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    phase_num = st.session_state.get("nav_phase") or 7
    meta = PHASE_META[phase_num]

    # Work order context: prefer session coupon, else most recent
    if is_preview():
        coupon = PREVIEW_COUPON
    else:
        coupon = None
        if st.session_state.coupon_id:
            coupon = db.get_coupon(st.session_state.coupon_id)
        if not coupon:
            coupons = db.list_coupons()
            coupon = coupons[0] if coupons else None

    # Determine upstream completion state
    upstream_done = coupon and coupon["current_phase"] >= phase_num if coupon else False

    # Viz: show actual work order phase as current, highlight the locked phase
    work_phase = coupon["current_phase"] if coupon else 0
    st.markdown(viz.workflow_svg(current_phase=work_phase, highlight_phase=phase_num, highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    if is_preview():
        preview_banner()
    st.markdown("<br>", unsafe_allow_html=True)

    # Phase header
    status_color = "#00cc77" if upstream_done else "#ffb300"
    status_text  = "READY — AWAITING ACTIVATION" if upstream_done else "UPSTREAM PHASES IN PROGRESS"
    st.markdown(
        f'<span style="background:rgba(255,179,0,0.08);border:1px solid #ffb300;color:#ffb300;'
        f'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE {phase_num}</span>'
        f'&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">{meta["name"].upper()}</span>'
        f'<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:14px">'
        f'ROLES: {meta["roles"]}</div>',
        unsafe_allow_html=True,
    )

    # Status banner
    st.markdown(
        f'<div style="background:rgba({("0,204,119" if upstream_done else "255,179,0")},0.07);'
        f'border-left:4px solid {status_color};padding:12px 16px;border-radius:2px;margin-bottom:16px">'
        f'<span style="color:{status_color};font-size:0.88em;letter-spacing:0.08em">'
        f'{"✓" if upstream_done else "○"} &nbsp;{status_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Work order context card
    if coupon:
        p_color = priority_color(coupon["priority"])
        st.markdown(
            f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #1a4050;'
            f'padding:14px;margin-bottom:16px;border-radius:2px">'
            f'<div style="color:#00d4ff;font-size:1em">{coupon["coupon_id"]}</div>'
            f'<div style="margin-top:4px">{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}</div>'
            f'<div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;font-size:0.82em">'
            f'<div><span style="color:#1a5060">PART NO.</span><br><span style="color:#c0d8e0">{coupon["part_number"]}</span></div>'
            f'<div><span style="color:#1a5060">PRIORITY</span><br><span style="color:{p_color}">{coupon["priority"]}</span></div>'
            f'<div><span style="color:#1a5060">CURRENT PHASE</span><br><span style="color:#00aacc">Phase {coupon["current_phase"]}</span></div>'
            f'<div><span style="color:#1a5060">CREATED BY</span><br><span style="color:#c0d8e0">{coupon["created_by"]}</span></div>'
            f'</div>'
            f'<div style="margin-top:8px;font-size:0.82em"><span style="color:#1a5060">DESCRIPTION</span><br>'
            f'<span style="color:#c0d8e0">{coupon["description"]}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="color:#1a5060;font-size:0.88em;padding:12px 0">'
            'No active work orders. Submit a Phase 1 request to begin the workflow.</div>',
            unsafe_allow_html=True,
        )

    # Phase description
    phase_descriptions = {
        4: "Supply Chain creates PR/RFQ/PO for required materials and schedules fabrication resources.",
        5: "ME and Weld Engineer define work instructions, bill of process, and fab/assembly/quality procedures. QE reviews.",
        6: "IE allocates resourcing, schedules work packages, and assigns personnel to the work order.",
        7: "Materials are received by Supply Chain and Warehouse/MMO. QE performs incoming inspection.",
        8: "MECHANIC executes the work plan. ME and QE provide oversight. All upstream branches converge here.",
        9: "QE initiates Non-Conformance Report (NCR) if defects are identified during or after execution.",
    }
    if phase_num in phase_descriptions:
        st.markdown(
            f'<div style="background:#06090e;border:1px solid #0d2030;padding:12px 16px;'
            f'border-radius:2px;margin-top:8px">'
            f'<div style="color:#1a5060;font-size:0.75em;letter-spacing:0.1em;margin-bottom:4px">PHASE DESCRIPTION</div>'
            f'<div style="color:#2a6070;font-size:0.85em">{phase_descriptions[phase_num]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Advance controls for phases 7–9
    advance_roles = {
        7: {"Supply Chain", "QE", "Warehouse/MMO"},
        8: {"Mechanic", "ME", "QE"},
        9: {"QE", "ME", "Mechanic"},
    }
    next_phase_label = {7: "PHASE 8 — WORK EXECUTION", 8: "PHASE 9 — NCR", 9: None}

    if coupon and (coupon["current_phase"] == phase_num or is_preview()) and phase_num in advance_roles:
        can_advance = is_preview() or role() in advance_roles[phase_num]
        next_label = next_phase_label.get(phase_num)
        st.markdown("<br>", unsafe_allow_html=True)
        if can_advance:
            if next_label:
                if st.button(f"⟶ ADVANCE TO {next_label}", key="locked_advance"):
                    if is_preview():
                        preview_banner()
                    else:
                        if phase_num == 7:
                            db.phase_complete(coupon["coupon_id"], 7, [8])
                        else:
                            db.advance_coupon_phase(coupon["coupon_id"], phase_num + 1)
                        if coupon.get("jira_ticket"):
                            jira_comment = _build_jira_comment(
                                coupon["coupon_id"], phase_num,
                                f"Phase {phase_num} COMPLETE — advanced by {udisp()}.",
                            )
                            with st.spinner("Updating Jira…"):
                                jira_api.advance_phase(coupon["jira_ticket"], new_phase=phase_num + 1, comment=jira_comment)
                        st.session_state.nav_phase = phase_num + 1
                        st.rerun()
            else:
                if st.button("✓ CLOSE WORK ORDER", key="locked_close"):
                    if is_preview():
                        preview_banner()
                    else:
                        db.advance_coupon_phase(coupon["coupon_id"], 9)
                        if coupon.get("jira_ticket"):
                            jira_comment = _build_jira_comment(
                                coupon["coupon_id"], 9,
                                f"NCR phase complete — work order closed by {udisp()}.",
                            )
                            with st.spinner("Updating Jira…"):
                                jira_api.advance_phase(coupon["jira_ticket"], new_phase=9, comment=jira_comment)
                        go("dashboard")
        else:
            st.markdown(
                f'<div style="color:#1a5060;font-size:0.83em;padding:8px 0">'
                f'Advance requires: <span style="color:#00aacc">'
                f'{" · ".join(sorted(advance_roles[phase_num]))}</span></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    inject_keyboard_nav(phase_num)
    if st.button("← DASHBOARD", key="locked_back"):
        go("dashboard")


# ── PAGE: PHASE 7 — MATERIAL RECEIVING ───────────────────────────────────────
def page_phase7():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    coupon = get_coupon_or_preview()
    coupon_id = coupon["coupon_id"] if coupon else None
    if not coupon:
        go("dashboard")
        return

    st.markdown(viz.workflow_svg(current_phase=coupon["current_phase"], highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(7)
    st.markdown("<br>", unsafe_allow_html=True)
    if is_preview():
        preview_banner()

    st.markdown(
        '<span style="background:rgba(0,212,255,0.08);border:1px solid #00d4ff;color:#00d4ff;'
        'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE 7</span>'
        '&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">MATERIAL RECEIVING</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:14px">'
        'MULTI-ROLE SIGN-OFF REQUIRED: Supply Chain · QE · Warehouse/MMO</div>',
        unsafe_allow_html=True,
    )

    # Work order card
    st.markdown(
        f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00d4ff;'
        f'padding:14px;margin-bottom:16px;border-radius:2px">'
        f'<div style="color:#00d4ff;font-size:1.05em">{coupon_id}</div>'
        f'<div style="margin-top:4px">{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}</div>'
        f'<div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;font-size:0.82em">'
        f'<div><span style="color:#5aaccc">PART NO.</span><br><span style="color:#c0d8e0">{coupon["part_number"]}</span></div>'
        f'<div><span style="color:#5aaccc">NX MODEL</span><br><span style="color:#c0d8e0">{coupon["nx_model_ref"]}</span></div>'
        f'<div><span style="color:#5aaccc">TC ITEM</span><br><span style="color:#c0d8e0">{coupon["tc_engineering_item"]}</span></div>'
        f'<div><span style="color:#5aaccc">PRIORITY</span><br><span style="color:{priority_color(coupon["priority"])}">{coupon["priority"]}</span></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    render_phase_nav(coupon, 7)
    render_phase_history(coupon_id, coupon)
    render_comments(coupon_id)
    signoffs     = [] if is_preview() else db.get_signoffs(coupon_id, 7)
    signed_roles = {s["role"] for s in signoffs}
    required_roles = [
        ("Supply Chain",  "Supply Chain",    "Materials received per PO — quantities and part numbers verified",  "PO / Packing Slip Ref"),
        ("QE",            "Quality Engineer","Incoming inspection complete — materials conform to drawing and spec", "Inspection Record Ref"),
        ("Warehouse/MMO", "Warehouse / MMO", "Materials received into inventory and stored in designated location",  "Storage Location / Bin"),
    ]
    current_role = role() if not is_preview() else "Supply Chain"

    st.markdown("**MATERIAL RECEIVING SIGN-OFF**")

    for r_key, r_label, r_confirm_text, r_ref_label in required_roles:
        if r_key in signed_roles:
            rec = next(s for s in signoffs if s["role"] == r_key)
            doc_ref = rec["notes"] or "—"
            st.markdown(
                f'<div style="background:rgba(0,160,80,0.08);border-left:3px solid #00b464;'
                f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                f'<span style="color:#00cc77">✓ {r_label}</span>'
                f'<span style="color:#1a5060;font-size:0.78em;margin-left:12px">'
                f'Signed by {rec["display_name"]} · {rec["signed_at"][:16]}</span>'
                f'<span style="color:#1a5060;font-size:0.78em;display:block;margin-top:2px">'
                f'{r_ref_label}: <span style="color:#00aacc">{doc_ref}</span></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            if current_role == r_key:
                st.markdown(
                    f'<div style="background:rgba(0,212,255,0.04);border-left:3px solid #00d4ff;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                    f'<span style="color:#00d4ff">⟶ Your sign-off required: {r_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                doc_ref_val = st.text_input(
                    f"{r_ref_label}", key=f"p7_ref_{r_key}",
                    placeholder=f"e.g. {'PO-2026-0042' if r_key=='Supply Chain' else 'INS-'+coupon_id+'-001' if r_key=='QE' else 'BIN-A4-07'}",
                )
                st.text_area("Comment (optional)", key=f"p7_cmt_{r_key}", height=60, placeholder="Add context for downstream phases…", label_visibility="visible")
                if st.button(f"✓ CONFIRM — {r_confirm_text[:45]}…", key=f"p7_sign_{r_key}"):
                    if is_preview():
                        preview_banner()
                    else:
                        db.add_signoff(coupon_id, 7, r_key, uname(), udisp(), notes=doc_ref_val)
                        db.add_phase_comment(coupon_id, 7, "signoff", uname(), udisp(), st.session_state.get(f"p7_cmt_{r_key}", ""))
                        st.rerun()
            else:
                hint = ""
                if current_role not in {k for k, *_ in required_roles}:
                    hint = " &nbsp;<span style='color:#1a3040;font-size:0.75em'>(log in as supply_chain / qe_user / warehouse)</span>"
                st.markdown(
                    f'<div style="background:rgba(255,196,0,0.05);border-left:3px solid #7a5800;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#c8960a">'
                    f"○ {r_label} — awaiting sign-off{hint}</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)
    signed_count = len(signed_roles & {k for k, *_ in required_roles})
    st.progress(signed_count / 3, text=f"SIGN-OFF PROGRESS: {signed_count} / 3")

    if (not is_preview() and db.phase7_complete(coupon_id)) or is_preview():
        st.markdown(
            '<div style="padding:16px;border:1px solid #00d4ff;background:#001520;'
            'text-align:center;margin-top:14px;border-radius:2px">'
            '<div style="color:#00d4ff;letter-spacing:0.1em">✓ ALL ROLES CONFIRMED — PHASE 7 COMPLETE</div>'
            '<div style="color:#1a5060;font-size:0.82em;margin-top:4px">'
            'Ready to advance to Phase 8 · Supply Chain must proceed.</div></div>',
            unsafe_allow_html=True,
        )
        if current_role == "Supply Chain" or is_preview():
            st.markdown("<br>", unsafe_allow_html=True)
            adv_comment_p7 = st.text_area("Advance Comment (optional)", key="p7_adv_cmt", height=60, placeholder="Notes for Phase 8 / Work Execution…", label_visibility="visible")
            if st.button("⟶ ADVANCE TO PHASE 8 — WORK EXECUTION", key="p7_advance"):
                if is_preview():
                    preview_banner()
                else:
                    db.add_phase_comment(coupon_id, 7, "advance", uname(), udisp(), adv_comment_p7)
                    db.phase_complete(coupon_id, 7, [8])
                    if coupon.get("jira_ticket"):
                        sigs = db.get_signoffs(coupon_id, 7)
                        names = ", ".join(s["display_name"] for s in sigs)
                        jira_comment = _build_jira_comment(
                            coupon_id, 7,
                            f"Phase 7 COMPLETE — Materials confirmed by: {names}. Converging to Phase 8: Work Execution.",
                        )
                        with st.spinner("Updating Jira…"):
                            jira_api.advance_phase(coupon["jira_ticket"], new_phase=8, comment=jira_comment)
                    go("dashboard")
        else:
            st.markdown(
                '<div style="color:#1a5060;font-size:0.8em;margin-top:8px">'
                "Log in as <strong style='color:#00aacc'>supply_chain</strong> to advance.</div>",
                unsafe_allow_html=True,
            )

    

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← DASHBOARD", key="p7_back"):
        go("dashboard")


# ── PAGE: PHASE 8 — WORK EXECUTION ────────────────────────────────────────────
def page_phase8():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    coupon = get_coupon_or_preview()
    coupon_id = coupon["coupon_id"] if coupon else None
    if not coupon:
        go("dashboard")
        return

    st.markdown(viz.workflow_svg(current_phase=coupon["current_phase"], highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(8)
    st.markdown("<br>", unsafe_allow_html=True)
    if is_preview():
        preview_banner()

    st.markdown(
        '<span style="background:rgba(0,212,255,0.12);border:2px solid #00f5ff;color:#00f5ff;'
        'padding:4px 14px;font-size:0.88em;letter-spacing:0.15em;'
        'text-shadow:0 0 10px rgba(0,245,255,0.6)">PHASE 8</span>'
        '&nbsp;&nbsp;<span style="color:#ffffff;letter-spacing:0.15em;font-size:1.05em;'
        'text-shadow:0 0 8px rgba(0,245,255,0.4)">WORK EXECUTION</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:6px">'
        'ALL UPSTREAM BRANCHES CONVERGE HERE</div>'
        '<div style="color:#1a5060;font-size:0.78em;margin-bottom:14px">'
        'MULTI-ROLE SIGN-OFF REQUIRED: <span style="color:#00d4ff">Mechanic</span> · ME · QE</div>',
        unsafe_allow_html=True,
    )

    # Work order card
    st.markdown(
        f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00f5ff;'
        f'padding:14px;margin-bottom:16px;border-radius:2px">'
        f'<div style="color:#00f5ff;font-size:1.05em">{coupon_id}'
        f'<span style="color:#1a5060;font-size:0.72em;margin-left:12px">MECHANIC CONVERGENCE NODE</span></div>'
        f'<div style="margin-top:4px">{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}</div>'
        f'<div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;font-size:0.82em">'
        f'<div><span style="color:#5aaccc">PART NO.</span><br><span style="color:#c0d8e0">{coupon["part_number"]}</span></div>'
        f'<div><span style="color:#5aaccc">NX MODEL</span><br><span style="color:#c0d8e0">{coupon["nx_model_ref"]}</span></div>'
        f'<div><span style="color:#5aaccc">TC ITEM</span><br><span style="color:#c0d8e0">{coupon["tc_engineering_item"]}</span></div>'
        f'<div><span style="color:#5aaccc">PRIORITY</span><br><span style="color:{priority_color(coupon["priority"])}">{coupon["priority"]}</span></div>'
        f'</div>'
        f'<div style="margin-top:8px;font-size:0.82em"><span style="color:#5aaccc">DESCRIPTION</span><br>'
        f'<span style="color:#c0d8e0">{coupon["description"]}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    render_phase_nav(coupon, 8)
    render_phase_history(coupon_id, coupon)
    render_comments(coupon_id)
    signoffs     = [] if is_preview() else db.get_signoffs(coupon_id, 8)
    signed_roles = {s["role"] for s in signoffs}
    required_roles = [
        ("Mechanic", "Mechanic (Mfg Tech)", "Work plan executed per work instructions — redlines documented if any", "Work Completion Notes / Redline Ref"),
        ("ME",       "Manufacturing Engineer", "Manufacturing oversight complete — work instructions followed",         "ME Sign-Off Notes"),
        ("QE",       "Quality Engineer",    "In-process and final inspection complete — work conforms to quality req", "Inspection Record / QC Ref"),
    ]
    current_role = role() if not is_preview() else "Mechanic"

    st.markdown("**EXECUTION SIGN-OFF**")

    for r_key, r_label, r_confirm_text, r_ref_label in required_roles:
        is_mechanic = r_key == "Mechanic"
        border_color = "#00f5ff" if is_mechanic else "#00d4ff"
        if r_key in signed_roles:
            rec = next(s for s in signoffs if s["role"] == r_key)
            doc_ref = rec["notes"] or "—"
            st.markdown(
                f'<div style="background:rgba(0,160,80,0.08);border-left:3px solid #00b464;'
                f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                f'<span style="color:#00cc77">✓ {r_label}</span>'
                f'<span style="color:#1a5060;font-size:0.78em;margin-left:12px">'
                f'Signed by {rec["display_name"]} · {rec["signed_at"][:16]}</span>'
                f'<span style="color:#1a5060;font-size:0.78em;display:block;margin-top:2px">'
                f'{r_ref_label}: <span style="color:#00aacc">{doc_ref}</span></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            if current_role == r_key:
                st.markdown(
                    f'<div style="background:rgba(0,212,255,0.04);border-left:3px solid {border_color};'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                    f'<span style="color:{border_color}">⟶ Your sign-off required: {r_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                doc_ref_val = st.text_area(
                    f"{r_ref_label}", key=f"p8_ref_{r_key}", height=70,
                    placeholder=f"e.g. {'Work complete, no redlines. All dims within tolerance.' if is_mechanic else 'WI followed per WI-'+coupon_id+'-001' if r_key=='ME' else 'QC-'+coupon_id+'-FINAL passed all checks'}",
                )
                st.text_area("Comment (optional)", key=f"p8_cmt_{r_key}", height=60, placeholder="Add context for downstream phases…", label_visibility="visible")
                btn_label = f"⚙ CONFIRM EXECUTION — {r_label.upper()}" if is_mechanic else f"✓ CONFIRM — {r_label.upper()}"
                if st.button(btn_label, key=f"p8_sign_{r_key}"):
                    if is_preview():
                        preview_banner()
                    else:
                        db.add_signoff(coupon_id, 8, r_key, uname(), udisp(), notes=doc_ref_val)
                        db.add_phase_comment(coupon_id, 8, "signoff", uname(), udisp(), st.session_state.get(f"p8_cmt_{r_key}", ""))
                        st.rerun()
            else:
                hint = ""
                if current_role not in {k for k, *_ in required_roles}:
                    hint = " &nbsp;<span style='color:#1a3040;font-size:0.75em'>(log in as mechanic / me_user / qe_user)</span>"
                st.markdown(
                    f'<div style="background:rgba(255,196,0,0.05);border-left:3px solid #7a5800;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#c8960a">'
                    f"○ {r_label} — awaiting sign-off{hint}</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)
    signed_count = len(signed_roles & {k for k, *_ in required_roles})
    st.progress(signed_count / 3, text=f"EXECUTION SIGN-OFF PROGRESS: {signed_count} / 3")

    if (not is_preview() and db.phase8_complete(coupon_id)) or is_preview():
        st.markdown(
            '<div style="padding:16px;border:2px solid #00f5ff;background:#001520;'
            'text-align:center;margin-top:14px;border-radius:2px;'
            'box-shadow:0 0 20px rgba(0,245,255,0.2)">'
            '<div style="color:#00f5ff;letter-spacing:0.15em;font-size:1.05em">⚙ EXECUTION COMPLETE — ALL ROLES CONFIRMED</div>'
            '<div style="color:#1a5060;font-size:0.82em;margin-top:4px">'
            'Ready to advance to Phase 9 · Mechanic or ME must proceed.</div></div>',
            unsafe_allow_html=True,
        )
        if current_role in ("Mechanic", "ME") or is_preview():
            st.markdown("<br>", unsafe_allow_html=True)
            adv_comment_p8 = st.text_area("Advance Comment (optional)", key="p8_adv_cmt", height=60, placeholder="Notes for Phase 9 / NCR Assessment…", label_visibility="visible")
            if st.button("⟶ ADVANCE TO PHASE 9 — NON-CONFORMANCE (NCR)", key="p8_advance"):
                if is_preview():
                    preview_banner()
                else:
                    db.add_phase_comment(coupon_id, 8, "advance", uname(), udisp(), adv_comment_p8)
                    db.advance_coupon_phase(coupon_id, 9)
                    if coupon.get("jira_ticket"):
                        sigs = db.get_signoffs(coupon_id, 8)
                        names = ", ".join(s["display_name"] for s in sigs)
                        jira_comment = _build_jira_comment(
                            coupon_id, 8,
                            f"Phase 8 COMPLETE — Work execution confirmed by: {names}. Advancing to Phase 9: NCR review.",
                        )
                        with st.spinner("Updating Jira…"):
                            jira_api.advance_phase(coupon["jira_ticket"], new_phase=9, comment=jira_comment)
                    go("phase9", coupon_id)
        else:
            st.markdown(
                '<div style="color:#1a5060;font-size:0.8em;margin-top:8px">'
                "Log in as <strong style='color:#00aacc'>mechanic</strong> or <strong style='color:#00aacc'>me_user</strong> to advance.</div>",
                unsafe_allow_html=True,
            )

    

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← DASHBOARD", key="p8_back"):
        go("dashboard")


# ── PAGE: PHASE 9 — NON-CONFORMANCE (NCR) ─────────────────────────────────────
def page_phase9():
    st.markdown(CSS, unsafe_allow_html=True)
    header()

    coupon = get_coupon_or_preview()
    coupon_id = coupon["coupon_id"] if coupon else None
    if not coupon:
        go("dashboard")
        return

    st.markdown(viz.workflow_svg(current_phase=coupon["current_phase"], highlight_all=is_preview(), clickable=not is_preview()), unsafe_allow_html=True)
    inject_keyboard_nav(9)
    st.markdown("<br>", unsafe_allow_html=True)
    if is_preview():
        preview_banner()

    st.markdown(
        '<span style="background:rgba(0,212,255,0.08);border:1px solid #00d4ff;color:#00d4ff;'
        'padding:4px 12px;font-size:0.82em;letter-spacing:0.1em">PHASE 9</span>'
        '&nbsp;&nbsp;<span style="color:#c0d8e0;letter-spacing:0.1em">NON-CONFORMANCE (NCR) REVIEW &amp; CLOSE</span>'
        '<div style="color:#1a5060;font-size:0.78em;margin-top:4px;margin-bottom:14px">'
        'ROLES: QE · ME · Mechanic — QE initiates NCR assessment; all roles confirm disposition</div>',
        unsafe_allow_html=True,
    )

    # Work order card
    st.markdown(
        f'<div style="background:#0a1520;border:1px solid #1a4050;border-left:3px solid #00d4ff;'
        f'padding:12px 14px;margin-bottom:14px;border-radius:2px;font-size:0.85em">'
        f'<span style="color:#00d4ff">{coupon_id}</span>'
        f'&nbsp;&nbsp;{jira_badge(coupon["jira_ticket"], coupon["jira_status"])}'
        f'&nbsp;&nbsp;<span style="color:#5aaccc">{coupon["part_number"]}</span>'
        f'&nbsp;&nbsp;<span style="color:{priority_color(coupon["priority"])}">{coupon["priority"]}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    render_phase_nav(coupon, 9)
    render_phase_history(coupon_id, coupon)
    render_comments(coupon_id)

    signoffs     = [] if is_preview() else db.get_signoffs(coupon_id, 9)
    signed_roles = {s["role"] for s in signoffs}
    current_role = role() if not is_preview() else "QE"

    # ── QE: NCR INITIATION (sign-off with structured notes) ───────────────────
    st.markdown("**NCR ASSESSMENT**")
    qe_signed = "QE" in signed_roles

    if qe_signed:
        rec = next(s for s in signoffs if s["role"] == "QE")
        st.markdown(
            f'<div style="background:rgba(0,160,80,0.08);border-left:3px solid #00b464;'
            f'padding:10px 14px;margin:5px 0;border-radius:2px">'
            f'<span style="color:#00cc77">✓ QE Assessment Complete</span>'
            f'<span style="color:#1a5060;font-size:0.78em;margin-left:12px">'
            f'By {rec["display_name"]} · {rec["signed_at"][:16]}</span>'
            f'<span style="color:#1a5060;font-size:0.78em;display:block;margin-top:2px">'
            f'Assessment: <span style="color:#00aacc">{rec["notes"] or "—"}</span></span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        if current_role == "QE":
            st.markdown(
                '<div style="background:rgba(0,212,255,0.04);border-left:3px solid #00d4ff;'
                'padding:10px 14px;margin:5px 0;border-radius:2px">'
                '<span style="color:#00d4ff">⟶ QE: Initiate NCR assessment</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            ncr_required = st.checkbox("Non-conformance identified — NCR required", key="p9_ncr_flag")
            if ncr_required:
                col1, col2 = st.columns(2)
                with col1:
                    ncr_number = st.text_input("NCR Number", key="p9_ncr_num", placeholder="e.g. NCR-2026-0042")
                    ncr_disposition = st.selectbox("Disposition", ["Use As Is", "Rework", "Repair", "Return to Vendor", "Scrap"], key="p9_disp")
                with col2:
                    ncr_desc = st.text_area("Non-Conformance Description", key="p9_ncr_desc", height=80,
                                            placeholder="Describe the non-conformance, location, and extent…")
                assessment_notes = f"NCR REQUIRED · {ncr_number or 'TBD'} · Disposition: {ncr_disposition} · {ncr_desc}"
            else:
                assessment_notes = "NO NCR — Work conforms to all requirements. Cleared for closure."

            p9_qe_comment = st.text_area("Comment (optional)", key="p9_qe_cmt", height=60, placeholder="Additional context for disposition review…", label_visibility="visible")
            if st.button("✓ SUBMIT NCR ASSESSMENT", key="p9_qe_sign"):
                if is_preview():
                    preview_banner()
                else:
                    db.add_signoff(coupon_id, 9, "QE", uname(), udisp(), notes=assessment_notes)
                    db.add_phase_comment(coupon_id, 9, "signoff", uname(), udisp(), p9_qe_comment)
                    st.rerun()
        else:
            hint = "" if current_role in ("ME", "Mechanic") else " &nbsp;<span style='color:#1a3040;font-size:0.75em'>(log in as qe_user)</span>"
            st.markdown(
                f'<div style="background:rgba(255,179,0,0.03);border-left:3px solid #1a2000;'
                f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#3a3010">'
                f"○ QE Assessment — awaiting{hint}</div>",
                unsafe_allow_html=True,
            )

    # ── ME and MECHANIC: DISPOSITION CONFIRMATION ──────────────────────────────
    if qe_signed or is_preview():
        st.markdown("**DISPOSITION CONFIRMATION**")
        for r_key, r_label in [("ME", "Manufacturing Engineer"), ("Mechanic", "Mechanic (Mfg Tech)")]:
            if r_key in signed_roles:
                rec = next(s for s in signoffs if s["role"] == r_key)
                st.markdown(
                    f'<div style="background:rgba(0,160,80,0.08);border-left:3px solid #00b464;'
                    f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                    f'<span style="color:#00cc77">✓ {r_label}</span>'
                    f'<span style="color:#1a5060;font-size:0.78em;margin-left:12px">'
                    f'Signed by {rec["display_name"]} · {rec["signed_at"][:16]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                if current_role == r_key:
                    st.markdown(
                        f'<div style="background:rgba(0,212,255,0.04);border-left:3px solid #00d4ff;'
                        f'padding:10px 14px;margin:5px 0;border-radius:2px">'
                        f'<span style="color:#00d4ff">⟶ Your confirmation required: {r_label}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.text_area("Comment (optional)", key=f"p9_cmt_{r_key}", height=60, placeholder="Disposition notes…", label_visibility="visible")
                    if st.button(f"✓ CONFIRM DISPOSITION — {r_label.upper()}", key=f"p9_sign_{r_key}"):
                        if is_preview():
                            preview_banner()
                        else:
                            db.add_signoff(coupon_id, 9, r_key, uname(), udisp())
                            db.add_phase_comment(coupon_id, 9, "signoff", uname(), udisp(), st.session_state.get(f"p9_cmt_{r_key}", ""))
                            st.rerun()
                else:
                    hint = "" if current_role in {"QE", "ME", "Mechanic"} else f" &nbsp;<span style='color:#1a3040;font-size:0.75em'>(log in as me_user / mechanic)</span>"
                    st.markdown(
                        f'<div style="background:rgba(255,179,0,0.03);border-left:3px solid #1a2000;'
                        f'padding:10px 14px;margin:5px 0;border-radius:2px;color:#3a3010">'
                        f"○ {r_label} — awaiting disposition confirmation{hint}</div>",
                        unsafe_allow_html=True,
                    )

    st.markdown("<br>", unsafe_allow_html=True)
    signed_count = len(signed_roles & {"QE", "ME", "Mechanic"})
    st.progress(signed_count / 3, text=f"DISPOSITION SIGN-OFF: {signed_count} / 3")

    if (not is_preview() and db.phase9_complete(coupon_id)) or is_preview():
        st.markdown(
            '<div style="padding:20px;border:1px solid #00d4ff;background:#001520;'
            'text-align:center;margin-top:14px;border-radius:2px">'
            '<div style="color:#00d4ff;letter-spacing:0.15em;font-size:1.1em">✓ NCR REVIEW COMPLETE — READY TO CLOSE</div>'
            '<div style="color:#1a5060;font-size:0.82em;margin-top:4px">'
            'All roles confirmed disposition. QE must close the work order.</div></div>',
            unsafe_allow_html=True,
        )
        if current_role == "QE" or is_preview():
            st.markdown("<br>", unsafe_allow_html=True)
            p9_close_comment = st.text_area("Closing Comment (optional)", key="p9_close_cmt", height=60, placeholder="Final notes for the work order record…", label_visibility="visible")
            if st.button("✓ CLOSE WORK ORDER", key="p9_close"):
                if is_preview():
                    preview_banner()
                else:
                    db.add_phase_comment(coupon_id, 9, "close", uname(), udisp(), p9_close_comment)
                    # ── DB: stamp closed_at, closed_by, jira_status=Closed ──
                    db.close_work_order(coupon_id, uname())

                    # ── JIRA: label → phase-9-ncr, comment, transition → Done ──
                    jira_ok = {"label_ok": True, "comment_ok": True, "transition_ok": True}
                    if coupon.get("jira_ticket"):
                        jira_comment = _build_jira_comment(
                            coupon_id, 9,
                            f"Work order CLOSED — Phase 9 NCR review complete.\nClosed by: {udisp()} ({uname()})",
                        )
                        with st.spinner("Closing Jira ticket…"):
                            jira_ok = jira_api.close_issue(coupon["jira_ticket"], comment=jira_comment)

                    # ── RESULT BANNER ──────────────────────────────────────────
                    if coupon.get("jira_ticket"):
                        jira_status_html = (
                            f'<div style="margin-top:8px">{jira_badge(coupon["jira_ticket"], "Done ✓")}</div>'
                            if jira_ok["transition_ok"] else
                            f'<div style="color:#ffb300;font-size:0.8em;margin-top:8px">'
                            f'⚠ Jira Done transition failed — label &amp; comment still updated. '
                            f'Manually close: {coupon["jira_ticket"]}</div>'
                        )
                    else:
                        jira_status_html = '<div style="color:#1a5060;font-size:0.8em;margin-top:6px">No Jira ticket linked.</div>'

                    st.markdown(
                        f'<div style="padding:24px;border:1px solid #00d4ff;background:#001520;'
                        f'border-radius:2px;text-align:center;margin:16px 0">'
                        f'<div style="font-size:1.4em;color:#00d4ff;letter-spacing:0.2em">✓ WORK ORDER CLOSED</div>'
                        f'<div style="color:#c0d8e0;margin-top:8px">Work Order: <strong style="color:#00d4ff">{coupon_id}</strong></div>'
                        f'{jira_status_html}'
                        f'<div style="color:#1a5060;font-size:0.82em;margin-top:10px">Closed by {udisp()} · {coupon["part_number"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button("↩ DASHBOARD", key="p9_done"):
                        go("dashboard")
        else:
            st.markdown(
                '<div style="color:#1a5060;font-size:0.8em;margin-top:8px">'
                "Log in as <strong style='color:#00aacc'>qe_user</strong> to close.</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← DASHBOARD", key="p9_back"):
        go("dashboard")


# ── ROUTER ────────────────────────────────────────────────────────────────────
_PAGE_MAP = {
    "dashboard":    page_dashboard,
    "phase1":       page_phase1,
    "phase2":       page_phase2,
    "phase3":       page_phase3,
    "phase4":       page_phase4,
    "phase5":       page_phase5,
    "phase6":       page_phase6,
    "phase7":       page_phase7,
    "phase8":       page_phase8,
    "phase9":       page_phase9,
    "phase_locked": page_phase_locked,
}

_current_mode = st.session_state.get("mode")
if _current_mode is None:
    page_mode_select()
elif _current_mode == "preview":
    _PAGE_MAP.get(st.session_state.page, page_dashboard)()
else:  # demo mode
    if not st.session_state.auth:
        page_login()
    else:
        _PAGE_MAP.get(st.session_state.page, page_dashboard)()
