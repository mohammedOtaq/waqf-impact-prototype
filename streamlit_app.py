import io
import json
import os
import re
import shutil
from pathlib import Path

import streamlit as st

import app as core


st.set_page_config(
    page_title="Waqf & Charity Impact Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def money(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "0.00"


def save_uploaded_document(project_id, uploaded_file):
    folder = core.UPLOADS_DIR / project_id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    text = core.extract_text(target)
    inferred = core.infer_fields_from_text(text)

    with core.db() as con:
        con.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
            (
                core.uid("DOC"),
                project_id,
                uploaded_file.name,
                target.suffix.lower(),
                core.now(),
                str(target),
                text,
                0,
            ),
        )
        p = core.project(con, project_id)
        for key, val in inferred.items():
            if key in ["budget_or_investment_value", "expected_number_of_beneficiaries"]:
                if core.float_or_zero(p.get(key)) <= 0:
                    con.execute(
                        f"UPDATE projects SET {key}=?, updated_at=? WHERE project_id=?",
                        (core.float_or_zero(val), core.now(), project_id),
                    )
            elif not (p.get(key) or "").strip():
                con.execute(
                    f"UPDATE projects SET {key}=?, updated_at=? WHERE project_id=?",
                    (val, core.now(), project_id),
                )
        updated_project = core.project(con, project_id)
        core.update_memory(
            con,
            project_id,
            updated_project["current_stage"],
            "Document Uploaded",
            "Run STAGE02 when ready.",
        )
    return text, inferred


def report_markdown(report_id):
    with core.db() as con:
        row = con.execute("SELECT content FROM reports WHERE report_id=?", (report_id,)).fetchone()
    return row["content"] if row else "Report not found."


def show_project_picker():
    projects = core.list_projects()
    if not projects:
        st.info("No projects yet. Create a project or seed the demo.")
        return None

    ids = [p["project_id"] for p in projects]
    labels = {
        p["project_id"]: f"{p['project_id']} · {p['project_name'] or 'Untitled'} · {p['current_stage']} · {p['current_status']}"
        for p in projects
    }
    default_index = 0
    if st.session_state.get("project_id") in ids:
        default_index = ids.index(st.session_state["project_id"])
    selected = st.sidebar.selectbox(
        "Project",
        ids,
        index=default_index,
        format_func=lambda pid: labels[pid],
    )
    st.session_state["project_id"] = selected
    return selected


