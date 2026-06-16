#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    import cgi
except ModuleNotFoundError:
    cgi = None
import datetime as dt
import html
import json
import os
import re
import shutil
import sqlite3
import sys
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "prototype.sqlite"
UPLOADS_DIR = BASE_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports"

STAGES = [
    ("STAGE00", "Project Opening", "AG-00/AG-01"),
    ("STAGE01", "Intake and Scope", "AG-01"),
    ("STAGE02", "Document Extraction and Data Quality", "AG-02"),
    ("STAGE03", "Theory of Change and KPIs", "AG-03"),
    ("STAGE04", "Basic SROI", "AG-04"),
    ("STAGE05", "Risks, Gaps, and Recommendations", "AG-05"),
    ("STAGE06", "Dashboard and Impact Decision Brief", "AG-06"),
]

AGENTS = {
    "AG-00": "Master Orchestrator Agent",
    "AG-01": "Project Intake and Scope Agent",
    "AG-02": "Document Extraction and Data Quality Agent",
    "AG-03": "Theory of Change and KPI Agent",
    "AG-04": "Basic SROI Agent",
    "AG-05": "Risk, Gap, and Recommendation Agent",
    "AG-06": "Dashboard and Report Agent",
}

PROJECT_FIELDS = [
    "project_name", "project_type", "study_type", "owning_entity", "project_owner",
    "study_manager", "department", "location", "implementation_period",
    "budget_or_investment_value", "funding_source", "waqf_or_charity_category",
    "target_beneficiaries", "expected_number_of_beneficiaries",
    "problem_or_social_need", "project_objectives", "main_activities",
    "expected_outputs", "expected_outcomes", "available_kpis", "available_evidence",
    "management_decision_required", "initial_risks", "missing_data",
    "confidentiality_level", "beneficiary_privacy_requirements",
    "project_opening_approval_status",
]

MANDATORY_FIELDS = [
    "project_name", "project_type", "study_type", "owning_entity", "project_owner",
    "study_manager", "department", "location", "implementation_period",
    "budget_or_investment_value", "funding_source", "waqf_or_charity_category",
    "target_beneficiaries", "expected_number_of_beneficiaries",
    "problem_or_social_need", "project_objectives", "main_activities",
    "expected_outputs", "expected_outcomes", "management_decision_required",
    "confidentiality_level", "beneficiary_privacy_requirements",
    "project_opening_approval_status",
]


def now():
    return dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def ensure_dirs():
    for p in [DB_PATH.parent, UPLOADS_DIR, REPORTS_DIR, REPORTS_DIR / "interim", REPORTS_DIR / "final"]:
        p.mkdir(parents=True, exist_ok=True)


