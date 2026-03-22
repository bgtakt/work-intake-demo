"""Tron-style SVG workflow diagram for the 9-phase coupon fab process."""

# Node layout: (cx, cy, w, h, phase_label, sub_label)
_NODES = {
    1: (48,  120, 72, 44, "PHASE 1", "Initiate"),
    2: (160, 120, 72, 44, "PHASE 2", "Align"),
    3: (272, 120, 72, 44, "PHASE 3", "Design"),
    4: (384, 60,  72, 44, "PHASE 4", "Procure"),
    5: (384, 120, 72, 44, "PHASE 5", "Work Inst"),
    6: (384, 180, 72, 44, "PHASE 6", "Resource"),
    7: (496, 60,  72, 44, "PHASE 7", "Receiving"),
    8: (614, 120, 84, 54, "PHASE 8", "EXECUTE"),   # MECHANIC convergence
    9: (737, 120, 72, 44, "PHASE 9", "NCR"),
}

_COLORS = {
    "completed":       dict(fill="#003d55", stroke="#00d4ff", text="#00f5ff"),
    "active":          dict(fill="#002840", stroke="#00f5ff", text="#ffffff"),
    "locked":          dict(fill="#0a1520", stroke="#1e4a62", text="#2e6e80"),
    "selected_locked": dict(fill="#1a1000", stroke="#ffc400", text="#ffc400"),  # amber = highlighted but not active
    "none":            dict(fill="#0a1520", stroke="#1e4a62", text="#3a7a8a"),
}


def _state(n: int, current: int, highlight: int = 0, highlight_all: bool = False) -> str:
    if highlight_all:
        return "completed"
    if current == 0:
        return "none"
    if n < current:
        return "completed"
    if n == current:
        return "active"
    if highlight and n == highlight:
        return "selected_locked"
    return "locked"


def _re(n):  # right edge center
    cx, cy, w, h, *_ = _NODES[n]
    return cx + w // 2, cy

def _le(n):  # left edge center
    cx, cy, w, h, *_ = _NODES[n]
    return cx - w // 2, cy


