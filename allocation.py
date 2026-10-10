import re
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


def normalize_text(v):
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def normalize_id(v):
    if pd.isna(v):
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(v).upper())


def normalize_operation(v):
    """Case/spacing/punctuation-insensitive key; does not infer related skills."""
    if pd.isna(v):
        return ""
    return re.sub(r"[^a-z0-9]", "", normalize_text(v).lower())


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


def to_num(s):
    return pd.to_numeric(s.astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False).str.strip(), errors="coerce")


def _positive_skill_mask(skills, skill_status_col):
    if normalize_text(skill_status_col).lower().replace(" ", "") in {"skillscore", "score"}:
        return pd.to_numeric(skills[skill_status_col], errors="coerce").fillna(0) > 0
    return skills[skill_status_col].map(lambda v: normalize_text(v).lower() in {"yes", "y", "true", "1", "skilled"})


def _slots_for_line(selected_line, lines, requirements, line_col, machine_col):
    target = normalize_text(selected_line).lower()
    line_rows = lines[lines[line_col].map(lambda x: normalize_text(x).lower()) == target].copy()
    line_rows = line_rows[line_rows[machine_col].notna()]
    if line_rows.empty:
        raise ValueError(f"No machine details found for {selected_line}.")
    try:
        count_col = find_column(line_rows, ["Machine Count", "Number of Machines", "No. of Machines", "Machines", "Machine Qty", "Qty"])
    except ValueError:
        count_col = None
    machine_counts = {}
    for _, row in line_rows.iterrows():
        op = normalize_text(row[machine_col])
        if not op:
            continue
        if count_col:
            count = pd.to_numeric(row[count_col], errors="coerce")
            count = int(max(0, count)) if pd.notna(count) else 0
        else:
            count = 1
        machine_counts[op] = machine_counts.get(op, 0) + count
    machine_count = sum(machine_counts.values())

    slots = []
    assumption = ""
    if requirements is not None and not requirements.empty:
        try:
            rline = find_column(requirements, ["Line", "Candidate Line"])
            rop = find_column(requirements, ["Operation", "Machine Type", "Required Operation"])
            rcount = find_column(requirements, ["Operators Required", "Required Operators", "Operator Count", "Slots"])
            rr = requirements[requirements[rline].map(lambda x: normalize_text(x).lower()) == target]
            for _, row in rr.iterrows():
                op = normalize_text(row[rop])
                count = pd.to_numeric(row[rcount], errors="coerce")
                if op and pd.notna(count) and count > 0:
                    slots.extend({"line": selected_line, "operation": op, "slot": k + 1, "machine_count": machine_counts.get(op, 0)} for k in range(int(count)))
        except ValueError:
            pass
    if not slots:
        assumption = "No matching staffing requirement found; used one operator per machine as the slot-count fallback."
        for op in sorted(machine_counts, key=str.lower):
            slots.extend({"line": selected_line, "operation": op, "slot": k + 1, "machine_count": machine_counts[op]} for k in range(machine_counts[op]))
    return slots, machine_count, assumption