def db():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                project_name TEXT, project_type TEXT, study_type TEXT,
                owning_entity TEXT, project_owner TEXT, study_manager TEXT,
                department TEXT, location TEXT, implementation_period TEXT,
                budget_or_investment_value REAL, funding_source TEXT,
                waqf_or_charity_category TEXT, target_beneficiaries TEXT,
                expected_number_of_beneficiaries INTEGER,
                problem_or_social_need TEXT, project_objectives TEXT,
                main_activities TEXT, expected_outputs TEXT, expected_outcomes TEXT,
                available_kpis TEXT, available_evidence TEXT,
                management_decision_required TEXT, initial_risks TEXT,
                missing_data TEXT, confidentiality_level TEXT,
                beneficiary_privacy_requirements TEXT,
                project_opening_approval_status TEXT,
                current_stage TEXT DEFAULT 'STAGE00',
                current_status TEXT DEFAULT 'Draft',
                created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                file_name TEXT, file_type TEXT, upload_date TEXT,
                storage_path TEXT, extracted_text TEXT,
                extraction_confirmed INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS evidence_register (
                evidence_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                evidence_type TEXT, evidence_level TEXT, source_name TEXT,
                source_file TEXT, source_date TEXT, owner TEXT,
                description TEXT, linked_finding TEXT, linked_calculation TEXT,
                confidence_level TEXT, external_reporting_allowed INTEGER,
                approved_for_use INTEGER DEFAULT 0, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS assumption_register (
                assumption_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                assumption_description TEXT, assumption_value TEXT, used_in TEXT,
                evidence_level TEXT, confidence_level TEXT, rationale TEXT,
                owner TEXT, approval_status TEXT, sensitivity_tested INTEGER,
                impact_if_changed TEXT, last_updated TEXT
            );
            CREATE TABLE IF NOT EXISTS stakeholders (
                stakeholder_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                stakeholder_name TEXT, stakeholder_type TEXT, role TEXT,
                expected_benefit TEXT, approved_in_scope INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS theory_of_change (
                toc_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                input TEXT, activity TEXT, output TEXT, outcome TEXT,
                impact TEXT, assumption_id TEXT, causal_risk_level TEXT,
                evidence_id TEXT, toc_approval_status TEXT
            );
            CREATE TABLE IF NOT EXISTS kpi_register (
                kpi_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                toc_id TEXT, kpi_name TEXT, formula TEXT, source TEXT,
                baseline TEXT, target TEXT, frequency TEXT, owner TEXT,
                threshold TEXT, evidence_id TEXT, confidence_level TEXT,
                kpi_approval_status TEXT
            );
            CREATE TABLE IF NOT EXISTS sroi_outcomes (
                sroi_outcome_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                kpi_id TEXT, outcome TEXT, stakeholder TEXT,
                quantity REAL, financial_proxy REAL, proxy_source TEXT,
                deadweight REAL, attribution REAL, displacement REAL,
                dropoff REAL, discount_rate REAL, gross_value REAL,
                adjusted_value_y1 REAL, present_value REAL,
                proxy_evidence_id TEXT, assumption_approval_status TEXT
            );
            CREATE TABLE IF NOT EXISTS sroi_summary (
                sroi_summary_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                total_investment REAL, total_present_value REAL,
                net_social_value REAL, sroi_ratio REAL,
                conservative_ratio REAL, optimistic_ratio REAL,
                higher_deadweight_ratio REAL, break_even_value REAL,
                sroi_approval_status TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS risk_register (
                risk_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                risk_category TEXT, risk_description TEXT,
                likelihood INTEGER, impact INTEGER, risk_score INTEGER,
                risk_level TEXT, owner TEXT, evidence_id TEXT,
                risk_approval_status TEXT
            );
            CREATE TABLE IF NOT EXISTS gaps (
                gap_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                gap_type TEXT, current_state TEXT, required_state TEXT,
                impact TEXT, priority TEXT, evidence_id TEXT,
                gap_approval_status TEXT
            );
            CREATE TABLE IF NOT EXISTS recommendations (
                recommendation_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                gap_id TEXT, risk_id TEXT, recommendation TEXT,
                priority TEXT, owner TEXT, due_date TEXT,
                expected_result TEXT, evidence_id TEXT,
                recommendation_approval_status TEXT
            );
            CREATE TABLE IF NOT EXISTS agent_log (
                run_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                agent_id TEXT, agent_name TEXT, stage_id TEXT,
                execution_timestamp TEXT, input_sources TEXT,
                output_report_name TEXT, memory_version TEXT,
                agent_status TEXT, approval_status TEXT,
                resume_token TEXT, warnings TEXT, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS stage_gates (
                stage_gate_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                stage_id TEXT, stage_name TEXT, lead_agent TEXT,
                stage_status TEXT, started_at TEXT, completed_at TEXT,
                approved_by TEXT, approved_at TEXT, approval_decision TEXT,
                approval_comments TEXT, resume_token TEXT, next_stage TEXT,
                blocking_issues TEXT
            );
            CREATE TABLE IF NOT EXISTS project_memory (
                memory_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                project_name TEXT, project_type TEXT, study_type TEXT,
                current_stage TEXT, current_status TEXT,
                last_approved_stage TEXT, pending_approval TEXT,
                memory_version TEXT, resume_token TEXT,
                completed_stages TEXT, uploaded_documents TEXT,
                missing_data TEXT, evidence_register TEXT,
                assumption_register TEXT, key_findings TEXT,
                sroi_findings TEXT, key_risks TEXT, material_gaps TEXT,
                priority_recommendations TEXT, reports_issued TEXT,
                next_required_action TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS dashboard (
                dashboard_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                current_stage TEXT, stage_completion_percentage REAL,
                data_completeness_score REAL, evidence_confidence_level TEXT,
                total_investment REAL, total_present_value REAL,
                net_social_value REAL, sroi_ratio REAL,
                number_of_beneficiaries INTEGER, cost_per_beneficiary REAL,
                key_outcomes TEXT, number_of_risks INTEGER,
                high_critical_risks INTEGER, missing_data_items INTEGER,
                number_of_recommendations INTEGER, pending_approvals TEXT,
                final_decision_recommendation TEXT, traffic_light_status TEXT,
                generated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                project_id TEXT REFERENCES projects(project_id),
                stage_id TEXT, report_name TEXT, report_type TEXT,
                content TEXT, file_path TEXT, memory_version TEXT,
                created_at TEXT, approved_only INTEGER DEFAULT 0
            );
            """
        )


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def next_project_id(con):
    row = con.execute("SELECT COUNT(*) AS c FROM projects").fetchone()
    return f"P{int(row['c']) + 1:03d}"


def dict_row(row):
    return dict(row) if row else None


def project(con, project_id):
    return dict_row(con.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone())


def approved_stage_ids(con, project_id):
    rows = con.execute(
        "SELECT stage_id FROM stage_gates WHERE project_id=? AND stage_status='Approved'",
        (project_id,),
    ).fetchall()
    return {r["stage_id"] for r in rows}


def stage_name(stage_id):
    return next((s[1] for s in STAGES if s[0] == stage_id), stage_id)


def stage_lead(stage_id):
    return next((s[2] for s in STAGES if s[0] == stage_id), "AG-00")


def next_unapproved_stage(con, project_id):
    approved = approved_stage_ids(con, project_id)
    for stage_id, _, _ in STAGES:
        if stage_id not in approved:
            return stage_id
    return "COMPLETE"


def memory_version(con, project_id):
    row = con.execute(
        "SELECT memory_version FROM project_memory WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    if not row:
        return "M001"
    match = re.search(r"(\d+)", row["memory_version"] or "M001")
    return f"M{int(match.group(1)) + 1:03d}"


def current_memory_version(con, project_id):
    row = con.execute(
        "SELECT memory_version FROM project_memory WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    return row["memory_version"] if row else "M001"


def resume_token(project_id, stage_id, mem):
    return f"RESUME-{project_id}-{stage_id}-{mem}"


def missing_items(p):
    items = []
    for f in MANDATORY_FIELDS:
        val = p.get(f)
        if val is None or str(val).strip() == "":
            items.append(f)
    if float_or_zero(p.get("budget_or_investment_value")) <= 0:
        items.append("budget_or_investment_value")
    if int_or_zero(p.get("expected_number_of_beneficiaries")) <= 0:
        items.append("expected_number_of_beneficiaries")
    return sorted(set(items))


def data_completeness(p):
    total = len(MANDATORY_FIELDS)
    missing = len([f for f in MANDATORY_FIELDS if not str(p.get(f) or "").strip()])
    return round(max(0, (total - missing) / total) * 100, 1)


def int_or_zero(v):
    try:
        return int(float(str(v).replace(",", "")))
    except Exception:
        return 0


def float_or_zero(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return 0.0


def risk_level(score):
    if score <= 4:
        return "Low"
    if score <= 9:
        return "Moderate"
    if score <= 16:
        return "High"
    return "Critical"


def write_report(con, project_id, stage_id, name, report_type, content, approved_only=0):
    mem = current_memory_version(con, project_id)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{project_id}_{stage_id}_{name}")[:90]
    folder = REPORTS_DIR / ("final" if stage_id == "STAGE06" else "interim")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{safe}.md"
    path.write_text(content, encoding="utf-8")
    rid = uid("RPT")
    con.execute(
        """INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (rid, project_id, stage_id, name, report_type, content, str(path), mem, now(), approved_only),
    )
    return str(path)


def add_agent_log(con, project_id, agent_id, stage_id, output_name, status="Completed", approval="Under Review", warnings="", notes=""):
    mem = current_memory_version(con, project_id)
    token = resume_token(project_id, stage_id, mem)
    con.execute(
        """INSERT INTO agent_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            uid("RUN"), project_id, agent_id, AGENTS.get(agent_id, agent_id), stage_id, now(),
            "Project memory, approved registers, user inputs", output_name, mem,
            status, approval, token, warnings, notes,
        ),
    )
    return token


def upsert_stage_gate(con, project_id, stage_id, status, decision="", comments="", blocking=""):
    row = con.execute(
        "SELECT stage_gate_id, started_at FROM stage_gates WHERE project_id=? AND stage_id=?",
        (project_id, stage_id),
    ).fetchone()
    mem = current_memory_version(con, project_id)
    token = resume_token(project_id, stage_id, mem)
    next_stage = stage_after(stage_id)
    if row:
        con.execute(
            """UPDATE stage_gates SET stage_status=?, completed_at=?, approved_at=?,
            approval_decision=?, approval_comments=?, resume_token=?, next_stage=?,
            blocking_issues=? WHERE stage_gate_id=?""",
            (
                status,
                now() if status in ["Under Review", "Approved", "Needs Revision", "Suspended", "Closed"] else None,
                now() if status == "Approved" else None,
                decision, comments, token, next_stage, blocking, row["stage_gate_id"],
            ),
        )
    else:
        con.execute(
            """INSERT INTO stage_gates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                uid("GATE"), project_id, stage_id, stage_name(stage_id), stage_lead(stage_id),
                status, now(), now() if status != "Draft" else None, None,
                now() if status == "Approved" else None, decision, comments,
                token, next_stage, blocking,
            ),
        )
    con.execute(
        "UPDATE projects SET current_stage=?, current_status=?, updated_at=? WHERE project_id=?",
        (stage_id, status, now(), project_id),
    )
    return token


def stage_after(stage_id):
    ids = [s[0] for s in STAGES]
    if stage_id not in ids:
        return ""
    i = ids.index(stage_id)
    return ids[i + 1] if i + 1 < len(ids) else "COMPLETE"


def update_memory(con, project_id, current_stage, status, next_action, extra=None):
    p = project(con, project_id)
    mem = memory_version(con, project_id)
    token = resume_token(project_id, current_stage, mem)
    approved = sorted(approved_stage_ids(con, project_id))
    docs = [r["file_name"] for r in con.execute("SELECT file_name FROM documents WHERE project_id=?", (project_id,))]
    ev_count = con.execute("SELECT COUNT(*) c FROM evidence_register WHERE project_id=?", (project_id,)).fetchone()["c"]
    as_count = con.execute("SELECT COUNT(*) c FROM assumption_register WHERE project_id=?", (project_id,)).fetchone()["c"]
    risks = [f"{r['risk_level']}: {r['risk_description']}" for r in con.execute("SELECT risk_level,risk_description FROM risk_register WHERE project_id=?", (project_id,))]
    recs = [r["recommendation"] for r in con.execute("SELECT recommendation FROM recommendations WHERE project_id=?", (project_id,))]
    sroi = con.execute("SELECT * FROM sroi_summary WHERE project_id=? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
    reports = [r["report_name"] for r in con.execute("SELECT report_name FROM reports WHERE project_id=?", (project_id,))]
    md = missing_items(p)
    con.execute(
        """INSERT INTO project_memory VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            uid("MEM"), project_id, p["project_name"], p["project_type"], p["study_type"],
            current_stage, status, approved[-1] if approved else "", current_stage if status == "Under Review" else "",
            mem, token, json.dumps(approved), json.dumps(docs), json.dumps(md),
            f"{ev_count} evidence records", f"{as_count} assumption records",
            (extra or {}).get("key_findings", ""), json.dumps(dict_row(sroi)) if sroi else "",
            json.dumps(risks), "", json.dumps(recs), json.dumps(reports), next_action, now(),
        ),
    )
    return token


def extract_text(path):
    suffix = path.suffix.lower()
    try:
        if suffix in [".txt", ".md", ".csv"]:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".docx":
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        if suffix in [".xlsx", ".xlsm"]:
            import openpyxl
            wb = openpyxl.load_workbook(str(path), data_only=True)
            lines = []
            for ws in wb.worksheets:
                lines.append(f"Sheet: {ws.title}")
                for row in ws.iter_rows(values_only=True):
                    vals = [str(v) for v in row if v is not None]
                    if vals:
                        lines.append(" | ".join(vals))
            return "\n".join(lines)
        if suffix == ".pdf":
            return "PDF uploaded. Text extraction requires PyMuPDF or pdfplumber in this environment."
    except Exception as e:
        return f"Extraction error: {e}"
    return "Unsupported file type for extraction."


def infer_fields_from_text(text):
    out = {}
    patterns = {
        "project_name": r"(?:Project Name|اسم المشروع)\s*[:\-]\s*(.+)",
        "budget_or_investment_value": r"(?:Budget|الميزانية|Investment|قيمة الاستثمار)\s*[:\-]?\s*([0-9,]+(?:\.\d+)?)",
        "expected_number_of_beneficiaries": r"(?:Beneficiaries|المستفيدين|عدد المستفيدين)\s*[:\-]?\s*([0-9,]+)",
        "location": r"(?:Location|الموقع)\s*[:\-]\s*(.+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            out[key] = m.group(1).strip()[:300]
    return out


def create_project(data):
    with db() as con:
        project_id = data.get("project_id") or next_project_id(con)
        values = {f: data.get(f, "") for f in PROJECT_FIELDS}
        values["budget_or_investment_value"] = float_or_zero(values["budget_or_investment_value"])
        values["expected_number_of_beneficiaries"] = int_or_zero(values["expected_number_of_beneficiaries"])
        con.execute(
            f"""INSERT INTO projects
            (project_id,{','.join(PROJECT_FIELDS)},created_at,updated_at)
            VALUES ({','.join(['?'] * (len(PROJECT_FIELDS)+3))})""",
            [project_id] + [values[f] for f in PROJECT_FIELDS] + [now(), now()],
        )
        seed_stage_zero(con, project_id)
        update_memory(con, project_id, "STAGE00", "Draft", "Approve creation of project file or run Stage 00.")
        return project_id


def seed_stage_zero(con, project_id):
    p = project(con, project_id)
    for name, stype, role, benefit in [
        (p["target_beneficiaries"] or "Target beneficiaries", "Direct", "Beneficiary", p["expected_outcomes"] or "Expected social benefit"),
        (p["owning_entity"] or "Owning entity", "Internal", "Sponsor", "Governance and strategic decision-making"),
    ]:
        con.execute(
            "INSERT INTO stakeholders VALUES (?,?,?,?,?,?,?)",
            (uid("STK"), project_id, name, stype, role, benefit, 1),
        )
    con.execute(
        """INSERT INTO evidence_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            uid("EVD"), project_id, "Opening Form", "L2", "Project Opening Form", "",
            now()[:10], p["project_owner"], "Project opening fields submitted by user",
            "Project profile", "", "B", 0, 1, "Internal record; external reporting requires validation.",
        ),
    )


def run_stage(project_id, requested=None):
    with db() as con:
        p = project(con, project_id)
        if not p:
            raise ValueError("Project not found")
        stage_id = requested or next_unapproved_stage(con, project_id)
        if stage_id == "COMPLETE":
            return {"stage_id": "COMPLETE", "message": "All stages are approved."}
        required_previous = previous_stage(stage_id)
        if required_previous and required_previous not in approved_stage_ids(con, project_id):
            raise ValueError(f"Cannot run {stage_id}. Previous stage {required_previous} is not approved.")
        if stage_id == "STAGE00":
            content = report_stage00(con, project_id)
            agent_id = "AG-00"
            name = "Project Opening Note"
        elif stage_id == "STAGE01":
            content = report_stage01(con, project_id)
            agent_id = "AG-01"
            name = "Project Definition and Scope Report"
        elif stage_id == "STAGE02":
            content = report_stage02(con, project_id)
            agent_id = "AG-02"
            name = "Document Extraction and Data Quality Report"
        elif stage_id == "STAGE03":
            content = report_stage03(con, project_id)
            agent_id = "AG-03"
            name = "Theory of Change and KPI Framework Report"
        elif stage_id == "STAGE04":
            content = report_stage04(con, project_id)
            agent_id = "AG-04"
            name = "Basic SROI Assessment Report"
        elif stage_id == "STAGE05":
            content = report_stage05(con, project_id)
            agent_id = "AG-05"
            name = "Risk, Gap, and Recommendation Report"
        elif stage_id == "STAGE06":
            missing_approvals = [s[0] for s in STAGES[:-1] if s[0] not in approved_stage_ids(con, project_id)]
            if missing_approvals:
                raise ValueError(f"Cannot generate final output. Missing approvals: {', '.join(missing_approvals)}")
            content = report_stage06(con, project_id)
            agent_id = "AG-06"
            name = "Prototype Executive Dashboard and Impact Decision Brief"
        else:
            raise ValueError("Unknown stage")
        path = write_report(con, project_id, stage_id, name, "Interim" if stage_id != "STAGE06" else "Final", content)
        token = add_agent_log(con, project_id, agent_id, stage_id, name)
        upsert_stage_gate(con, project_id, stage_id, "Under Review", "Pending management approval", "", "")
        update_memory(con, project_id, stage_id, "Under Review", "APPROVE STAGE, REVISE STAGE, ADD DATA, or PAUSE.", {"key_findings": name})
        return {"stage_id": stage_id, "report": content, "path": path, "resume_token": token}


def previous_stage(stage_id):
    ids = [s[0] for s in STAGES]
    if stage_id not in ids:
        return None
    i = ids.index(stage_id)
    return ids[i - 1] if i > 0 else None


def report_header(con, project_id, title):
    p = project(con, project_id)
    mem = current_memory_version(con, project_id)
    return f"""# {title}

**Project_ID:** {project_id}  
**Project_Name:** {p['project_name']}  
**Memory_Version:** {mem}  
**Generated_At:** {now()}  

"""


def missing_block(field, why, assumption="", owner="Project Owner", can_continue="Yes", external="No"):
    return f"""Missing Data: {field}
Why It Matters: {why}
Proposed Temporary Assumption: {assumption or "Prototype assumption — not approved for external reporting."}
Evidence Level: L1
Confidence Level: D
Owner: {owner}
Collection Method: Request official record or management confirmation.
Required Date: Before external reporting.
Reporting Limitation: Evidence gap: validation required before external reporting.
Can Prototype Continue? {can_continue}
Can External Reporting Proceed? {external}
"""


def report_stage00(con, project_id):
    p = project(con, project_id)
    md = missing_items(p)
    body = report_header(con, project_id, "Project Opening Note")
    body += f"""## Opening Record
- Owning Entity: {p['owning_entity']}
- Project Owner: {p['project_owner']}
- Study Type: {p['study_type']}
- Location: {p['location']}
- Total Investment: {p['budget_or_investment_value']:,.2f}
- Expected Beneficiaries: {p['expected_number_of_beneficiaries']:,}
- Management Decision Required: {p['management_decision_required']}

## Missing Data Register
"""
    if md:
        body += "\n".join(missing_block(f, "Mandatory for controlled project opening.") for f in md)
    else:
        body += "No mandatory opening data gaps detected.\n"
    body += "\n## Stop Rule\nManagement approval required before implementation.\n"
    return body


def report_stage01(con, project_id):
    p = project(con, project_id)
    stakeholders = con.execute("SELECT * FROM stakeholders WHERE project_id=?", (project_id,)).fetchall()
    md = missing_items(p)
    body = report_header(con, project_id, "Project Definition and Scope Report")
    body += f"""## Project Scope
- Project Type: {p['project_type']}
- Study Type: {p['study_type']}
- Assessment Boundary: One pilot project only; no portfolio analytics or external assurance workflow.
- Target Beneficiaries: {p['target_beneficiaries']}
- Problem or Social Need: {p['problem_or_social_need']}
- Objectives: {p['project_objectives']}

## Stakeholders
"""
    for s in stakeholders:
        body += f"- {s['stakeholder_name']} ({s['stakeholder_type']}): {s['expected_benefit']}\n"
    body += "\n## Initial Assumptions\n"
    if p["missing_data"]:
        con.execute(
            "INSERT INTO assumption_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid("ASM"), project_id, "Known missing data from opening form", p["missing_data"], "Scope definition", "L1", "D", "User identified gap", p["project_owner"], "Pending", 0, "May limit report confidence", now()),
        )
        body += f"- {p['missing_data']} (Evidence L1, Confidence D)\n"
    else:
        body += "- No user-declared opening assumptions.\n"
    body += "\n## Missing Data\n"
    body += "No critical scope gaps detected.\n" if not md else "\n".join(missing_block(f, "Required for reliable scope confirmation.") for f in md)
    body += "\n## Stop Rule\nDo not move to document/data quality stage until the intake stage is approved.\n"
    return body


def report_stage02(con, project_id):
    docs = con.execute("SELECT * FROM documents WHERE project_id=?", (project_id,)).fetchall()
    p = project(con, project_id)
    body = report_header(con, project_id, "Document Extraction and Data Quality Report")
    body += "## Uploaded Document Register\n"
    if not docs:
        body += "- No documents uploaded. Evidence gap: validation required before external reporting.\n"
        con.execute(
            "INSERT INTO evidence_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid("EVD"), project_id, "Missing Document", "L1", "No uploaded source", "", now()[:10], p["project_owner"], "No supporting document uploaded", "Data quality", "", "D", 0, 0, "Evidence gap: validation required before external reporting."),
        )
    for d in docs:
        body += f"- {d['file_name']} ({d['file_type']}), uploaded {d['upload_date']}\n"
        text = d["extracted_text"] or ""
        conf = "C" if "Extraction error" in text or "requires" in text else "B"
        con.execute(
            "INSERT INTO evidence_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid("EVD"), project_id, "Uploaded Document", "L2", d["file_name"], d["storage_path"], d["upload_date"][:10], p["project_owner"], text[:500], "Document evidence", "", conf, 0, 0, "Internal evidence; external reporting requires validation."),
        )
    body += "\n## Data Quality Assessment\n"
    body += f"- Data Completeness Score: {data_completeness(p)}%\n"
    evidence_rows = con.execute("SELECT evidence_level, confidence_level, description FROM evidence_register WHERE project_id=?", (project_id,)).fetchall()
    for ev in evidence_rows[-8:]:
        body += f"- Evidence {ev['evidence_level']} / Confidence {ev['confidence_level']}: {ev['description'][:120]}\n"
    body += "\n## Evidence Improvement Plan\n- Validate financial and beneficiary numbers before external reporting.\n- Add stakeholder survey if outcome evidence is needed.\n- Attach board/finance approval records where available.\n\n## Stop Rule\nStop after issuing the report and wait for approval.\n"
    return body


def report_stage03(con, project_id):
    p = project(con, project_id)
    toc_id = uid("TOC")
    input_txt = f"Investment value {p['budget_or_investment_value']:,.2f}; staff and delivery resources"
    activity = p["main_activities"] or "Deliver project activities"
    output = p["expected_outputs"] or "Project outputs delivered"
    outcome = p["expected_outcomes"] or "Improved beneficiary wellbeing"
    impact = f"Measurable social impact for {p['target_beneficiaries'] or 'target beneficiaries'}"
    con.execute(
        "INSERT INTO theory_of_change VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (toc_id, project_id, input_txt, activity, output, outcome, impact, "", "Moderate", "", "Under Review"),
    )
    kpis = [
        ("Beneficiaries served", "Count of unique beneficiaries served", "Project records", "0", str(p["expected_number_of_beneficiaries"] or 0), "Monthly", p["project_owner"], ">= 90% target"),
        ("Cost per beneficiary", "Total investment / beneficiaries served", "Finance records + beneficiary register", "N/A", f"{cost_per_beneficiary(p):,.2f}", "Quarterly", p["study_manager"], "Within approved budget"),
        ("Outcome achievement rate", "Beneficiaries achieving stated outcome / surveyed beneficiaries", "Stakeholder survey", "Prototype assumption", ">= 70%", "End of pilot", p["study_manager"], "Amber below 60%"),
    ]
    for k in kpis:
        con.execute(
            "INSERT INTO kpi_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid("KPI"), project_id, toc_id, *k, "", "C", "Under Review"),
        )
    body = report_header(con, project_id, "Theory of Change and KPI Framework Report")
    body += f"""## Basic Theory of Change
- Inputs: {input_txt}
- Activities: {activity}
- Outputs: {output}
- Short-Term Outcomes: {outcome}
- Medium-Term Outcomes: Improved stability and service access.
- Long-Term Impact: {impact}

## Causal Assumptions
- Beneficiaries can access and use the service as intended.
- Outputs are sufficient to contribute to the stated outcome.
- No major operational disruption occurs during implementation.

## KPI Framework
"""
    for k in kpis:
        body += f"- {k[0]} | Formula: {k[1]} | Source: {k[2]} | Target: {k[4]} | Owner: {k[6]}\n"
    body += "\n## Stop Rule\nStop after issuing the report and wait for approval.\n"
    return body


def cost_per_beneficiary(p):
    b = float_or_zero(p["budget_or_investment_value"])
    n = int_or_zero(p["expected_number_of_beneficiaries"])
    return b / n if n else 0


def report_stage04(con, project_id):
    p = project(con, project_id)
    con.execute("DELETE FROM sroi_outcomes WHERE project_id=?", (project_id,))
    con.execute("DELETE FROM sroi_summary WHERE project_id=?", (project_id,))
    investment = float_or_zero(p["budget_or_investment_value"])
    beneficiaries = int_or_zero(p["expected_number_of_beneficiaries"])
    if investment <= 0:
        return report_header(con, project_id, "Basic SROI Assessment Report") + missing_block("Budget_or_Investment_Value", "SROI ratio requires total investment.", can_continue="No", external="No")
    if beneficiaries <= 0:
        return report_header(con, project_id, "Basic SROI Assessment Report") + missing_block("Expected_Number_of_Beneficiaries", "SROI requires outcome quantity.", can_continue="No", external="No")
    proxy = round(max(investment / beneficiaries * 1.35, 100), 2)
    quantity = beneficiaries
    deadweight = 0.20
    attribution = 0.10
    displacement = 0.00
    dropoff = 0.15
    discount = 0.03
    gross = quantity * proxy
    adjusted_y1 = gross * (1 - deadweight) * (1 - attribution) * (1 - displacement)
    total_pv = 0
    years = []
    for year in range(1, 4):
        value = adjusted_y1 * ((1 - dropoff) ** (year - 1))
        pv = value / ((1 + discount) ** (year - 1))
        total_pv += pv
        years.append((year, value, pv))
    net = total_pv - investment
    ratio = total_pv / investment
    conservative = (total_pv * 0.8) / investment
    optimistic = (total_pv * 1.2) / investment
    higher_deadweight = (gross * (1 - 0.35) * (1 - attribution) * (1 - displacement)) / investment
    con.execute(
        """INSERT INTO sroi_outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid("SROI-O"), project_id, "", p["expected_outcomes"] or "Material social outcome", p["target_beneficiaries"], quantity, proxy, "Prototype assumption based on project cost per beneficiary; not approved for external reporting", deadweight, attribution, displacement, dropoff, discount, gross, adjusted_y1, total_pv, "", "Pending"),
    )
    con.execute(
        """INSERT INTO sroi_summary VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid("SROI-S"), project_id, investment, total_pv, net, ratio, conservative, optimistic, higher_deadweight, investment, "Under Review", now()),
    )
    con.execute(
        "INSERT INTO assumption_register VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (uid("ASM"), project_id, "Financial proxy per beneficiary", str(proxy), "SROI", "L1", "D", "Prototype assumption — not approved for external reporting.", p["study_manager"], "Pending", 1, "High impact on SROI ratio", now()),
    )
    body = report_header(con, project_id, "Basic SROI Assessment Report")
    body += f"""## SROI Inputs
- Total Investment: {investment:,.2f}
- Quantity: {quantity:,.0f}
- Financial Proxy: {proxy:,.2f}
- Deadweight: {deadweight:.0%}
- Attribution: {attribution:.0%}
- Displacement: {displacement:.0%}
- Drop-off: {dropoff:.0%}
- Discount Rate: {discount:.0%}

## Calculations
- Gross Value = {gross:,.2f}
- Adjusted Value Year 1 = {adjusted_y1:,.2f}
"""
    for y, value, pv in years:
        body += f"- Year {y}: Outcome Value {value:,.2f}; Present Value {pv:,.2f}\n"
    body += f"""
## SROI Result
- Total Present Value of Social Benefits: {total_pv:,.2f}
- Net Social Value: {net:,.2f}
- SROI Ratio: {ratio:.2f}:1

## Sensitivity Analysis
- Base case: {ratio:.2f}:1
- Conservative case -20% benefits: {conservative:.2f}:1
- Optimistic case +20% benefits: {optimistic:.2f}:1
- Higher deadweight case: {higher_deadweight:.2f}:1
- Break-even required benefits: {investment:,.2f}

## Limitation
SROI must not be used as the only decision basis. It must be interpreted with data quality, risks, sustainability, governance, implementation readiness, and management judgement.

## Stop Rule
Stop after issuing the report and wait for approval.
"""
    return body


def report_stage05(con, project_id):
    p = project(con, project_id)
    con.execute("DELETE FROM risk_register WHERE project_id=?", (project_id,))
    con.execute("DELETE FROM gaps WHERE project_id=?", (project_id,))
    con.execute("DELETE FROM recommendations WHERE project_id=?", (project_id,))
    md_count = len(missing_items(p))
    risk_templates = [
        ("Data-quality", "Evidence gaps may limit external reporting.", 4 if md_count else 2, 4 if md_count else 3, p["study_manager"]),
        ("Financial", "SROI depends on a prototype financial proxy unless verified.", 4, 4, p["project_owner"]),
        ("Governance", "Management approval is required before implementation or scaling.", 3, 4, p["owning_entity"]),
    ]
    risk_ids = []
    for cat, desc, likelihood, impact, owner in risk_templates:
        score = likelihood * impact
        rid = uid("RSK")
        risk_ids.append(rid)
        con.execute(
            "INSERT INTO risk_register VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (rid, project_id, cat, desc, likelihood, impact, score, risk_level(score), owner, "", "Under Review"),
        )
    gap_id = uid("GAP")
    con.execute(
        "INSERT INTO gaps VALUES (?,?,?,?,?,?,?,?,?)",
        (gap_id, project_id, "Evidence", "Internal or assumed evidence", "Verified evidence for external reporting", "Limits confidence and external publication", "High", "", "Under Review"),
    )
    recs = [
        ("Validate beneficiary count and financial records before external reporting.", "High", p["project_owner"], "+14 days", "Evidence confidence improves to B or A", risk_ids[0]),
        ("Replace prototype financial proxy with approved local proxy source.", "High", p["study_manager"], "+21 days", "SROI assumptions become auditable", risk_ids[1]),
        ("Approve or revise stage outputs through management gate.", "Medium", p["owning_entity"], "+7 days", "Governance trail completed", risk_ids[2]),
    ]
    for rec, priority, owner, due, expected, rid in recs:
        con.execute(
            "INSERT INTO recommendations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (uid("REC"), project_id, gap_id, rid, rec, priority, owner, due, expected, "", "Under Review"),
        )
    body = report_header(con, project_id, "Risk, Gap, and Recommendation Report")
    body += "## Risk Register\n"
    for r in con.execute("SELECT * FROM risk_register WHERE project_id=?", (project_id,)):
        body += f"- {r['risk_category']}: {r['risk_description']} | Score {r['risk_score']} | Level {r['risk_level']} | Owner {r['owner']}\n"
    body += "\n## Material Gap\n- Evidence gap between prototype assumptions/internal records and externally reportable assurance.\n\n## Priority Recommendations\n"
    for r in con.execute("SELECT * FROM recommendations WHERE project_id=?", (project_id,)):
        body += f"- {r['priority']}: {r['recommendation']} | Owner: {r['owner']} | Due: {r['due_date']}\n"
    body += "\n## Stop Rule\nStop after issuing the report and wait for approval.\n"
    return body


def dashboard_values(con, project_id):
    p = project(con, project_id)
    approved = approved_stage_ids(con, project_id)
    sroi = con.execute("SELECT * FROM sroi_summary WHERE project_id=? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
    risks = con.execute("SELECT COUNT(*) c FROM risk_register WHERE project_id=?", (project_id,)).fetchone()["c"]
    high = con.execute("SELECT COUNT(*) c FROM risk_register WHERE project_id=? AND risk_level IN ('High','Critical')", (project_id,)).fetchone()["c"]
    recs = con.execute("SELECT COUNT(*) c FROM recommendations WHERE project_id=?", (project_id,)).fetchone()["c"]
    md_count = len(missing_items(p))
    completeness = data_completeness(p)
    traffic = "Green"
    if high or completeness < 90:
        traffic = "Amber"
    if any(r["risk_level"] == "Critical" for r in con.execute("SELECT risk_level FROM risk_register WHERE project_id=?", (project_id,))) or completeness < 70:
        traffic = "Red"
    decision = "APPROVE WITH CONDITIONS"
    if traffic == "Green" and sroi and sroi["sroi_ratio"] >= 1.0:
        decision = "CONTINUE PILOT"
    if traffic == "Red":
        decision = "PAUSE"
    stage_pct = round(len(approved) / len(STAGES) * 100, 1)
    return {
        "current_stage": next_unapproved_stage(con, project_id),
        "stage_completion_percentage": stage_pct,
        "data_completeness_score": completeness,
        "evidence_confidence_level": "B/C mixed; external validation required",
        "total_investment": float_or_zero(p["budget_or_investment_value"]),
        "total_present_value": float_or_zero(sroi["total_present_value"]) if sroi else 0,
        "net_social_value": float_or_zero(sroi["net_social_value"]) if sroi else 0,
        "sroi_ratio": float_or_zero(sroi["sroi_ratio"]) if sroi else 0,
        "number_of_beneficiaries": int_or_zero(p["expected_number_of_beneficiaries"]),
        "cost_per_beneficiary": cost_per_beneficiary(p),
        "key_outcomes": p["expected_outcomes"],
        "number_of_risks": risks,
        "high_critical_risks": high,
        "missing_data_items": md_count,
        "number_of_recommendations": recs,
        "pending_approvals": ", ".join([s[0] for s in STAGES if s[0] not in approved]),
        "final_decision_recommendation": decision,
        "traffic_light_status": traffic,
    }


def report_stage06(con, project_id):
    vals = dashboard_values(con, project_id)
    p = project(con, project_id)
    con.execute("DELETE FROM dashboard WHERE project_id=?", (project_id,))
    con.execute(
        """INSERT INTO dashboard VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid("DSH"), project_id, vals["current_stage"], vals["stage_completion_percentage"], vals["data_completeness_score"], vals["evidence_confidence_level"], vals["total_investment"], vals["total_present_value"], vals["net_social_value"], vals["sroi_ratio"], vals["number_of_beneficiaries"], vals["cost_per_beneficiary"], vals["key_outcomes"], vals["number_of_risks"], vals["high_critical_risks"], vals["missing_data_items"], vals["number_of_recommendations"], vals["pending_approvals"], vals["final_decision_recommendation"], vals["traffic_light_status"], now()),
    )
    body = report_header(con, project_id, "Prototype Executive Dashboard and Impact Decision Brief")
    body += f"""## Executive Dashboard
- Current Stage: {vals['current_stage']}
- Stage Completion: {vals['stage_completion_percentage']}%
- Data Completeness: {vals['data_completeness_score']}%
- Evidence Confidence: {vals['evidence_confidence_level']}
- Total Investment: {vals['total_investment']:,.2f}
- Total Present Value of Social Benefits: {vals['total_present_value']:,.2f}
- Net Social Value: {vals['net_social_value']:,.2f}
- SROI Ratio: {vals['sroi_ratio']:.2f}:1
- Beneficiaries: {vals['number_of_beneficiaries']:,}
- Cost per Beneficiary: {vals['cost_per_beneficiary']:,.2f}
- Risks: {vals['number_of_risks']} total; {vals['high_critical_risks']} high/critical
- Missing Data Items: {vals['missing_data_items']}
- Recommendations: {vals['number_of_recommendations']}
- Traffic Light: {vals['traffic_light_status']}

## Impact Decision Brief
### Project Profile
{p['project_name']} is a {p['project_type']} project owned by {p['owning_entity']} and assessed as a {p['study_type']} study.

### Study Scope
One pilot project only. No ERP, CRM, portfolio analytics, external assurance, or government integration is included in Prototype v1.

### Data Quality
Data completeness is {vals['data_completeness_score']}%. Evidence confidence is {vals['evidence_confidence_level']}.

### Theory of Change Summary
The project links resources and activities to outputs, beneficiary outcomes, and long-term social impact. Assumptions require management validation.

### KPI Summary
Core KPIs include beneficiaries served, cost per beneficiary, and outcome achievement rate.

### SROI Result
The estimated SROI ratio is {vals['sroi_ratio']:.2f}:1 with net social value of {vals['net_social_value']:,.2f}.

### Key Risks
High or critical risks: {vals['high_critical_risks']}.

### Proposed Management Decision
{vals['final_decision_recommendation']}

### Conditions Before Approval
- Validate assumptions and evidence before external reporting.
- Approve or revise all management gates.
- Replace prototype assumptions with verified data where available.

### Evidence and Limitations
SROI does not stand alone. Decision-making must consider evidence quality, data completeness, risks, sustainability, implementation readiness, and management judgement.

Management approval required before implementation.
"""
    return body


def approve_stage(project_id, stage_id, approver, comments):
    with db() as con:
        upsert_stage_gate(con, project_id, stage_id, "Approved", "Approved", comments)
        next_stage = stage_after(stage_id)
        token = update_memory(con, project_id, next_stage, "Ready" if next_stage != "COMPLETE" else "Closed", f"Run {next_stage}" if next_stage != "COMPLETE" else "Management review complete.")
        con.execute("UPDATE agent_log SET approval_status='Approved', resume_token=? WHERE project_id=? AND stage_id=?", (token, project_id, stage_id))
        return token


def revise_stage(project_id, stage_id, comments):
    with db() as con:
        token = upsert_stage_gate(con, project_id, stage_id, "Needs Revision", "Needs Revision", comments, comments)
        update_memory(con, project_id, stage_id, "Needs Revision", "Revise stage output and rerun the stage.")
        return token


def add_uploaded_document(project_id, field_storage):
    fileitem = field_storage["file"]
    filename = os.path.basename(fileitem.filename or "upload.txt")
    folder = UPLOADS_DIR / project_id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    with target.open("wb") as f:
        shutil.copyfileobj(fileitem.file, f)
    text = extract_text(target)
    inferred = infer_fields_from_text(text)
    with db() as con:
        con.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
            (uid("DOC"), project_id, filename, target.suffix.lower(), now(), str(target), text, 0),
        )
        for key, val in inferred.items():
            if key in ["budget_or_investment_value", "expected_number_of_beneficiaries"]:
                if float_or_zero(project(con, project_id).get(key)) <= 0:
                    con.execute(f"UPDATE projects SET {key}=?, updated_at=? WHERE project_id=?", (float_or_zero(val), now(), project_id))
            elif not (project(con, project_id).get(key) or "").strip():
                con.execute(f"UPDATE projects SET {key}=?, updated_at=? WHERE project_id=?", (val, now(), project_id))
        update_memory(con, project_id, project(con, project_id)["current_stage"], "Document Uploaded", "Run STAGE02 when ready.")
    return {"file": filename, "extracted_chars": len(text), "inferred": inferred}


def list_projects():
    with db() as con:
        return [dict(r) for r in con.execute("SELECT project_id, project_name, current_stage, current_status, updated_at FROM projects ORDER BY created_at DESC")]


def status_payload(project_id):
    with db() as con:
        p = project(con, project_id)
        if not p:
            return {}
        gates = [dict(r) for r in con.execute("SELECT * FROM stage_gates WHERE project_id=? ORDER BY stage_id", (project_id,))]
        memory = dict_row(con.execute("SELECT * FROM project_memory WHERE project_id=? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone())
        reports = [dict(r) for r in con.execute("SELECT report_id,stage_id,report_name,file_path,created_at FROM reports WHERE project_id=? ORDER BY created_at DESC", (project_id,))]
        dash = dict_row(con.execute("SELECT * FROM dashboard WHERE project_id=? ORDER BY generated_at DESC LIMIT 1", (project_id,)).fetchone())
        return {"project": p, "gates": gates, "memory": memory, "reports": reports, "dashboard": dash, "next_stage": next_unapproved_stage(con, project_id)}


def seed_demo():
    data = {
        "project_name": "مشروع كفالة ورعاية الأيتام",
        "project_type": "Orphan sponsorship project",
        "study_type": "Ex-ante / Forecast",
        "owning_entity": "مؤسسة وقفية تجريبية",
        "project_owner": "مدير البرامج",
        "study_manager": "مدير قياس الأثر",
        "department": "إدارة المشاريع الخيرية",
        "location": "دبي",
        "implementation_period": "2026",
        "budget_or_investment_value": "500000",
        "funding_source": "Waqf income",
        "waqf_or_charity_category": "Social welfare",
        "target_beneficiaries": "الأيتام وأسرهم",
        "expected_number_of_beneficiaries": "250",
        "problem_or_social_need": "الحاجة إلى دعم معيشي وتعليمي مستقر للأيتام.",
        "project_objectives": "تحسين الاستقرار المعيشي والتعليمي للمستفيدين.",
        "main_activities": "دعم مالي، متابعة تعليمية، إرشاد أسري.",
        "expected_outputs": "صرف المساعدات وتنفيذ جلسات المتابعة.",
        "expected_outcomes": "تحسن الاستقرار الأسري والاستمرار التعليمي.",
        "available_kpis": "عدد المستفيدين، نسبة الاستمرار التعليمي.",
        "available_evidence": "سجلات داخلية وطلبات مستفيدين.",
        "management_decision_required": "Continue pilot or approve with conditions.",
        "initial_risks": "جودة البيانات، اعتماد الوكيل المالي.",
        "missing_data": "Financial proxy requires validation.",
        "confidentiality_level": "High",
        "beneficiary_privacy_requirements": "Mask beneficiary identities in reports.",
        "project_opening_approval_status": "Draft",
    }
    return create_project(data)


HTML_PAGE = r"""
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Waqf & Charity Impact Intelligence Prototype</title>
  <style>
    :root { --ink:#17211b; --muted:#5d6760; --line:#d9ded8; --bg:#f7f8f5; --panel:#fff; --accent:#0b6b57; --amber:#a76b00; --red:#9f2530; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif; background:var(--bg); color:var(--ink); }
    header { background:#ffffff; border-bottom:1px solid var(--line); padding:18px 28px; position:sticky; top:0; z-index:2; }
    h1 { margin:0; font-size:22px; letter-spacing:0; }
    .subtitle { color:var(--muted); margin-top:4px; font-size:13px; }
    main { max-width:1280px; margin:0 auto; padding:22px; display:grid; grid-template-columns:320px 1fr; gap:18px; }
    section, aside { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }
    h2 { margin:0 0 12px; font-size:18px; }
    h3 { margin:18px 0 8px; font-size:15px; }
    label { display:block; color:var(--muted); font-size:12px; margin:8px 0 4px; }
    input, textarea, select { width:100%; border:1px solid var(--line); border-radius:6px; padding:9px; background:#fff; color:var(--ink); font:inherit; }
    textarea { min-height:70px; resize:vertical; }
    button { border:0; border-radius:6px; padding:9px 12px; background:var(--accent); color:white; cursor:pointer; font-weight:600; margin:4px 0; }
    button.secondary { background:#3c4941; }
    button.warn { background:var(--amber); }
    button.danger { background:var(--red); }
    button.ghost { background:#eef2ee; color:var(--ink); }
    .row { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
    .row3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
    .toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:12px; }
    .project { padding:10px; border:1px solid var(--line); border-radius:6px; margin-bottom:8px; cursor:pointer; background:#fbfcfa; }
    .project.active { border-color:var(--accent); box-shadow:0 0 0 2px rgba(11,107,87,.12); }
    .pill { display:inline-flex; align-items:center; border-radius:999px; padding:3px 8px; font-size:12px; background:#eef2ee; color:#2f4037; margin:2px; }
    .metric-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
    .metric { border:1px solid var(--line); border-radius:8px; padding:12px; background:#fbfcfa; min-height:82px; }
    .metric .label { color:var(--muted); font-size:12px; }
    .metric .value { font-size:20px; font-weight:700; margin-top:8px; overflow-wrap:anywhere; }
    pre { white-space:pre-wrap; direction:ltr; text-align:left; background:#111a15; color:#eef8f2; border-radius:8px; padding:14px; overflow:auto; max-height:540px; }
    .report { direction:rtl; text-align:right; white-space:pre-wrap; background:#fbfcfa; border:1px solid var(--line); border-radius:8px; padding:14px; max-height:620px; overflow:auto; }
    .gate { display:grid; grid-template-columns:90px 1fr 120px; gap:8px; align-items:center; border-bottom:1px solid var(--line); padding:8px 0; }
    .status-Approved { color:var(--accent); font-weight:700; }
    .status-Under { color:var(--amber); font-weight:700; }
    .status-Needs { color:var(--red); font-weight:700; }
    .ltr { direction:ltr; text-align:left; }
    .small { color:var(--muted); font-size:12px; }
    @media (max-width:900px){ main{grid-template-columns:1fr;} .metric-grid,.row3,.row{grid-template-columns:1fr;} header{position:static;} }
  </style>
</head>
<body>
<header>
  <h1>منصة الذكاء الاصطناعي لتقييم وإدارة الأثر الوقفي والخيري</h1>
  <div class="subtitle">Waqf & Charity Impact Intelligence Prototype · Stage-gate governance · SROI · Evidence registers · Audit trail</div>
</header>
<main>
  <aside>
    <h2>المشاريع</h2>
    <button onclick="seedDemo()">إنشاء مشروع تجريبي</button>
    <button class="ghost" onclick="refresh()">تحديث</button>
    <div id="projects"></div>
  </aside>
  <section>
    <div class="toolbar">
      <button onclick="runNext()">RUN NEXT STAGE</button>
      <button class="secondary" onclick="approve()">APPROVE STAGE</button>
      <button class="warn" onclick="revise()">REVISE STAGE</button>
      <button class="secondary" onclick="showStatus()">SHOW STATUS</button>
      <button class="secondary" onclick="generateDashboard()">GENERATE DASHBOARD</button>
      <button class="danger" onclick="pauseProject()">PAUSE</button>
    </div>
    <div id="status"></div>
    <h2>نموذج فتح مشروع وطلب تقييم الأثر</h2>
    <form id="projectForm">
      <div class="row3">
        <div><label>Project Name</label><input name="project_name" required></div>
        <div><label>Project Type</label><select name="project_type"><option>Orphan sponsorship project</option><option>Water waqf project</option><option>Family support project</option><option>Education or Quran memorisation project</option><option>Health or social empowerment project</option><option>Waqf real-estate income project</option></select></div>
        <div><label>Study Type</label><select name="study_type"><option>Ex-ante / Forecast</option><option>Monitoring</option><option>Ex-post / Evaluative</option><option>Hybrid</option></select></div>
      </div>
      <div class="row3">
        <div><label>Owning Entity</label><input name="owning_entity"></div>
        <div><label>Project Owner</label><input name="project_owner"></div>
        <div><label>Study Manager</label><input name="study_manager"></div>
      </div>
      <div class="row3">
        <div><label>Department</label><input name="department"></div>
        <div><label>Location</label><input name="location"></div>
        <div><label>Implementation Period</label><input name="implementation_period"></div>
      </div>
      <div class="row3">
        <div><label>Budget or Investment Value</label><input name="budget_or_investment_value" type="number"></div>
        <div><label>Funding Source</label><input name="funding_source"></div>
        <div><label>Waqf or Charity Category</label><input name="waqf_or_charity_category"></div>
      </div>
      <div class="row3">
        <div><label>Target Beneficiaries</label><input name="target_beneficiaries"></div>
        <div><label>Expected Number of Beneficiaries</label><input name="expected_number_of_beneficiaries" type="number"></div>
        <div><label>Confidentiality Level</label><select name="confidentiality_level"><option>High</option><option>Medium</option><option>Low</option></select></div>
      </div>
      <label>Problem or Social Need</label><textarea name="problem_or_social_need"></textarea>
      <label>Project Objectives</label><textarea name="project_objectives"></textarea>
      <div class="row">
        <div><label>Main Activities</label><textarea name="main_activities"></textarea></div>
        <div><label>Expected Outputs</label><textarea name="expected_outputs"></textarea></div>
      </div>
      <label>Expected Outcomes</label><textarea name="expected_outcomes"></textarea>
      <div class="row">
        <div><label>Available KPIs</label><textarea name="available_kpis"></textarea></div>
        <div><label>Available Evidence</label><textarea name="available_evidence"></textarea></div>
      </div>
      <div class="row">
        <div><label>Management Decision Required</label><textarea name="management_decision_required"></textarea></div>
        <div><label>Initial Risks</label><textarea name="initial_risks"></textarea></div>
      </div>
      <div class="row">
        <div><label>Missing Data</label><textarea name="missing_data"></textarea></div>
        <div><label>Beneficiary Privacy Requirements</label><textarea name="beneficiary_privacy_requirements"></textarea></div>
      </div>
      <label>Project Opening Approval Status</label><select name="project_opening_approval_status"><option>Draft</option><option>Under Review</option><option>Approved</option></select>
      <button type="submit">START PROJECT ASSESSMENT</button>
    </form>
    <h3>UPLOAD PROJECT DOCUMENT</h3>
    <form id="uploadForm">
      <input type="file" name="file">
      <button type="submit" class="secondary">رفع الوثيقة</button>
    </form>
    <h3>Stage Gates</h3>
    <div id="gates"></div>
    <h3>Dashboard</h3>
    <div id="dashboard"></div>
    <h3>آخر تقرير</h3>
    <div id="report" class="report">لم يتم تشغيل أي مرحلة بعد.</div>
  </section>
</main>
<script>
let selectedProject = null;
let selectedStage = null;

async function api(path, opts={}) {
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error || res.statusText);
  return data;
}
function esc(s){ return String(s ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])); }
function money(n){ return Number(n||0).toLocaleString(undefined,{maximumFractionDigits:2}); }

async function refresh() {
  const data = await api('/api/projects');
  const box = document.getElementById('projects');
  box.innerHTML = data.projects.map(p => `<div class="project ${p.project_id===selectedProject?'active':''}" onclick="selectProject('${p.project_id}')">
    <b class="ltr">${p.project_id}</b><br>${esc(p.project_name || 'Untitled')}<br>
    <span class="pill">${esc(p.current_stage)}</span><span class="pill">${esc(p.current_status)}</span>
  </div>`).join('');
  if (!selectedProject && data.projects.length) selectProject(data.projects[0].project_id);
}

async function selectProject(id) {
  selectedProject = id;
  await showStatus();
  await refresh();
}

async function showStatus() {
  if (!selectedProject) return;
  const data = await api('/api/status?project_id='+encodeURIComponent(selectedProject));
  const p = data.project;
  selectedStage = data.next_stage === 'COMPLETE' ? 'STAGE06' : data.next_stage;
  document.getElementById('status').innerHTML = `<div class="metric-grid">
    <div class="metric"><div class="label">Project_ID</div><div class="value ltr">${esc(p.project_id)}</div></div>
    <div class="metric"><div class="label">Current Status</div><div class="value">${esc(p.current_status)}</div></div>
    <div class="metric"><div class="label">Next Stage</div><div class="value ltr">${esc(data.next_stage)}</div></div>
    <div class="metric"><div class="label">Resume Token</div><div class="value ltr" style="font-size:13px">${esc(data.memory?.resume_token || '')}</div></div>
  </div>`;
  document.getElementById('gates').innerHTML = data.gates.map(g => `<div class="gate"><b class="ltr">${g.stage_id}</b><span>${esc(g.stage_name)}</span><span class="status-${esc((g.stage_status||'').split(' ')[0])}">${esc(g.stage_status)}</span></div>`).join('') || '<span class="small">لا توجد بوابات بعد.</span>';
  if (data.dashboard) {
    const d = data.dashboard;
    document.getElementById('dashboard').innerHTML = `<div class="metric-grid">
      <div class="metric"><div class="label">Traffic Light</div><div class="value">${esc(d.traffic_light_status)}</div></div>
      <div class="metric"><div class="label">SROI</div><div class="value">${Number(d.sroi_ratio||0).toFixed(2)}:1</div></div>
      <div class="metric"><div class="label">Net Social Value</div><div class="value">${money(d.net_social_value)}</div></div>
      <div class="metric"><div class="label">Decision</div><div class="value" style="font-size:16px">${esc(d.final_decision_recommendation)}</div></div>
    </div>`;
  } else {
    document.getElementById('dashboard').innerHTML = '<span class="small">لم يتم إنشاء لوحة القيادة بعد.</span>';
  }
  if (data.reports.length) document.getElementById('report').innerText = await (await fetch('/api/report?report_id='+data.reports[0].report_id)).text();
}

document.getElementById('projectForm').addEventListener('submit', async e => {
  e.preventDefault();
  const form = new FormData(e.target);
  const payload = Object.fromEntries(form.entries());
  const data = await api('/api/create_project', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  selectedProject = data.project_id;
  await refresh();
  await showStatus();
});

document.getElementById('uploadForm').addEventListener('submit', async e => {
  e.preventDefault();
  if (!selectedProject) return alert('اختر مشروعاً أولاً');
  const form = new FormData(e.target);
  form.append('project_id', selectedProject);
  const data = await api('/api/upload', {method:'POST', body:form});
  document.getElementById('report').innerText = 'Uploaded: '+data.file+'\nExtracted chars: '+data.extracted_chars+'\nInferred: '+JSON.stringify(data.inferred, null, 2);
  await showStatus();
});

async function seedDemo(){ const d = await api('/api/seed_demo',{method:'POST'}); selectedProject=d.project_id; await refresh(); await showStatus(); }
async function runNext(){ if(!selectedProject)return alert('اختر مشروعاً'); const d=await api('/api/run_next',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:selectedProject})}); selectedStage=d.stage_id; document.getElementById('report').innerText=d.report||d.message; await showStatus(); }
async function generateDashboard(){ if(!selectedProject)return; const d=await api('/api/run_stage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:selectedProject,stage_id:'STAGE06'})}); document.getElementById('report').innerText=d.report; await showStatus(); }
async function approve(){ if(!selectedProject)return; const st=prompt('Stage to approve', selectedStage || 'STAGE00'); if(!st)return; const comments=prompt('Approval comments','Approved for prototype workflow')||''; const d=await api('/api/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:selectedProject,stage_id:st,approver:'Management Reviewer',comments})}); document.getElementById('report').innerText='Stage approved.\nResume Token: '+d.resume_token; await showStatus(); }
async function revise(){ if(!selectedProject)return; const st=prompt('Stage to revise', selectedStage || 'STAGE00'); if(!st)return; const comments=prompt('Revision comments','Please revise assumptions/evidence')||''; const d=await api('/api/revise',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:selectedProject,stage_id:st,comments})}); document.getElementById('report').innerText='Stage marked Needs Revision.\nResume Token: '+d.resume_token; await showStatus(); }
async function pauseProject(){ if(!selectedProject)return; const d=await api('/api/pause',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_id:selectedProject})}); document.getElementById('report').innerText='Project paused.\nResume Token: '+d.resume_token; await showStatus(); }
refresh().catch(e=>alert(e.message));
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (now(), fmt % args))

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                data = HTML_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif parsed.path == "/api/projects":
                self.send_json({"projects": list_projects()})
            elif parsed.path == "/api/status":
                qs = parse_qs(parsed.query)
                self.send_json(status_payload(qs.get("project_id", [""])[0]))
            elif parsed.path == "/api/report":
                qs = parse_qs(parsed.query)
                report_id = qs.get("report_id", [""])[0]
                with db() as con:
                    row = con.execute("SELECT content FROM reports WHERE report_id=?", (report_id,)).fetchone()
                data = (row["content"] if row else "Report not found").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e), "trace": traceback.format_exc()}, 500)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/create_project":
                payload = self.read_json()
                self.send_json({"project_id": create_project(payload)})
            elif parsed.path == "/api/seed_demo":
                self.send_json({"project_id": seed_demo()})
            elif parsed.path == "/api/run_next":
                payload = self.read_json()
                self.send_json(run_stage(payload["project_id"]))
            elif parsed.path == "/api/run_stage":
                payload = self.read_json()
                self.send_json(run_stage(payload["project_id"], payload["stage_id"]))
            elif parsed.path == "/api/approve":
                payload = self.read_json()
                token = approve_stage(payload["project_id"], payload["stage_id"], payload.get("approver", "Management Reviewer"), payload.get("comments", ""))
                self.send_json({"resume_token": token})
            elif parsed.path == "/api/revise":
                payload = self.read_json()
                token = revise_stage(payload["project_id"], payload["stage_id"], payload.get("comments", ""))
                self.send_json({"resume_token": token})
            elif parsed.path == "/api/pause":
                payload = self.read_json()
                with db() as con:
                    stage_id = project(con, payload["project_id"])["current_stage"]
                    token = upsert_stage_gate(con, payload["project_id"], stage_id, "Suspended", "Paused", "Paused by user")
                    update_memory(con, payload["project_id"], stage_id, "Suspended", "RESUME PROJECT ASSESSMENT with token.")
                self.send_json({"resume_token": token})
            elif parsed.path == "/api/upload":
                if cgi is None:
                    raise RuntimeError("The legacy HTTP upload endpoint requires Python 3.12 or earlier. Use streamlit_app.py for uploads on Streamlit Cloud.")
                form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type")})
                project_id = form.getvalue("project_id")
                if not project_id or "file" not in form:
                    raise ValueError("project_id and file are required")
                self.send_json(add_uploaded_document(project_id, form))
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e), "trace": traceback.format_exc()}, 500)


def main():
    init_db()
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Waqf & Charity Impact Intelligence Prototype running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
