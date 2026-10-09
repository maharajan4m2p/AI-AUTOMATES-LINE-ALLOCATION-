import re
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

def normalize_text(v):
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()

def find_column(df, candidates):
    lookup = {normalize_text(c).lower(): c for c in df.columns}
    for x in candidates:
        if normalize_text(x).lower() in lookup:
            return lookup[normalize_text(x).lower()]
    def compact(x):
        return re.sub(r"[^a-z0-9]", "", normalize_text(x).lower())
    lookup2 = {compact(c): c for c in df.columns}
    for x in candidates:
        if compact(x) in lookup2:
            return lookup2[compact(x)]
    raise ValueError("Could not find columns: " + ", ".join(candidates) + ". Available columns: " + ", ".join(map(str, df.columns)))

def is_yes(v):
    return normalize_text(v).lower() in {"yes", "y", "true", "1", "skilled"}

def to_num(s):
    return pd.to_numeric(s.astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False).str.strip(), errors="coerce")

<<<<<<< HEAD
def recommend_for_line(selected_line, skills, lines, efficiency, requirements, line_col, machine_col, skill_id_col, skill_name_col, skill_op_col, skill_status_col, eff_id_col, eff_col, eligible_employee_ids=None, excluded_employee_ids=None):
=======
def recommend_for_line(selected_line, skills, lines, efficiency, requirements, line_col, machine_col, skill_id_col, skill_name_col, skill_op_col, skill_status_col, eff_id_col, eff_col, eligible_employee_ids=None):
>>>>>>> 7ed376980eda079e94e5400f7bb31e455aceb63c
    target = normalize_text(selected_line).lower()
    line_rows = lines[lines[line_col].map(lambda x: normalize_text(x).lower()) == target].copy()
    line_rows = line_rows[line_rows[machine_col].notna()]
    if line_rows.empty:
        raise ValueError(f"No machine details found for {selected_line}.")

    # Each physical machine row or Machine Count contributes to the displayed machine total.
    machine_id_col = None
    count_col = None
    for candidates in (["Machine ID", "Machine No", "Machine Number", "Equipment ID"],):
        try:
            machine_id_col = find_column(line_rows, candidates)
        except ValueError:
            pass
    try:
        count_col = find_column(line_rows, ["Machine Count", "Number of Machines", "No. of Machines", "Machines", "Machine Qty", "Qty"])
    except ValueError:
        pass

    if count_col:
        line_rows["_machine_count"] = pd.to_numeric(line_rows[count_col], errors="coerce").fillna(0).clip(lower=0)
        machine_count = int(line_rows["_machine_count"].sum())
        machine_counts = line_rows.groupby(line_rows[machine_col].map(normalize_text))["_machine_count"].sum().to_dict()
    elif machine_id_col:
        line_rows["_machine_count"] = 1
        machine_count = len(line_rows)
        machine_counts = line_rows.groupby(line_rows[machine_col].map(normalize_text))["_machine_count"].sum().to_dict()
    else:
        line_rows["_machine_count"] = 1
        machine_counts = line_rows.groupby(line_rows[machine_col].map(normalize_text)).size().to_dict()
        machine_count = len(line_rows)

    ops = sorted([op for op in machine_counts if normalize_text(op)], key=str.lower)
    slots = []
    assumption = None
    if requirements is not None:
        rline = find_column(requirements, ["Line", "Candidate Line"])
        rop = find_column(requirements, ["Operation", "Machine Type", "Required Operation"])
        rcount = find_column(requirements, ["Operators Required", "Required Operators", "Operator Count", "Slots"])
        rr = requirements[requirements[rline].map(lambda x: normalize_text(x).lower()) == target].copy()
        if not rr.empty:
            for _, row in rr.iterrows():
                op = normalize_text(row[rop])
                count = pd.to_numeric(row[rcount], errors="coerce")
                if op and pd.notna(count) and count > 0:
                    # Keep one slot per required operator; machine count is added as context in output.
                    slots.extend([op] * int(count))
        if not slots:
            for op in ops:
                slots.extend([op] * int(machine_counts.get(op, 1)))
            assumption = "No matching staffing requirement found; using machine count as a fallback for operator slots."
    else:
        for op in ops:
            slots.extend([op] * int(machine_counts.get(op, 1)))
        assumption = "No staffing file supplied; using one operator per machine as a fallback. Confirm actual staffing requirements."

    if not slots:
        raise ValueError(f"No operator slots found for {selected_line}.")

    sk = skills.copy()
    sk["_id"] = sk[skill_id_col].map(normalize_text)
    sk["_name"] = sk[skill_name_col].map(normalize_text)
    sk["_op"] = sk[skill_op_col].map(normalize_text)
    sk["_yes"] = sk[skill_status_col].map(is_yes)
    ef = efficiency.copy()
    ef["_id"] = ef[eff_id_col].map(normalize_text)
    ef["_eff"] = to_num(ef[eff_col])
    eff_by = ef[ef["_id"] != ""].groupby("_id")["_eff"].max()
    emp = sk[sk["_id"] != ""].drop_duplicates("_id").sort_values("_name")[["_id", "_name"]].copy()
    emp["_eff"] = emp["_id"].map(eff_by).fillna(0).clip(0, 100)