def project_form():
    st.subheader("Project Opening and Impact Assessment Request Form")
    with st.form("project_opening_form"):
        c1, c2, c3 = st.columns(3)
        project_name = c1.text_input("Project_Name")
        project_type = c2.selectbox(
            "Project_Type",
            [
                "Orphan sponsorship project",
                "Water waqf project",
                "Waqf real-estate income project",
                "Family support project",
                "Education or Quran memorisation project",
                "Health or social empowerment project",
            ],
        )
        study_type = c3.selectbox(
            "Study_Type",
            ["Ex-ante / Forecast", "Monitoring", "Ex-post / Evaluative", "Hybrid"],
        )

        c1, c2, c3 = st.columns(3)
        owning_entity = c1.text_input("Owning_Entity")
        project_owner = c2.text_input("Project_Owner")
        study_manager = c3.text_input("Study_Manager")

        c1, c2, c3 = st.columns(3)
        department = c1.text_input("Department")
        location = c2.text_input("Location")
        implementation_period = c3.text_input("Implementation_Period")

        c1, c2, c3 = st.columns(3)
        budget = c1.number_input("Budget_or_Investment_Value", min_value=0.0, step=1000.0)
        funding_source = c2.text_input("Funding_Source")
        category = c3.text_input("Waqf_or_Charity_Category")

        c1, c2, c3 = st.columns(3)
        target_beneficiaries = c1.text_input("Target_Beneficiaries")
        beneficiaries = c2.number_input("Expected_Number_of_Beneficiaries", min_value=0, step=1)
        confidentiality = c3.selectbox("Confidentiality_Level", ["High", "Medium", "Low"])

        problem = st.text_area("Problem_or_Social_Need")
        objectives = st.text_area("Project_Objectives")

        c1, c2 = st.columns(2)
        activities = c1.text_area("Main_Activities")
        outputs = c2.text_area("Expected_Outputs")

        outcomes = st.text_area("Expected_Outcomes")

        c1, c2 = st.columns(2)
        kpis = c1.text_area("Available_KPIs")
        evidence = c2.text_area("Available_Evidence")

        c1, c2 = st.columns(2)
        decision = c1.text_area("Management_Decision_Required")
        risks = c2.text_area("Initial_Risks")

        c1, c2 = st.columns(2)
        missing = c1.text_area("Missing_Data")
        privacy = c2.text_area("Beneficiary_Privacy_Requirements")

        approval = st.selectbox("Project_Opening_Approval_Status", ["Draft", "Under Review", "Approved"])
        submitted = st.form_submit_button("START PROJECT ASSESSMENT", type="primary")

    if submitted:
        payload = {
            "project_name": project_name,
            "project_type": project_type,
            "study_type": study_type,
            "owning_entity": owning_entity,
            "project_owner": project_owner,
            "study_manager": study_manager,
            "department": department,
            "location": location,
            "implementation_period": implementation_period,
            "budget_or_investment_value": budget,
            "funding_source": funding_source,
            "waqf_or_charity_category": category,
            "target_beneficiaries": target_beneficiaries,
            "expected_number_of_beneficiaries": beneficiaries,
            "problem_or_social_need": problem,
            "project_objectives": objectives,
            "main_activities": activities,
            "expected_outputs": outputs,
            "expected_outcomes": outcomes,
            "available_kpis": kpis,
            "available_evidence": evidence,
            "management_decision_required": decision,
            "initial_risks": risks,
            "missing_data": missing,
            "confidentiality_level": confidentiality,
            "beneficiary_privacy_requirements": privacy,
            "project_opening_approval_status": approval,
        }
        project_id = core.create_project(payload)
        st.session_state["project_id"] = project_id
        st.success(f"Project created: {project_id}")
        st.rerun()


def status_panel(project_id):
    data = core.status_payload(project_id)
    p = data["project"]
    memory = data.get("memory") or {}
    dash = data.get("dashboard")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Project_ID", p["project_id"])
    c2.metric("Current Status", p["current_status"])
    c3.metric("Next Stage", data["next_stage"])
    c4.metric("Memory Version", memory.get("memory_version", "M001"))
    st.caption(f"Resume Token: `{memory.get('resume_token', '')}`")

    if dash:
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Traffic Light", dash["traffic_light_status"])
        c2.metric("SROI Ratio", f"{float(dash['sroi_ratio'] or 0):.2f}:1")
        c3.metric("Net Social Value", money(dash["net_social_value"]))
        c4.metric("Decision", dash["final_decision_recommendation"])


