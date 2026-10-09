import streamlit as st
import pandas as pd
from io import BytesIO
from pathlib import Path
import os
from allocation import recommend_for_line, normalize_text, find_column

st.set_page_config(page_title="Sewing Line AI Allocation", page_icon="🧵", layout="wide")
st.title("🧵 Sewing Line AI Operator Allocation")
st.caption("Upload master data once. It is saved for reuse; upload only the daily punching file for each allocation day.")

def read_upload(upload):
    if upload is None: return None
    return pd.read_csv(upload) if upload.name.lower().endswith(".csv") else pd.read_excel(upload)

# Persistent storage: on Render, mount a persistent disk at /var/data. Locally, use ./data/master_data.
DATA_ROOT = Path("/var/data") if Path("/var/data").exists() and os.access("/var/data", os.W_OK) else Path(__file__).parent / "data"
MASTER_DIR = DATA_ROOT / "master_data"
MASTER_DIR.mkdir(parents=True, exist_ok=True)
MASTER_FILES = {
    "skills": ("Employee Skills / Operation Skill Matrix", "employee_skills"),
    "lines": ("Line Machine Details", "line_machine_details"),
    "eff": ("Employee Efficiency", "employee_efficiency"),
    "req": ("Staffing Requirements (optional)", "staffing_requirements"),
}

def saved_master_path(key):
    matches = list(MASTER_DIR.glob(f"{MASTER_FILES[key][1]}.*"))
    return matches[0] if matches else None

def load_saved_master(key):
    path = saved_master_path(key)
    if path is None: return None
    return pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)

def save_master_upload(key, upload):
    if upload is None: return
    stem = MASTER_FILES[key][1]
    for old in MASTER_DIR.glob(f"{stem}.*"):
        old.unlink()
    suffix = Path(upload.name).suffix.lower()
    target = MASTER_DIR / f"{stem}{suffix}"
    target.write_bytes(upload.getvalue())

with st.sidebar:
    st.header("Master Data (upload once)")
    st.caption("Master data is saved and reused automatically. Re-upload only when the master data changes.")
    skills_file = st.file_uploader("1. Employee Skills / Operation Skill Matrix", type=["xlsx","xls","csv"], key="master_skills_upload")
    lines_file = st.file_uploader("2. Line Machine Details", type=["xlsx","xls","csv"], key="master_lines_upload")
    eff_file = st.file_uploader("3. Employee Efficiency", type=["xlsx","xls","csv"], key="master_eff_upload")
    req_file = st.file_uploader("4. Staffing Requirements (optional)", type=["xlsx","xls","csv"], key="master_req_upload")
    punch_file = st.file_uploader("5. Daily Punching Machine Data (upload each day)", type=["xlsx","xls","csv"], key="daily_punch_upload")

for key, uploaded in [("skills", skills_file), ("lines", lines_file), ("eff", eff_file), ("req", req_file)]:
    if uploaded is not None:
        save_master_upload(key, uploaded)

skills = read_upload(skills_file) if skills_file is not None else load_saved_master("skills")
lines = read_upload(lines_file) if lines_file is not None else load_saved_master("lines")
eff = read_upload(eff_file) if eff_file is not None else load_saved_master("eff")
req = read_upload(req_file) if req_file is not None else load_saved_master("req")
punches = read_upload(punch_file)

if "page" not in st.session_state: st.session_state["page"] = "allocation"

def get_roster(skills_df):
    idc=find_column(skills_df,["Employee ID","Emp ID","EmployeeID"])
    namec=find_column(skills_df,["Employee Name","Name","Employee"])
    return skills_df[[idc,namec]].rename(columns={idc:"Employee ID",namec:"Employee Name"}).dropna(subset=["Employee ID"]).drop_duplicates("Employee ID")