<<<<<<< HEAD
    if emp.empty:
        raise ValueError("No employees found in Employee Skills.")
=======
>>>>>>> 7ed376980eda079e94e5400f7bb31e455aceb63c
    if eligible_employee_ids is not None:
        allowed = {normalize_text(x) for x in eligible_employee_ids}
        emp = emp[emp["_id"].isin(allowed)].copy()
        if emp.empty:
            raise ValueError("No employees have punch records on the selected date. Check the punching data or choose another date.")
<<<<<<< HEAD
    # Employees assigned to an earlier selected line cannot be reused on another line.
    if excluded_employee_ids:
        excluded = {normalize_text(x) for x in excluded_employee_ids}
        emp = emp[~emp["_id"].isin(excluded)].copy()
=======
    if emp.empty:
        raise ValueError("No employees found in Employee Skills.")
>>>>>>> 7ed376980eda079e94e5400f7bb31e455aceb63c
    eligible = set(zip(sk.loc[sk["_yes"], "_id"], sk.loc[sk["_yes"], "_op"].str.lower()))

    n, m = len(emp), len(slots)
    penalty = 1e7
    cost = np.full((n + m, m), penalty, dtype=float)
    for i, (_, e) in enumerate(emp.iterrows()):
        for j, op in enumerate(slots):
            if (e["_id"], normalize_text(op).lower()) in eligible:
                cost[i, j] = -float(e["_eff"]) + (i * 1e-8)
    cost[n:, :] = 0
    rows, cols = linear_sum_assignment(cost)
    assigned = {j: i for i, j in zip(rows, cols) if i < n and cost[i, j] < penalty}

    # Machine count by operation, and a stable machine slot number for readable output.
    op_slot_numbers = {}
    output = []
    for j, op in enumerate(slots):
        op_slot_numbers[op] = op_slot_numbers.get(op, 0) + 1
        if j in assigned:
            e = emp.iloc[assigned[j]]
            output.append({
                "Line": selected_line,
                "Operation": op,
                "Machines for Operation": int(machine_counts.get(op, 0)),
                "Operator Slot": op_slot_numbers[op],
                "Employee Name": e["_name"],
                "Employee ID": e["_id"],
                "Avg Efficiency (%)": round(float(e["_eff"]), 2),
                "Status": "Recommended",
                "Reason": "Qualified for this operation; ranked using average efficiency."
            })
        else:
            output.append({
                "Line": selected_line,
                "Operation": op,
                "Machines for Operation": int(machine_counts.get(op, 0)),
                "Operator Slot": op_slot_numbers[op],
                "Employee Name": "",
                "Employee ID": "",
                "Avg Efficiency (%)": None,
                "Status": "Unfilled",
                "Reason": "No eligible unassigned employee available for this operator slot."
            })
    result = pd.DataFrame(output)
    return result, {
        "required_slots": len(slots),
        "assigned": int((result["Status"] == "Recommended").sum()),
        "unfilled": int((result["Status"] == "Unfilled").sum()),
        "machine_count": machine_count,
        "assumption": assumption
    }