def workflow_panel(project_id):
    data = core.status_payload(project_id)
    next_stage = data["next_stage"]

    st.subheader("Stage-Gate Workflow")
    cols = st.columns([1, 1, 1, 1])
    if cols[0].button("RUN NEXT STAGE", type="primary", use_container_width=True, disabled=next_stage == "COMPLETE"):
        try:
            result = core.run_stage(project_id)
            st.session_state["last_report"] = result.get("report", result.get("message", ""))
            st.success(f"Generated {result.get('stage_id')}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    stage_options = [stage[0] for stage in core.STAGES]
    default_stage = next_stage if next_stage in stage_options else "STAGE06"
    chosen_stage = cols[1].selectbox("Stage", stage_options, index=stage_options.index(default_stage), label_visibility="collapsed")

    if cols[2].button("APPROVE STAGE", use_container_width=True):
        token = core.approve_stage(project_id, chosen_stage, "Management Reviewer", "Approved through Streamlit UI")
        st.success(f"Approved. Resume token: {token}")
        st.rerun()

    if cols[3].button("REVISE STAGE", use_container_width=True):
        token = core.revise_stage(project_id, chosen_stage, "Revision requested through Streamlit UI")
        st.warning(f"Needs revision. Resume token: {token}")
        st.rerun()

    gate_rows = data["gates"]
    if gate_rows:
        st.dataframe(
            [
                {
                    "Stage": g["stage_id"],
                    "Name": g["stage_name"],
                    "Lead Agent": g["lead_agent"],
                    "Status": g["stage_status"],
                    "Decision": g["approval_decision"],
                    "Resume Token": g["resume_token"],
                }
                for g in gate_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No stage gates yet. Run Stage 00 to begin.")


def upload_panel(project_id):
    st.subheader("UPLOAD PROJECT DOCUMENT")
    uploaded = st.file_uploader("Upload PDF, DOCX, XLSX, CSV, TXT, or MD", type=["pdf", "docx", "xlsx", "xlsm", "csv", "txt", "md"])
    if uploaded and st.button("Save Document", type="primary"):
        text, inferred = save_uploaded_document(project_id, uploaded)
        st.success(f"Uploaded {uploaded.name}. Extracted {len(text)} characters.")
        if inferred:
            st.json(inferred)
        else:
            st.info("No opening-form fields were inferred automatically.")


def dashboard_panel(project_id):
    st.subheader("Executive Dashboard")
    data = core.status_payload(project_id)
    dash = data.get("dashboard")
    if not dash:
        st.info("Generate STAGE06 after approving prior stages to create the dashboard.")
        if st.button("GENERATE DASHBOARD / DECISION BRIEF"):
            try:
                result = core.run_stage(project_id, "STAGE06")
                st.session_state["last_report"] = result["report"]
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stage Completion", f"{dash['stage_completion_percentage']}%")
    c2.metric("Data Completeness", f"{dash['data_completeness_score']}%")
    c3.metric("High/Critical Risks", dash["high_critical_risks"])
    c4.metric("Recommendations", dash["number_of_recommendations"])

    st.dataframe([dict(dash)], use_container_width=True, hide_index=True)


def reports_panel(project_id):
    st.subheader("Reports")
    data = core.status_payload(project_id)
    reports = data["reports"]
    if not reports:
        st.info("No reports yet.")
        return
    selected = st.selectbox(
        "Report",
        reports,
        format_func=lambda r: f"{r['stage_id']} · {r['report_name']} · {r['created_at']}",
    )
    content = report_markdown(selected["report_id"])
    st.download_button(
        "Download Markdown",
        content.encode("utf-8"),
        file_name=Path(selected["file_path"]).name,
        mime="text/markdown",
    )
    st.markdown(content)


def deployment_panel():
    st.subheader("Deployment Notes")
    st.markdown(
        """
1. Push this folder to GitHub.
2. In Streamlit Community Cloud, create a new app from the GitHub repo.
3. Set the entrypoint to `streamlit_app.py`.
4. Keep secrets out of the repo. Add secrets in Streamlit Cloud settings only.

This prototype uses local SQLite. That is fine for a demo, but production should move state to PostgreSQL, Supabase, or another persistent database.
"""
    )


core.init_db()

st.title("Waqf and Charity Impact Intelligence Prototype")
st.caption("Waqf & Charity Impact Intelligence Prototype · Streamlit deployment build")

with st.sidebar:
    st.header("Control")
    if st.button("Create Demo Project", use_container_width=True):
        project_id = core.seed_demo()
        st.session_state["project_id"] = project_id
        st.success(project_id)
        st.rerun()
    selected_project = show_project_picker()

tab_create, tab_workflow, tab_upload, tab_dashboard, tab_reports, tab_deploy = st.tabs(
    ["New Project", "Workflow", "Upload", "Dashboard", "Reports", "Deploy"]
)

with tab_create:
    project_form()

if selected_project:
    with tab_workflow:
        status_panel(selected_project)
        workflow_panel(selected_project)
        if st.session_state.get("last_report"):
            st.markdown("### Last Generated Report")
            st.markdown(st.session_state["last_report"])
    with tab_upload:
        upload_panel(selected_project)
    with tab_dashboard:
        dashboard_panel(selected_project)
    with tab_reports:
        reports_panel(selected_project)
else:
    for tab in [tab_workflow, tab_upload, tab_dashboard, tab_reports]:
        with tab:
            st.info("Create or select a project first.")

with tab_deploy:
    deployment_panel()
