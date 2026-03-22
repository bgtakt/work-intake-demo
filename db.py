import sqlite3
import os
import random
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "coupon_fab.db")

SEED_USERS = [
    ("stakeholder",  "demo", "Stakeholder",   "Alex Torres"),
    ("de_user",      "demo", "DE",             "Jordan Lee"),
    ("me_user",      "demo", "ME",             "Sam Rivera"),
    ("weld_eng",     "demo", "Weld Engineer",  "Casey Kim"),
    ("supply_chain", "demo", "Supply Chain",   "Morgan Chen"),
    ("ie_user",      "demo", "IE",             "Riley Adams"),
    ("qe_user",      "demo", "QE",             "Drew Patel"),
    ("warehouse",    "demo", "Warehouse/MMO",  "Quinn Nguyen"),
    ("mechanic",     "demo", "Mechanic",       "Chris Martinez"),
]

PHASE2_REQUIRED = {"DE", "ME", "Weld Engineer"}
PHASE5_REQUIRED = {"ME", "Weld Engineer", "QE"}
PHASE7_REQUIRED = {"Supply Chain", "QE", "Warehouse/MMO"}
PHASE8_REQUIRED = {"Mechanic", "ME", "QE"}
PHASE9_REQUIRED = {"QE", "ME", "Mechanic"}

JIRA_STATUSES = {
    1: "New Request",
    2: "In Design",
    3: "Eng. Definition",
    4: "Procurement",
    5: "Instructions",
    6: "Resourcing",
    7: "Receiving",
    8: "Execution",
    9: "Closed",
}


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    UNIQUE NOT NULL,
            password     TEXT    NOT NULL,
            role         TEXT    NOT NULL,
            display_name TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS coupons (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_id             TEXT UNIQUE NOT NULL,
            jira_ticket           TEXT,
            part_number           TEXT,
            description           TEXT,
            priority              TEXT DEFAULT 'Medium',
            requesting_stakeholder TEXT,
            nx_model_ref          TEXT,
            tc_engineering_item   TEXT,
            notes                 TEXT,
            current_phase         INTEGER DEFAULT 1,
            jira_status           TEXT DEFAULT 'New Request',
            created_at            TEXT DEFAULT (datetime('now')),
            created_by            TEXT,
            p1_submitted_at       TEXT,
            p1_submitted_by       TEXT,
            p2_completed_at       TEXT,
            p3_tc_ebom            TEXT,
            p3_completed_at       TEXT,
            p3_completed_by       TEXT,
            closed_at             TEXT,
            closed_by             TEXT
        );

        CREATE TABLE IF NOT EXISTS phase_signoffs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_id    TEXT NOT NULL,
            phase        INTEGER NOT NULL,
            role         TEXT NOT NULL,
            signed_by    TEXT NOT NULL,
            display_name TEXT NOT NULL,
            notes        TEXT DEFAULT '',
            signed_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(coupon_id, phase, role)
        );

        CREATE TABLE IF NOT EXISTS phase_submissions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_id    TEXT NOT NULL,
            phase        INTEGER NOT NULL,
            submitted_by TEXT NOT NULL,
            submitted_at TEXT DEFAULT (datetime('now')),
            data_json    TEXT NOT NULL DEFAULT '{}',
            UNIQUE(coupon_id, phase)
        );

        CREATE TABLE IF NOT EXISTS phase_comments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_id    TEXT NOT NULL,
            phase        INTEGER NOT NULL,
            action       TEXT NOT NULL,
            posted_by    TEXT NOT NULL,
            display_name TEXT NOT NULL,
            posted_at    TEXT DEFAULT (datetime('now')),
            comment      TEXT NOT NULL DEFAULT ''
        );
    """)
    # Migrate existing DBs: add columns if absent
    for col, col_type in [("closed_at", "TEXT"), ("closed_by", "TEXT"),
                          ("active_phases", "TEXT"), ("completed_phases", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE coupons ADD COLUMN {col} {col_type}")
            conn.commit()
        except Exception:
            pass  # column already exists

    # Migrate existing DBs: create phase_comments table if absent
    conn.execute("""
        CREATE TABLE IF NOT EXISTS phase_comments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            coupon_id    TEXT NOT NULL,
            phase        INTEGER NOT NULL,
            action       TEXT NOT NULL,
            posted_by    TEXT NOT NULL,
            display_name TEXT NOT NULL,
            posted_at    TEXT DEFAULT (datetime('now')),
            comment      TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()

    for username, password, role, display_name in SEED_USERS:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password, role, display_name) VALUES (?,?,?,?)",
            (username, password, role, display_name),
        )
    conn.commit()
    conn.close()


