# Sewing Line AI — Apply Workflow + Attendance Details

This version supports selecting multiple sewing lines in one allocation run. Punching Machine Data is compulsory for allocation. A separate ATTENDANCE DETAILS button opens attendance.

Important allocation rules:
- Allocation uses only Employee IDs that have at least one punch record on the selected allocation date.
- Select one or more sewing lines and click APPLY & ANALYSE SELECTED LINES.
- An employee can be assigned to only one selected line in a single allocation run. Employees allocated to an earlier selected line are excluded from later selected lines.
- If no eligible employee remains for a slot, that slot is shown as Unfilled.

Run locally:
`python -m pip install -r requirements.txt`
`python -m streamlit run app.py`

Render:
Build command: `pip install -r requirements.txt`
Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

Uploads:
- Employee Skills: Employee ID, Employee Name, Operation, Skill (YES/NO)
- Line Machine Details: Line, Machine Type, and Machine ID or Machine Count
- Employee Efficiency: Employee ID, Avg Efficiency
- Staffing Requirements: optional; Line, Operation, Operators Required
- Punching Machine Data: REQUIRED for allocation; Employee ID, Punch Date, Punch Time, optional Punch Type/Machine ID

Attendance rule: Present if an employee ID has at least one punch record on selected date; Absent if in the skills roster with no punch record that day.

Master data persistence:
- Upload Employee Skills, Line Machine Details, Employee Efficiency, and optional Staffing Requirements once. The app saves these files and reloads them automatically on future sessions.
- Upload only the daily Punching Machine Data file each day.
- On Render, attach a persistent disk to the web service and set its mount path to `/var/data`. Without a persistent disk, Render's local filesystem can be cleared on restart/redeploy, so saved master data may be lost.
- To update master data later, upload the changed file in the matching master-data uploader; it replaces the saved version of that master file.