def workflow_svg(current_phase: int = 0, highlight_phase: int = 0, highlight_all: bool = False,
                 phase_counts: dict = None, click_prefix: str = "nav", clickable: bool = True) -> str:
    """
    Return an SVG string for the 9-phase Tron workflow diagram.
    current_phase : the phase the work order is actually at (drives completed/active states)
    highlight_phase: an additional phase to visually select (amber, for locked-page context)
    highlight_all : render all nodes as completed/lit to showcase the full process
    phase_counts  : dict of {phase: count} to show work-order count badges on each node
    click_prefix  : query param name used in node onclick (default "nav"; use "pdialog" for dialog mode)
    clickable     : if False, nodes show default cursor and have no onclick (use in preview mode)
    """
    phase_counts = phase_counts or {}
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 790 240" '
        'id="wf-svg" '
        'style="width:100%;max-width:820px;background:#163248;border-radius:3px;'
        'border:1px solid #2a8ab0;display:block;margin:0 auto">',

        "<defs>",
        "<style>",
        f"  .wf-node {{ cursor:{'pointer' if clickable else 'default'}; }}",
        "  .wf-node:hover { opacity:1 !important; }",
        "  .wf-label { pointer-events:none; }",
        "</style>",
        '<filter id="glow" x="-60%" y="-60%" width="220%" height="220%">',
        '  <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="b"/>',
        '  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>',
        "</filter>",
        '<filter id="glow2" x="-60%" y="-60%" width="220%" height="220%">',
        '  <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="b"/>',
        '  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>',
        "</filter>",
        '<marker id="arr" markerWidth="7" markerHeight="5" refX="7" refY="2.5" orient="auto">',
        '  <polygon points="0 0,7 2.5,0 5" fill="#00d4ff"/>',
        "</marker>",
        '<marker id="arr-dim" markerWidth="7" markerHeight="5" refX="7" refY="2.5" orient="auto">',
        '  <polygon points="0 0,7 2.5,0 5" fill="#1e4060"/>',
        "</marker>",
        "</defs>",

        # Subtle grid
        '<g opacity="0.14">',
    ]
    for y in range(0, 241, 20):
        parts.append(f'<line x1="0" y1="{y}" x2="790" y2="{y}" stroke="#00d4ff" stroke-width="0.4"/>')
    parts.append("</g>")

    # Arrows
    arrows = [
        (1, 2, "S"), (2, 3, "S"),
        (3, 4, "CU"), (3, 5, "S"), (3, 6, "CD"),
        (4, 7, "S"),
        (7, 8, "CD"), (5, 8, "S"), (6, 8, "CU"),
        (8, 9, "S"),
    ]
    for frm, to, atype in arrows:
        s = _state(frm, current_phase, highlight_phase, highlight_all)
        active_arrow = s in ("completed", "active")
        color  = "#00d4ff" if active_arrow else "#1e4060"
        marker = "url(#arr)" if active_arrow else "url(#arr-dim)"
        opacity = "1.0" if active_arrow else "0.5"
        attrs = f'fill="none" stroke="{color}" stroke-width="2" opacity="{opacity}" marker-end="{marker}"'

        x1, y1 = _re(frm)
        x2, y2 = _le(to)

        if atype == "S":
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {attrs}/>')
        else:
            parts.append(f'<path d="M{x1},{y1} C{x1+22},{y1} {x2-22},{y2} {x2},{y2}" {attrs}/>')

    # Nodes
    for n, (cx, cy, w, h, lbl, sub) in _NODES.items():
        s = _state(n, current_phase, highlight_phase, highlight_all)
        c = _COLORS[s]
        x, y = cx - w // 2, cy - h // 2
        sw  = "3" if s in ("active", "selected_locked") else "1.5"
        flt = 'filter="url(#glow2)"' if s == "active" else ('filter="url(#glow)"' if s in ("completed", "selected_locked") else "")
        op  = "1" if s in ("active", "completed", "selected_locked") else "0.7"

        # Clickable rect (onclick omitted when not clickable)
        onclick = f'onclick="window.location.href=\'?{click_prefix}={n}\'"' if clickable else ''
        parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" class="wf-node" '
            f'fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="{sw}" '
            f'opacity="{op}" {flt} {onclick}/>'
        )
        # Phase label (non-interactive)
        parts.append(
            f'<text x="{cx}" y="{cy - 7}" text-anchor="middle" class="wf-label" '
            f'font-family="\'Share Tech Mono\',\'Courier New\',monospace" '
            f'font-size="8.5" fill="{c["text"]}" opacity="0.9">{lbl}</text>'
        )
        # Sub label
        fw = "bold" if n == 8 else "normal"
        fs = "10" if n == 8 else "9"
        parts.append(
            f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" class="wf-label" '
            f'font-family="\'Share Tech Mono\',\'Courier New\',monospace" '
            f'font-size="{fs}" font-weight="{fw}" fill="{c["text"]}">{sub}</text>'
        )

        # Pulsing dot on active node
        if s == "active":
            parts.append(
                f'<circle cx="{x + w - 7}" cy="{y + 7}" r="4" fill="#00f5ff" filter="url(#glow2)">'
                f'<animate attributeName="opacity" values="1;0.1;1" dur="1.4s" repeatCount="indefinite"/>'
                f"</circle>"
            )
        # Amber dot on selected-locked node
        if s == "selected_locked":
            parts.append(
                f'<circle cx="{x + w - 7}" cy="{y + 7}" r="3" fill="#ffc400" filter="url(#glow)"/>'
            )

        # Work-order count badge (bottom-right corner of node)
        if phase_counts is not None:
            count = phase_counts.get(n, 0)
            bx = x + w - 8
            by = y + h - 8
            if count > 0:
                parts.append(
                    f'<circle cx="{bx}" cy="{by}" r="8" fill="#00d4ff" opacity="0.92" filter="url(#glow)"/>'
                )
                parts.append(
                    f'<text x="{bx}" y="{by + 4}" text-anchor="middle" '
                    f'font-family="\'Share Tech Mono\',\'Courier New\',monospace" '
                    f'font-size="8" font-weight="bold" fill="#05111e">{count}</text>'
                )

    parts.append("</svg>")
    return "\n".join(parts)