def authenticate(username: str, password: str):
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?", (username, password)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def generate_coupon_id() -> str:
    return f"CPN-{datetime.now().strftime('%Y%m%d')}-{random.randint(100, 999)}"


def create_coupon(data: dict, created_by: str, coupon_id: str = "", jira_ticket: str = ""):
    if not coupon_id:
        coupon_id = generate_coupon_id()
    conn = _conn()
    conn.execute(
        """INSERT INTO coupons (
            coupon_id, jira_ticket, part_number, description, priority,
            requesting_stakeholder, nx_model_ref, tc_engineering_item, notes,
            current_phase, jira_status, created_by, p1_submitted_at, p1_submitted_by
        ) VALUES (?,?,?,?,?,?,?,?,?,2,'In Design',?,datetime('now'),?)""",
        (
            coupon_id, jira_ticket,
            data["part_number"], data["description"], data["priority"],
            data["requesting_stakeholder"], data["nx_model_ref"],
            data["tc_engineering_item"], data["notes"],
            created_by, created_by,
        ),
    )
    conn.commit()
    conn.close()
    return coupon_id


def list_coupons():
    conn = _conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM coupons ORDER BY created_at DESC"
    ).fetchall()]
    conn.close()
    return rows


def get_coupon(coupon_id: str):
    conn = _conn()
    row = conn.execute("SELECT * FROM coupons WHERE coupon_id=?", (coupon_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_signoffs(coupon_id: str, phase: int):
    conn = _conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM phase_signoffs WHERE coupon_id=? AND phase=?", (coupon_id, phase)
    ).fetchall()]
    conn.close()
    return rows


