import streamlit as st
import pandas as pd
from io import BytesIO
from pathlib import Path
import os
from allocation import recommend_for_lines, normalize_text, normalize_id, normalize_operation, find_column

st.set_page_config(page_title="Sewing Line AI Allocation", page_icon="🧵", layout="wide")
st.title("🧵 Sewing Line AI Operator Allocation")
st.caption("Master files are bundled with the app. Upload only the daily punching file for each allocation day.")

def read_upload(upload):
    if upload is None: return None
    name = upload.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(upload)
    if name.endswith(".ods"):
        return pd.read_excel(upload, engine="odf")
    return pd.read_excel(upload)

# Master data is bundled with the project. No database or Supabase is required.
# Keep these files in the repository; only the daily punching file is uploaded.
DATA_ROOT = Path(__file__).parent / "data"
MASTER_DIR = DATA_ROOT / "master_data"

MASTER_FILES = {
    "employee": ("Employee Details Master", ["Employee_Details_Master.xlsx", "EMP DETAILS.xlsx"]),
    "skills": ("Employee Skills / Operation Skill Matrix", ["01_Employee_Skills.xlsx", "Employee_Skill_Data.xlsx", "Employee_Skill.xlsx", "Employee_Skills.xlsx"]),
    "lines": ("Line Machine Details", ["02_Line_Machine_Details.xlsx", "Line_Machine_Details_Converted.xlsx", "Line_Machine_Details.xlsx"]),
    "eff": ("Employee Efficiency", ["03_Employee_Efficiency.xlsx", "Employee_Efficiency_Data.xlsx", "Employee_Efficiency.xlsx"]),
    "req": ("Staffing Requirements (optional)", ["04_Staffing_Requirements.xlsx"]),
}

def _read_master_file(path):
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".ods":
        return pd.read_excel(path, engine="odf")
    return pd.read_excel(path)

def load_saved_master(key):
    # Search both project root and master_data; match names case-insensitively for Linux.
    display_name, candidates = MASTER_FILES[key]
    for root in [Path(__file__).parent, MASTER_DIR]:
        if not root.exists():
            continue
        existing = {p.name.lower(): p for p in root.iterdir() if p.is_file()}
        for candidate in candidates:
            path = existing.get(candidate.lower())
            if path is not None:
                try:
                    return _read_master_file(path)
                except Exception as exc:
                    st.warning(f"Could not read bundled {display_name} file '{path.name}': {exc}")
    return None

with st.sidebar:
    st.header("Daily Allocation")
    st.caption("Master files are bundled in this project. Upload only today's punching data.")
    punch_file = st.file_uploader(
        "Daily Punching Machine Data",
        type=["xlsx", "xls", "csv", "ods"],
        key="daily_punch_upload",
    )

punches = None
if punch_file is not None:
    try:
        if punch_file.name.lower().endswith(".csv"):
            punches = pd.read_csv(punch_file)
        elif punch_file.name.lower().endswith(".ods"):
            punches = pd.read_excel(punch_file, engine="odf")
        else:
            punches = pd.read_excel(punch_file)
    except Exception as exc:
        st.error(f"Could not read daily punching file: {exc}")

employee_master = load_saved_master("employee")
skills = load_saved_master("skills")
lines = load_saved_master("lines")
eff = load_saved_master("eff")
req = load_saved_master("req")

if "page" not in st.session_state: st.session_state["page"] = "allocation"

def get_roster(skills_df):
    idc=find_column(skills_df,["Employee ID","Emp ID","EmployeeID"])
    namec=find_column(skills_df,["Employee Name","Name","Employee"])
    return skills_df[[idc,namec]].rename(columns={idc:"Employee ID",namec:"Employee Name"}).dropna(subset=["Employee ID"]).drop_duplicates("Employee ID")

