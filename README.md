# Sewing Line AI Operator Allocation — Serial Number Edition

## Features
- Upload only the daily punching file (.xlsx, .xls, .csv, .ods).
- Master employee/skill/efficiency files are bundled; no Supabase required.
- Uses `02_Line_Machine_Details.xlsx` → `Machine Register` as the source of physical machine slots.
- One employee per machine slot and no employee duplication across selected lines.
- Outputs employee name, ID, efficiency, machine serial number, line, operation, and qualification verification status.
- Shows separate line tabs and CSV/Excel downloads.
- Provisional assignments are visibly flagged when skill records or approved machine-to-skill mappings are not verified. A supervisor must verify them before production use.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Render
1. Upload/replace the project files in the GitHub repository root.
2. Keep the Excel master files in the repository root.
3. Commit the changes.
4. In Render, deploy the latest commit.

## Important
- The `Machine Register` sheet has one row per machine slot from the line-count master. If the supplied inventory has no serial number for a slot, it says `Not recorded in machine inventory`; do not treat this as a real serial number.
- The `Machine Skill Mapping` sheet is a template. Add only factory-approved skill-operation mappings.
- The app may assign provisional employees to reduce unfilled slots, but provisional assignment is not proof of qualification. Verify before the operator runs the machine.