def add_signoff(coupon_id: str, phase: int, role: str, signed_by: str, display_name: str, notes: str = ""):
    conn = _conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO phase_signoffs
               (coupon_id, phase, role, signed_by, display_name, notes)
               VALUES (?,?,?,?,?,?)""",
            (coupon_id, phase, role, signed_by, display_name, notes),
        )
        conn.commit()
        result = True
    except Exception:
        result = False
    conn.close()
    return result


def phase2_complete(coupon_id: str) -> bool:
    signed = {s["role"] for s in get_signoffs(coupon_id, 2)}
    return PHASE2_REQUIRED.issubset(signed)


def advance_to_phase3(coupon_id: str):
    conn = _conn()
    conn.execute(
        "UPDATE coupons SET current_phase=3, p2_completed_at=datetime('now'), jira_status='Eng. Definition' WHERE coupon_id=?",
        (coupon_id,),
    )
    conn.commit()
    conn.close()


def complete_phase3(coupon_id: str, tc_ebom: str, completed_by: str):
    conn = _conn()
    conn.execute(
        """UPDATE coupons SET p3_tc_ebom=?, p3_completed_at=datetime('now'),
           p3_completed_by=? WHERE coupon_id=?""",
        (tc_ebom, completed_by, coupon_id),
    )
    conn.commit()
    conn.close()
    # Unlock phases 4, 5, 6 in parallel
    phase_complete(coupon_id, 3, [4, 5, 6])


def phase_complete(coupon_id: str, done_phase: int, next_phases: list):
    """
    Mark done_phase complete, remove from active, unlock next_phases.
    Phase 8 only unlocks when phases 5, 6, AND 7 are all complete (convergence gate).
    """
    conn = _conn()
    row = conn.execute(
        "SELECT active_phases, completed_phases, current_phase FROM coupons WHERE coupon_id=?",
        (coupon_id,),
    ).fetchone()
    active    = json.loads(row["active_phases"]    or "[]") if row["active_phases"]    else []
    completed = json.loads(row["completed_phases"] or "[]") if row["completed_phases"] else []

    # Seed active from current_phase if not yet initialised
    if not active:
        active = [row["current_phase"]]

    if done_phase not in completed:
        completed.append(done_phase)
    if done_phase in active:
        active.remove(done_phase)

    for p in next_phases:
        if p == 8:
            # Convergence gate: 5, 6, AND 7 must all be complete
            if all(x in completed for x in [5, 6, 7]) and 8 not in active and 8 not in completed:
                active.append(8)
        elif p not in completed and p not in active:
            active.append(p)

    active.sort()
    display_phase = min(active) if active else done_phase
    status = JIRA_STATUSES.get(display_phase, f"Phase {display_phase}")
    conn.execute(
        """UPDATE coupons SET active_phases=?, completed_phases=?,
           current_phase=?, jira_status=? WHERE coupon_id=?""",
        (json.dumps(active), json.dumps(completed), display_phase, status, coupon_id),
    )
    conn.commit()
    conn.close()


def advance_coupon_phase(coupon_id: str, new_phase: int):
    """Generic phase advance for phases 4 onward (legacy / sequential)."""
    status = JIRA_STATUSES.get(new_phase, f"Phase {new_phase}")
    conn = _conn()
    conn.execute(
        "UPDATE coupons SET current_phase=?, jira_status=? WHERE coupon_id=?",
        (new_phase, status, coupon_id),
    )
    conn.commit()
    conn.close()


def close_work_order(coupon_id: str, closed_by: str):
    """Mark a work order as fully closed after Phase 9 NCR review."""
    conn = _conn()
    conn.execute(
        """UPDATE coupons
           SET current_phase=9, jira_status='Closed',
               closed_at=datetime('now'), closed_by=?
           WHERE coupon_id=?""",
        (closed_by, coupon_id),
    )
    conn.commit()
    conn.close()


def save_phase_submission(coupon_id: str, phase: int, submitted_by: str, data: dict):
    conn = _conn()
    conn.execute(
        """INSERT OR REPLACE INTO phase_submissions (coupon_id, phase, submitted_by, data_json)
           VALUES (?,?,?,?)""",
        (coupon_id, phase, submitted_by, json.dumps(data)),
    )
    conn.commit()
    conn.close()


def get_phase_submission(coupon_id: str, phase: int):
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM phase_submissions WHERE coupon_id=? AND phase=? LIMIT 1",
        (coupon_id, phase),
    ).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["data"] = json.loads(d["data_json"])
        return d
    return None


def phase5_complete(coupon_id: str) -> bool:
    signed = {s["role"] for s in get_signoffs(coupon_id, 5)}
    return PHASE5_REQUIRED.issubset(signed)


def phase7_complete(coupon_id: str) -> bool:
    signed = {s["role"] for s in get_signoffs(coupon_id, 7)}
    return PHASE7_REQUIRED.issubset(signed)


def phase8_complete(coupon_id: str) -> bool:
    signed = {s["role"] for s in get_signoffs(coupon_id, 8)}
    return PHASE8_REQUIRED.issubset(signed)


def phase9_complete(coupon_id: str) -> bool:
    signed = {s["role"] for s in get_signoffs(coupon_id, 9)}
    return PHASE9_REQUIRED.issubset(signed)


def count_by_phase() -> dict:
    """Return {phase_number: count} for active (non-closed) work orders only."""
    conn = _conn()
    rows = conn.execute(
        "SELECT current_phase, COUNT(*) as cnt FROM coupons WHERE closed_at IS NULL GROUP BY current_phase"
    ).fetchall()
    conn.close()
    return {row["current_phase"]: row["cnt"] for row in rows}


def add_phase_comment(coupon_id: str, phase: int, action: str, posted_by: str, display_name: str, comment: str):
    if not comment or not comment.strip():
        return
    conn = _conn()
    conn.execute(
        "INSERT INTO phase_comments (coupon_id, phase, action, posted_by, display_name, comment) VALUES (?,?,?,?,?,?)",
        (coupon_id, phase, action, posted_by, display_name, comment.strip()),
    )
    conn.commit()
    conn.close()


def get_phase_comments(coupon_id: str) -> list:
    conn = _conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM phase_comments WHERE coupon_id=? ORDER BY posted_at ASC",
        (coupon_id,),
    ).fetchall()]
    conn.close()
    return rows
