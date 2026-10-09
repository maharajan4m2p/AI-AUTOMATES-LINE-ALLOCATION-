# Sewing Line AI — Apply Workflow + Attendance Details

<<<<<<< HEAD
This version supports selecting multiple sewing lines in one allocation run. Punching Machine Data is compulsory for allocation. A separate ATTENDANCE DETAILS button opens attendance.

Important allocation rules:
- Allocation uses only Employee IDs that have at least one punch record on the selected allocation date.
- Select one or more sewing lines and click APPLY & ANALYSE SELECTED LINES.
- An employee can be assigned to only one selected line in a single allocation run. Employees allocated to an earlier selected line are excluded from later selected lines.
- If no eligible employee remains for a slot, that slot is shown as Unfilled.
=======
This version keeps the selected-line workflow and APPLY & ANALYSE button. Punching Machine Data is compulsory for allocation. A separate ATTENDANCE DETAILS button opens attendance.

Important allocation rule: APPLY & ANALYSE uses only Employee IDs that have at least one punch record on the selected allocation date. Employees without a punch record that date are excluded from allocation recommendations.
>>>>>>> 7ed376980eda079e94e5400f7bb31e455aceb63c

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