def punched_ids_for_date(punch_df, date_choice):
    pid = find_column(punch_df, ["Employee ID","Emp ID","EmployeeID"])
    datec = find_column(punch_df, ["Punch Date","Date","Attendance Date","Log Date"])
    temp = punch_df.copy()
    temp["_id"] = temp[pid].map(normalize_text)
    temp["_date"] = pd.to_datetime(temp[datec], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d")
    chosen = pd.to_datetime(date_choice).strftime("%Y-%m-%d")
    return set(temp.loc[temp["_date"] == chosen, "_id"].dropna().tolist())

def make_attendance(skills_df,punch_df,date_choice=None):
    roster=get_roster(skills_df)
    pid=find_column(punch_df,["Employee ID","Emp ID","EmployeeID"])
    datec=find_column(punch_df,["Punch Date","Date","Attendance Date","Log Date"])
    pn=punch_df.copy()
    pn["_id"]=pn[pid].map(normalize_text)
    pn["_date"]=pd.to_datetime(pn[datec],errors="coerce",dayfirst=True).dt.strftime("%Y-%m-%d")
    dates=sorted(pn["_date"].dropna().unique().tolist())
    if not dates: raise ValueError("No valid punch dates found.")
    selected=pd.to_datetime(date_choice or dates[-1]).strftime("%Y-%m-%d")
    daily=pn[pn["_date"]==selected]
    roster["Employee ID"]=roster["Employee ID"].map(normalize_text)
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
        st.warning("Upload Employee Skills and Punching Machine Data in the sidebar.")
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
    st.info("Upload Employee Skills, Line Machine Details, and Employee Efficiency once in the sidebar. Saved master data will load automatically on future visits.")
    st.markdown("**Punching Machine Data is compulsory for allocation.** Upload it to enable recommendations; only employees with punch records on the selected date can be allocated. Attendance Details can be opened separately.")
    if st.button("📋 ATTENDANCE DETAILS",use_container_width=True):
        st.session_state["page"]="attendance"; st.rerun()
    st.stop()

try:
    line_col=find_column(lines,["Line","Candidate Line"])
    machine_col=find_column(lines,["Machine Type","Operation","Required Operation"])
    emp_id_sk=find_column(skills,["Employee ID","Emp ID","EmployeeID"])
    emp_name_sk=find_column(skills,["Employee Name","Name","Employee"])
    op_sk=find_column(skills,["Operation","Machine Type","Skill Operation"])
    skill_col=find_column(skills,["Skill","Skill Status","Knowledge","YES/NO"])
    emp_id_eff=find_column(eff,["Employee ID","Emp ID","EmployeeID"])
    efficiency_col=find_column(eff,["Avg Efficiency","Avg Eff (%)","Avg Eff","Efficiency","Average Efficiency"])
except ValueError as e:
    st.error(str(e)); st.stop()

line_values=sorted([x for x in lines[line_col].dropna().unique().tolist() if normalize_text(x).lower()!="grand total"],key=str)
selected_lines=st.multiselect("Select one or more sewing lines",line_values,default=[] ,help="Choose multiple lines for one allocation run. Each employee can be assigned to only one of the selected lines.")

allocation_date = None
punched_employee_ids = None
if punches is not None:
    try:
        _, punch_dates, latest_punch_date = make_attendance(skills, punches)
        allocation_date = st.selectbox("Allocate using punch attendance date", punch_dates, index=len(punch_dates)-1)
        punched_employee_ids = punched_ids_for_date(punches, allocation_date)
        st.info(f"Allocation will use only employees with punch records on {allocation_date}. Punched employees found: {len(punched_employee_ids)}. Each employee can be assigned to only one selected line.")
    except Exception as e:
        st.error(f"Could not filter employees using punching data: {e}")
        st.stop()
else:
    st.error("Punching Machine Data is compulsory. Upload the punch file in the sidebar before you can run employee allocation. APPLY & ANALYSE remains disabled until it is uploaded.")

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
        all_results=[]
        all_summaries=[]
        already_assigned=set()
        for selected_line in selected_lines:
            result,summary=recommend_for_line(selected_line,skills,lines,eff,req,line_col,machine_col,emp_id_sk,emp_name_sk,op_sk,skill_col,emp_id_eff,efficiency_col, eligible_employee_ids=punched_employee_ids, excluded_employee_ids=already_assigned)
            assigned_ids=set(result.loc[result["Status"]=="Recommended","Employee ID"].map(normalize_text))
            already_assigned.update(x for x in assigned_ids if x)
            all_results.append(result)
            all_summaries.append({"Line":selected_line,**summary})
        combined=pd.concat(all_results,ignore_index=True) if all_results else pd.DataFrame()
        st.session_state["multi_result"]=combined
        st.session_state["multi_summary"]=pd.DataFrame(all_summaries)
        st.session_state["multi_selected_lines"]=list(selected_lines)
        st.session_state["multi_allocation_date"]=allocation_date
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
    st.caption("Employees are allocated in the order of selected lines. Once assigned to one line, an employee is excluded from every subsequent selected line in this run.")
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