def punched_ids_for_date(punch_df, date_choice):
    pid = find_column(punch_df, ["Employee ID","Emp ID","EmployeeID","Emp Code","Employee Code","Employee No","Emp No","Employee Number"])
    datec = find_column(punch_df, ["Punch Date","Date","Attendance Date","Log Date"])
    temp = punch_df.copy()
    temp["_id"] = temp[pid].map(normalize_id)
    temp["_date"] = pd.to_datetime(temp[datec], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")
    chosen = pd.to_datetime(date_choice).strftime("%Y-%m-%d")
    return set(temp.loc[temp["_date"] == chosen, "_id"].dropna().tolist())

def make_attendance(skills_df,punch_df,date_choice=None):
    roster=get_roster(skills_df)
    pid=find_column(punch_df,["Employee ID","Emp ID","EmployeeID","Emp Code","Employee Code","Employee No","Emp No","Employee Number"])
    datec=find_column(punch_df,["Punch Date","Date","Attendance Date","Log Date"])
    pn=punch_df.copy()
    pn["_id"]=pn[pid].map(normalize_id)
    pn["_date"]=pd.to_datetime(pn[datec],errors="coerce",dayfirst=True).dt.strftime("%Y-%m-%d")
    dates=sorted(pn["_date"].dropna().unique().tolist())
    if not dates: raise ValueError("No valid punch dates found.")
    selected=pd.to_datetime(date_choice or dates[-1]).strftime("%Y-%m-%d")
    daily=pn[pn["_date"]==selected]
    roster["Employee ID"]=roster["Employee ID"].map(normalize_id)
    roster["Attendance Date"]=selected
    present=set(daily["_id"])
    roster["Attendance Status"]=roster["Employee ID"].map(lambda x:"Present" if x in present else "Absent")
    roster["Punch Records"]=roster["Employee ID"].map(daily.groupby("_id").size()).fillna(0).astype(int)
    try:
        timec=find_column(daily,["Punch Time","Time","Punch Timestamp"])
        roster["First Punch"]=roster["Employee ID"].map(daily.groupby("_id")[timec].min()).fillna("")
        roster["Last Punch"]=roster["Employee ID"].map(daily.groupby("_id")[timec].max()).fillna("")
    except ValueError: pass
    return roster,dates,selected

if st.session_state["page"]=="attendance":
    st.header("📋 Attendance Details")
    if skills is None or punches is None:
        st.warning("The bundled Employee Skills file or daily punching file is missing. Check the GitHub master file and upload today's punching data.")
    else:
        try:
            _,dates,latest=make_attendance(skills,punches)
            date_choice=st.selectbox("Attendance date",dates,index=len(dates)-1)
            attendance,_,_=make_attendance(skills,punches,date_choice)
            a,b,c=st.columns(3)
            a.metric("Total employees",len(attendance))
            b.metric("Present",int((attendance["Attendance Status"]=="Present").sum()))
            c.metric("Absent",int((attendance["Attendance Status"]=="Absent").sum()))
            view=st.radio("View records",["All","Present","Absent"],horizontal=True)
            shown=attendance if view=="All" else attendance[attendance["Attendance Status"]==view]
            st.dataframe(shown,use_container_width=True,hide_index=True)
            buf=BytesIO()
            with pd.ExcelWriter(buf,engine="openpyxl") as writer: shown.to_excel(writer,index=False,sheet_name="Attendance")
            st.download_button("Download attendance Excel",buf.getvalue(),f"attendance_{date_choice}_{view.lower()}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e: st.error(f"Could not read attendance: {e}")
    if st.button("⬅ Back to Allocation",use_container_width=True):
        st.session_state["page"]="allocation"; st.rerun()
    st.stop()

if any(x is None for x in [skills,lines,eff]):
    st.info("Required bundled master file is missing. Check that 01_Employee_Skills.xlsx, 02_Line_Machine_Details.xlsx, and 03_Employee_Efficiency.xlsx are committed in the GitHub repository root.")
    st.markdown("**Punching Machine Data is compulsory for allocation.** Upload it to enable recommendations; only employees with punch records on the selected date can be allocated. Attendance Details can be opened separately.")
    if st.button("📋 ATTENDANCE DETAILS",use_container_width=True):
        st.session_state["page"]="attendance"; st.rerun()
    st.stop()

try:
    line_col=find_column(lines,["Line","Candidate Line"])
    machine_col=find_column(lines,["Operation","Required Operation","Machine Type"])
    emp_id_sk=find_column(skills,["Employee ID","Emp ID","EmployeeID"])
    emp_name_sk=find_column(skills,["Employee Name","Name","Employee"])
    op_sk=find_column(skills,["Operation","Machine Type","Skill Operation"])
    skill_col=find_column(skills,["Skill","Skill Status","Knowledge","YES/NO","Skill Score","Score"])
    emp_id_eff=find_column(eff,["Employee ID","Emp ID","EmployeeID"])
    efficiency_col=find_column(eff,["Avg Efficiency","Avg Eff (%)","Avg Eff","Efficiency","Average Efficiency","Average Efficiency (%)","Average Efficiency (Source Ratio)"])
except ValueError as e:
    st.error(str(e)); st.stop()

line_values=sorted([x for x in lines[line_col].dropna().unique().tolist() if normalize_text(x).lower()!="grand total"],key=str)
# Strict operation diagnostics: never silently treat unrelated operations as equivalent.
try:
    _skill_ops = {normalize_operation(x) for x in skills[op_sk].dropna() if normalize_operation(x)}
    _approved_map = {}
    if operation_mapping is not None and not operation_mapping.empty:
        _mc = find_column(operation_mapping, ["Machine Operation", "Machine Type", "Operation"])
        _sc = find_column(operation_mapping, ["Skill Operation", "Approved Skill Operation", "Employee Skill Operation"])
        for _, _mr in operation_mapping.iterrows():
            _mk, _sk = normalize_operation(_mr[_mc]), normalize_operation(_mr[_sc])
            if _mk and _sk: _approved_map.setdefault(_mk, set()).add(_sk)
    _machine_ops = sorted({normalize_text(x) for x in lines[machine_col].dropna() if normalize_text(x)})
    _unmapped_ops = [x for x in _machine_ops if normalize_operation(x) not in _skill_ops and not (_approved_map.get(normalize_operation(x), set()) & _skill_ops)]
    if _unmapped_ops:
        st.warning("Strict skill matching: these machine operations have no exact skill-name match or verified mapping: " + ", ".join(_unmapped_ops) + ". Their slots will remain unfilled until you add verified rows to 05_Operation_Mapping.xlsx or align the master operation names.")
except Exception:
    pass
selected_lines=st.multiselect("Select one or more sewing lines",line_values,default=[] ,help="Choose multiple lines for one allocation run. Each employee can be assigned to only one of the selected lines.")

allocation_date = None
punched_employee_ids = None
if punches is not None:
    try:
        _, punch_dates, latest_punch_date = make_attendance(skills, punches)
        allocation_date = st.selectbox("Allocate using punch attendance date", punch_dates, index=len(punch_dates)-1)
        punched_employee_ids = punched_ids_for_date(punches, allocation_date)
        skill_ids = set(skills[emp_id_sk].map(normalize_id)) if "emp_id_sk" in globals() else set()
        # emp_id_sk is detected later in the script, so calculate overlap using common ID column names here.
        try:
            _sid_col = find_column(skills, ["Employee ID", "Emp ID", "EmployeeID"])
            _skill_ids = {normalize_id(x) for x in skills[_sid_col].dropna()}
            _overlap = len(_skill_ids.intersection(punched_employee_ids))
            st.info(f"Allocation date: {allocation_date}. Punch records found: {len(punched_employee_ids)} unique IDs; IDs matching the skill matrix: {_overlap}. Each employee can be assigned to only one selected line.")
            if _overlap == 0:
                st.error("No punched employee IDs match the skill matrix. Check that 01_Employee_Skills.xlsx in GitHub is the correct current skill matrix and that the punching IDs use the same employee codes.")
            elif _overlap < len(punched_employee_ids):
                st.warning(f"{len(punched_employee_ids) - _overlap} punched employee IDs do not exist in the skill matrix and cannot be allocated. Check ID formats or refresh the skill master.")
        except Exception:
            st.info(f"Allocation will use only employees with punch records on {allocation_date}. Punched employees found: {len(punched_employee_ids)}. Each employee can be assigned to only one selected line.")
    except Exception as e:
        st.error(f"Could not filter employees using punching data: {e}")
        st.stop()
else:
    st.error("Punching Machine Data is compulsory. Upload the punch file in the sidebar before you can run employee allocation. APPLY & ANALYSE remains disabled until it is uploaded.")

if selected_lines and punched_employee_ids is not None and lines is not None:
    try:
        total_required = 0
        for _line in selected_lines:
            _lr = lines[lines[line_col].map(lambda x: normalize_text(x).lower()) == normalize_text(_line).lower()]
            _count_col = None
            try:
                _count_col = find_column(_lr, ["Machine Count", "Number of Machines", "No. of Machines", "Machines", "Machine Qty", "Qty"])
            except ValueError:
                pass
            if _count_col:
                total_required += int(pd.to_numeric(_lr[_count_col], errors="coerce").fillna(0).clip(lower=0).sum())
            else:
                total_required += len(_lr)
        if len(punched_employee_ids) < total_required:
            st.warning(f"Capacity check: {len(punched_employee_ids)} unique employees punched in, while selected lines require approximately {total_required} operator slots (one per machine). All slots cannot be filled unless staffing requirements are lower or more employees are present. The app will assign available eligible employees without duplicating them.")
    except Exception:
        pass

if selected_lines:
    with st.expander("Selected line machine details", expanded=False):
        for selected_line in selected_lines:
            target=normalize_text(selected_line).lower()
            line_rows=lines[lines[line_col].map(lambda x:normalize_text(x).lower())==target].copy()
            try:
                count_col=find_column(line_rows,["Machine Count","Number of Machines","No. of Machines","Machines","Machine Qty","Qty"])
            except ValueError:
                count_col=None
            line_rows["_Machine Count"]=pd.to_numeric(line_rows[count_col],errors="coerce").fillna(0) if count_col else 1
            op_summary=line_rows.groupby(machine_col,dropna=False)["_Machine Count"].sum().reset_index()
            op_summary.columns=["Operation","Number of Machines"]
            st.markdown(f"**{selected_line}** — {int(op_summary['Number of Machines'].sum())} machines")
            st.dataframe(op_summary,use_container_width=True,hide_index=True)

left,right=st.columns([2,1])
with left: apply_clicked=st.button("🚀 APPLY & ANALYSE SELECTED LINES",type="primary",use_container_width=True, disabled=(punches is None or not selected_lines))
with right: attendance_clicked=st.button("📋 ATTENDANCE DETAILS",use_container_width=True)
if attendance_clicked:
    st.session_state["page"]="attendance"; st.rerun()
if apply_clicked:
    try:
        combined, summary_df = recommend_for_lines(
            selected_lines, skills, lines, eff, req,
            line_col, machine_col, emp_id_sk, emp_name_sk, op_sk, skill_col,
            emp_id_eff, efficiency_col,
            eligible_employee_ids=punched_employee_ids,
            operation_mapping=operation_mapping,
        )
        st.session_state["multi_result"] = combined
        st.session_state["multi_summary"] = summary_df
        st.session_state["multi_selected_lines"] = list(selected_lines)
        st.session_state["multi_allocation_date"] = allocation_date
    except Exception as e:
        st.error(f"Could not calculate recommendations: {e}")

if st.session_state.get("multi_selected_lines")==list(selected_lines) and "multi_result" in st.session_state:
    r=st.session_state["multi_result"]
    summary_df=st.session_state["multi_summary"]
    st.header("Employee recommendations across selected lines")
    a,b,c=st.columns(3)
    a.metric("Selected lines",len(selected_lines))
    b.metric("Total assigned employees",int((r["Status"]=="Recommended").sum()))
    c.metric("Unfilled operator slots",int((r["Status"]=="Unfilled").sum()))
    st.caption("Allocation is optimized across all selected lines together. Assignments are balanced across lines where qualifications allow; each employee can be assigned to only one machine.")
    st.subheader("Line summary")
    st.dataframe(summary_df,use_container_width=True,hide_index=True)
    st.subheader("All line recommendations")
    st.dataframe(r,use_container_width=True,hide_index=True)
    st.download_button("Download all recommendations (CSV)",r.to_csv(index=False).encode("utf-8-sig"),"multi_line_recommendations.csv","text/csv")
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as writer:
        r.to_excel(writer,index=False,sheet_name="Recommendations")
        summary_df.to_excel(writer,index=False,sheet_name="Line Summary")
    st.download_button("Download all recommendations (Excel)",buf.getvalue(),"multi_line_recommendations.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
