# MTE Coupon Fabrication Workflow

A Streamlit-based manufacturing workflow demo for managing coupon fabrication work orders through a 9-phase process with role-based access, multi-role sign-offs, and Jira integration.

---

## Quick Start

```bash
pip install streamlit requests
streamlit run app.py
```

On launch, select an operating mode:

| Mode | Description |
|------|-------------|
| **Preview** | All 9 phases visible. No login. Forms shown with sample data. Submits disabled. |
| **Demo** | Enforced workflow. Login required. Role-based access. Live Jira integration. |

---

## Preview Mode

Preview mode is a read-only walkthrough of the entire workflow.

- No login required (auto-authenticated as "Preview" role)
- All 9 phase nodes highlighted in the workflow diagram
- **Phase selector buttons** at the top of the dashboard let you jump to any phase
- Clicking a phase button or a work order action button opens a **popup dialog** with the full form and sample data
- All form controls are visible but **submits and sign-offs are disabled**
- A yellow banner reminds the user: *"PREVIEW MODE -- actions disabled"*
- No database writes, no Jira calls

### Preview Sample Data

The preview uses a fixed dummy work order:

| Field | Value |
|-------|-------|
| Work Order | CPN-20260317-042 |
| Jira Ticket | MTE-7 |
| Part Number | SUB-CPN-0042 |
| Description | Hull coupon -- weld test specimen for rib-to-shell joint qualification |
| Priority | High |

---

## Demo Mode

Demo mode is the full interactive workflow with login, role gates, and live execution.

### Login

All demo accounts use password: **`demo`**

| Username | Role | Display Name | Phases |
|----------|------|--------------|--------|
| `stakeholder` | Stakeholder | Alex Torres | 1 |
| `de_user` | DE (Design Engineer) | Jordan Lee | 1, 2, 3 |
| `me_user` | ME (Manufacturing Engineer) | Sam Rivera | 1, 2, 3, 5 |
| `weld_eng` | Weld Engineer | Casey Kim | 1, 2, 5 |
| `supply_chain` | Supply Chain | Morgan Chen | 4, 7 |
| `ie_user` | IE (Industrial Engineer) | Riley Adams | 6 |
| `qe_user` | QE (Quality Engineer) | Drew Patel | 5, 7, 8, 9 |
| `warehouse` | Warehouse/MMO | Quinn Nguyen | 7 |
| `mechanic` | Mechanic | Chris Martinez | 8, 9 |

### Dashboard

After login, the dashboard displays:

1. **Workflow SVG** -- Tron-style diagram showing all 9 phases with status indicators, active work order counts, and clickable nodes
2. **NEW REQUEST button** -- Opens a modal dialog to create a new work order (available to Stakeholder, DE, ME, Weld Engineer)
3. **Role Context Card** -- Shows your role and which phases you have access to, with active work order counts
4. **Active Work Orders** -- Table of open work orders with action buttons (Sign Off, Submit, Execute, etc.)
5. **Closed Work Orders** -- Read-only list of completed work orders

Clicking any action button on an active work order opens a **popup modal dialog** with the phase-specific form for that coupon.

---

## The 9-Phase Process

```
Phase 1 --> Phase 2 --> Phase 3 --+--> Phase 4 --> Phase 7 --+
                                  |                          |
                                  +--> Phase 5 --------------+--> Phase 8 --> Phase 9
                                  |                          |
                                  +--> Phase 6 --------------+
```

### Phase 1: Initiate Design Request

| | |
|---|---|
| **Roles** | Stakeholder, DE, ME, Weld Engineer |
| **Type** | Submission form |
| **Unlocks** | Phase 2 |

The requesting stakeholder (or any authorized role) creates a new work order by entering:

- Part Number, NX Model Reference, TC Engineering Item (required)
- Description, Priority, Requesting Stakeholder (required)
- Notes / Special Requirements (optional)

On submit:
- Coupon ID generated: `CPN-YYYYMMDD-###`
- Jira ticket created with labels `coupon-fab` + `phase-1-design-request`
- Work order advances to Phase 2

### Phase 2: Alignment Sign-Off

| | |
|---|---|
| **Roles** | DE, ME, Weld Engineer (all 3 required) |
| **Type** | Multi-role sign-off |
| **Unlocks** | Phase 3 |

All three roles must independently confirm alignment on design, fabrication, and manufacturing processes. Each role provides an optional comment for downstream context.

Progress bar tracks sign-off completion (0/3 to 3/3).

When all roles have signed off, DE can advance to Phase 3.

**Jira**: Adds comment, updates label to `phase-2-alignment`, transitions to **In Progress**.

### Phase 3: NX Design + TC EBOM Creation

| | |
|---|---|
| **Roles** | DE only |
| **Type** | Submission form |
| **Unlocks** | Phases 4, 5, 6 (parallel) |

DE confirms NX model design completion and enters TC EBOM item reference.

On submit, three parallel branches unlock simultaneously:
- Phase 4 (Procurement)
- Phase 5 (Work Instructions)
- Phase 6 (Resourcing)

**Jira**: Adds comment, updates label to `phase-3-design`.

### Phase 4: Procurement / Scheduling

| | |
|---|---|
| **Roles** | Supply Chain only |
| **Type** | Submission form (parallel with 5 & 6) |
| **Unlocks** | Phase 7 |

Supply Chain enters procurement details: PR number, vendor, RFQ reference, PO number, estimated delivery date, and procurement notes.

**Jira**: Adds comment, updates label to `phase-4-procurement`.

### Phase 5: Work Instructions Sign-Off

