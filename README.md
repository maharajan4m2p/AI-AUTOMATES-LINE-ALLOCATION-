# Sewing Line AI — Apply Workflow + Attendance Details

This version keeps the selected-line workflow and APPLY & ANALYSE button. Punching Machine Data is compulsory for allocation. A separate ATTENDANCE DETAILS button opens attendance.

Important allocation rule: APPLY & ANALYSE uses only Employee IDs that have at least one punch record on the selected allocation date. Employees without a punch record that date are excluded from allocation recommendations.

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
