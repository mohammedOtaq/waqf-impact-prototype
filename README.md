# Waqf & Charity Impact Intelligence Prototype

Functional local prototype for:

**منصة الذكاء الاصطناعي لتقييم وإدارة الأثر الوقفي والخيري**  
**Waqf & Charity Impact Intelligence Prototype**

## Run

```bash
/Users/hdf/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 app.py
```

Then open:

```text
http://127.0.0.1:8765
```

## What It Includes

- Arabic/English project-opening form.
- Uploaded-document register and basic extraction for text, DOCX, and XLSX.
- SQLite database with project, evidence, assumptions, SROI, risks, stage gates, agent log, memory, dashboard, and reports.
- Seven-stage workflow with human approval gates.
- Resume token generation.
- Interim reports for each stage.
- Basic Theory of Change and KPI framework.
- Basic SROI calculation and sensitivity analysis.
- Risk, gap, and recommendation engine.
- Executive dashboard.
- Impact Decision Brief.

## Demo Path

1. Click `إنشاء مشروع تجريبي`.
2. Click `RUN NEXT STAGE`.
3. Click `APPROVE STAGE`.
4. Repeat until `STAGE06`.
5. Review the dashboard and final Impact Decision Brief.

Generated reports are saved in:

```text
reports/interim/
reports/final/
```

The database is saved in:

```text
database/prototype.sqlite
```