| | |
|---|---|
| **Roles** | ME, Weld Engineer, QE (all 3 required) |
| **Type** | Multi-role sign-off (parallel with 4 & 6) |
| **Unlocks** | Phase 8 (with convergence gate) |

Each role confirms their work instruction documents:

| Role | Document Reference |
|------|-------------------|
| ME | Work Instruction / Bill of Process (WI Doc Ref) |
| Weld Engineer | Welding Process Specification (WPS / Weld Proc Ref) |
| QE | Inspection Plan (Inspection Plan Ref) |

**Jira**: Adds comment, updates label to `phase-5-work-instructions`.

### Phase 6: Resourcing / Work Allocation

| | |
|---|---|
| **Roles** | IE only |
| **Type** | Submission form (parallel with 4 & 5) |
| **Unlocks** | Phase 8 (with convergence gate) |

IE assigns a technician, schedules start/end dates, and specifies shift, work package reference, and resourcing notes.

**Jira**: Adds comment, updates label to `phase-6-resourcing`.

### Phase 7: Material Receiving Sign-Off

| | |
|---|---|
| **Roles** | Supply Chain, QE, Warehouse/MMO (all 3 required) |
| **Type** | Multi-role sign-off |
| **Unlocks** | Phase 8 (with convergence gate) |

Each role confirms material receipt:

| Role | Document Reference |
|------|-------------------|
| Supply Chain | PO / Packing Slip Ref |
| QE | Inspection Record Ref |
| Warehouse/MMO | Storage Location / Bin |

**Jira**: Adds comment, updates label to `phase-7-receiving`.

### Phase 8: Work Execution (Convergence)

| | |
|---|---|
| **Roles** | Mechanic, ME, QE (all 3 required) |
| **Type** | Multi-role sign-off |
| **Unlocks** | Phase 9 |
| **Gate** | Requires Phases 5, 6, AND 7 all complete |

This is the **convergence node** where all parallel branches merge. Phase 8 only unlocks when phases 5, 6, and 7 have ALL been completed.

| Role | Document Reference |
|------|-------------------|
| Mechanic (Mfg Tech) | Work Completion Notes / Redline Ref |
| ME | ME Sign-Off Notes |
| QE | Inspection Record / QC Ref |

When all 3 sign off, Mechanic or ME can advance to Phase 9.

**Jira**: Adds comment, updates label to `phase-8-execution`.

### Phase 9: Non-Conformance (NCR) Review & Close

| | |
|---|---|
| **Roles** | QE, ME, Mechanic (all 3 required to close) |
| **Type** | Assessment + disposition sign-off + close |

Three-part process:

1. **QE NCR Assessment** -- QE determines if non-conformance exists. If yes: enters NCR number, disposition (Use As Is / Rework / Repair / Return to Vendor / Scrap), and description.
2. **Disposition Confirmation** -- ME and Mechanic each review and confirm the QE assessment.
3. **Close Work Order** -- QE closes the work order after all confirmations.

**Jira**: Adds closing comment, transitions to **Done**, label remains `phase-9-ncr`.

---

## Jira Integration

Configured via `.streamlit/secrets.toml`:

```toml
[jira]
base_url    = "https://your-org.atlassian.net"
email       = "you@example.com"
api_token   = "your-api-token"
project_key = "MTE"
issue_type  = "10005"
```

All Jira calls fail silently if not configured -- the app works fully without Jira.

### Jira Lifecycle

| Event | Jira Action | Status | Labels |
|-------|-------------|--------|--------|
| Phase 1 submit | Create issue | To Do | `coupon-fab`, `phase-1-design-request` |
| Phase 2 complete | Comment + transition | **In Progress** | `coupon-fab`, `phase-2-alignment` |
| Phase 3-8 advance | Comment + label update | In Progress | `coupon-fab`, `phase-N-*` |
| Phase 9 close | Comment + transition | **Done** | `coupon-fab`, `phase-9-ncr` |

Two labels are maintained on every ticket:
- **`coupon-fab`** -- Static identifier, applied on creation, never removed
- **`phase-N-*`** -- Dynamic phase label, swapped on each phase advance

---

## Database

SQLite database stored at `data/coupon_fab.db`. Created automatically on first run.

### Tables

| Table | Purpose |
|-------|---------|
| `users` | Demo user accounts (username, password, role, display_name) |
| `coupons` | Work orders with phase tracking, Jira references, and timestamps |
| `phase_signoffs` | Individual role sign-offs per phase (unique per coupon + phase + role) |
| `phase_submissions` | Form data for single-role submission phases (3, 4, 6) |
| `phase_comments` | Audit trail of all actions (sign-off, submit, advance, close) |

### Convergence Gate Logic

The `active_phases` and `completed_phases` JSON arrays on each coupon track parallel branch progress. Phase 8 requires that phases 5, 6, and 7 are all present in `completed_phases` before it can be added to `active_phases`.

---

## Project Structure

```
coupon-fab-demo/
  app.py              Main Streamlit application
  db.py               SQLite database layer
  jira.py             Jira REST API integration
  viz.py              Workflow SVG visualization
  .streamlit/
    secrets.toml      Jira credentials (not committed)
  data/
    coupon_fab.db      SQLite database (auto-created)
```

---

## UI Theme

Tron-inspired dark theme with:
- Primary cyan: `#00f5ff`
- Background: `#0c192b`
- Amber accent: `#ffc400`
- Dialog background: `#2F4F4E` with cyan border glow
- Phase 8 execution node: Emphasized with cyan highlight as convergence point