def recommend_for_lines(selected_lines, skills, lines, efficiency, requirements,
                        line_col, machine_col, skill_id_col, skill_name_col,
                        skill_op_col, skill_status_col, eff_id_col, eff_col,
                        eligible_employee_ids=None, operation_mapping=None):
    """Allocate across all selected lines in one global assignment.

    Strict policy: a worker can fill a slot only when their positive skill row
    matches that slot's operation (case/spacing/punctuation-insensitive).
    Each employee is assigned at most once across all selected lines.
    Allocation maximizes filled slots first, then balances earlier round-robin
    slot ranks across lines, then prefers higher efficiency.
    """
    if not selected_lines:
        return pd.DataFrame(), pd.DataFrame()
    all_slots, machine_counts, assumptions = [], {}, {}
    for line in selected_lines:
        slots, mc, assumption = _slots_for_line(line, lines, requirements, line_col, machine_col)
        machine_counts[line] = mc
        assumptions[line] = assumption
        all_slots.extend(slots)

    sk = skills.copy()
    sk["_id"] = sk[skill_id_col].map(normalize_id)
    sk["_name"] = sk[skill_name_col].map(normalize_text)
    sk["_opkey"] = sk[skill_op_col].map(normalize_operation)
    sk["_positive"] = _positive_skill_mask(sk, skill_status_col)
    valid = sk[(sk["_id"] != "") & sk["_positive"] & (sk["_opkey"] != "")]
    # Skill compatibility is exact after harmless formatting normalization.
    # Optional mapping rows explicitly authorize a machine operation to use a
    # specific skill-matrix operation. No inferred/broad fallback is performed.
    qualified = set(zip(valid["_id"], valid["_opkey"]))
    operation_to_skill_keys = {}
    if operation_mapping is not None and not operation_mapping.empty:
        try:
            map_machine_col = find_column(operation_mapping, ["Machine Operation", "Machine Type", "Operation"])
            map_skill_col = find_column(operation_mapping, ["Skill Operation", "Approved Skill Operation", "Employee Skill Operation"])
            for _, map_row in operation_mapping.iterrows():
                machine_key = normalize_operation(map_row[map_machine_col])
                skill_key = normalize_operation(map_row[map_skill_col])
                if machine_key and skill_key:
                    operation_to_skill_keys.setdefault(machine_key, set()).add(skill_key)
        except ValueError:
            operation_to_skill_keys = {}

    def _slot_skill_keys(slot):
        machine_key = normalize_operation(slot["operation"])
        return {machine_key} | operation_to_skill_keys.get(machine_key, set())

    ef = efficiency.copy()
    ef["_id"] = ef[eff_id_col].map(normalize_id)
    ef["_eff"] = to_num(ef[eff_col])
    eff_by = ef[ef["_id"] != ""].groupby("_id")["_eff"].max()
    emp = sk[sk["_id"] != ""].drop_duplicates("_id").sort_values("_name")[ ["_id", "_name"] ].copy()
    emp["_eff"] = emp["_id"].map(eff_by).fillna(0)
    if not emp.empty and emp["_eff"].dropna().size and emp["_eff"].max() <= 1.5:
        emp["_eff"] = emp["_eff"] * 100
    emp["_eff"] = emp["_eff"].clip(0, 100)
    if eligible_employee_ids is not None:
        allowed = {normalize_id(x) for x in eligible_employee_ids if normalize_id(x)}
        emp = emp[emp["_id"].isin(allowed)].copy()

    # Interleave slots line-by-line (slot 1 from every line before slot 2) to
    # make equal-capacity solutions spread assignments fairly across lines.
    by_line = {line: [s for s in all_slots if normalize_text(s["line"]).lower() == normalize_text(line).lower()] for line in selected_lines}
    ordered_slots = []
    max_slots = max((len(v) for v in by_line.values()), default=0)
    for depth in range(max_slots):
        for line in selected_lines:
            if depth < len(by_line[line]):
                s = dict(by_line[line][depth])
                s["_fair_rank"] = depth
                ordered_slots.append(s)
    all_slots = ordered_slots

    n, m = len(emp), len(all_slots)
    output_rows = []
    if m == 0:
        return pd.DataFrame(), pd.DataFrame()
    if n:
        # Dummy rows allow unfilled slots. A qualified assignment has a large
        # reward, so the optimizer maximizes the number filled before balancing.
        # Lower slot depth gets a small priority; efficiency is a later tie-breaker.
        unfilled_penalty = 0.0
        forbidden = 1e12
        cost = np.full((n + m, m), forbidden, dtype=float)
        cost[n:, :] = unfilled_penalty
        for i, (_, e) in enumerate(emp.iterrows()):
            for j, slot in enumerate(all_slots):
                if any((e["_id"], skill_key) in qualified for skill_key in _slot_skill_keys(slot)):
                    cost[i, j] = -1e9 + float(slot["_fair_rank"]) * 1000 - float(e["_eff"])
        rows, cols = linear_sum_assignment(cost)
        assigned = {j: i for i, j in zip(rows, cols) if i < n and cost[i, j] < forbidden}
    else:
        assigned = {}

    for j, slot in enumerate(all_slots):
        line, op = slot["line"], slot["operation"]
        qualified_available = sum(1 for _, e in emp.iterrows() if any((e["_id"], skill_key) in qualified for skill_key in _slot_skill_keys(slot)))
        if j in assigned:
            e = emp.iloc[assigned[j]]
            output_rows.append({"Line": line, "Operation": op, "Machines for Operation": int(slot["machine_count"]),
                "Operator Slot": slot["slot"], "Employee Name": e["_name"], "Employee ID": e["_id"],
                "Avg Efficiency (%)": round(float(e["_eff"]), 2), "Status": "Recommended",
                "Reason": "Positive skill score for this exact operation; globally allocated once and ranked by efficiency."})
        else:
            if qualified_available == 0:
                reason = "No punched employee has a positive skill score for this exact operation. Check the operation names in the machine and skill masters."
            else:
                reason = "Qualified employees are unavailable or already assigned to another selected machine/line."
            output_rows.append({"Line": line, "Operation": op, "Machines for Operation": int(slot["machine_count"]),
                "Operator Slot": slot["slot"], "Employee Name": "", "Employee ID": "", "Avg Efficiency (%)": None,
                "Status": "Unfilled", "Reason": reason})

    result = pd.DataFrame(output_rows)
    summary_rows = []
    for line in selected_lines:
        lr = result[result["Line"].map(lambda x: normalize_text(x).lower()) == normalize_text(line).lower()]
        summary_rows.append({"Line": line, "required_slots": len(lr),
            "assigned": int((lr["Status"] == "Recommended").sum()),
            "unfilled": int((lr["Status"] == "Unfilled").sum()),
            "machine_count": int(machine_counts[line]),
            "assumption": assumptions[line] + (" " if assumptions[line] else "") + "Strict operation-specific skill matching enabled."})
    return result, pd.DataFrame(summary_rows)


def recommend_for_line(*args, **kwargs):
    """Backward-compatible wrapper for older app versions."""
    selected_line = args[0]
    result, summary = recommend_for_lines([selected_line], *args[1:], **kwargs)
    return result, (summary.iloc[0].to_dict() if not summary.empty else {})
