import streamlit as st
import pandas as pd
from io import BytesIO
from allocation import recommend_for_line, normalize_text, find_column

st.set_page_config(page_title="Sewing Line AI Allocation", page_icon="🧵", layout="wide")
st.title("🧵 Sewing Line AI Operator Allocation")
st.caption("Upload all required factory data, including Punching Machine Data, choose a line and attendance date, then click APPLY & ANALYSE.")

def read_upload(upload):
    if upload is None: return None
    return pd.read_csv(upload) if upload.name.lower().endswith(".csv") else pd.read_excel(upload)

with st.sidebar:
    st.header("Upload your data")
    skills_file = st.file_uploader("1. Employee Skills / Operation Skill Matrix", type=["xlsx","xls","csv"])
    lines_file = st.file_uploader("2. Line Machine Details", type=["xlsx","xls","csv"])
    eff_file = st.file_uploader("3. Employee Efficiency", type=["xlsx","xls","csv"])
    req_file = st.file_uploader("4. Staffing Requirements (optional)", type=["xlsx","xls","csv"])
    punch_file = st.file_uploader("5. Punching Machine Data (REQUIRED for allocation)", type=["xlsx","xls","csv"])

skills, lines, eff, req, punches = map(read_upload, [skills_file, lines_file, eff_file, req_file, punch_file])
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
    st.info("Upload Employee Skills, Line Machine Details, and Employee Efficiency to start.")
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
selected_line=st.selectbox("Select sewing line",line_values)

allocation_date = None
punched_employee_ids = None
if punches is not None:
    try:
        _, punch_dates, latest_punch_date = make_attendance(skills, punches)
        allocation_date = st.selectbox("Allocate using punch attendance date", punch_dates, index=len(punch_dates)-1)
        punched_employee_ids = punched_ids_for_date(punches, allocation_date)
        st.info(f"Allocation will use only employees with punch records on {allocation_date}. Punched employees found: {len(punched_employee_ids)}.")
    except Exception as e:
        st.error(f"Could not filter employees using punching data: {e}")
        st.stop()
else:
    st.error("Punching Machine Data is compulsory. Upload the punch file in the sidebar before you can run employee allocation. APPLY & ANALYSE remains disabled until it is uploaded.")
try:
    target=normalize_text(selected_line).lower()
    line_rows=lines[lines[line_col].map(lambda x:normalize_text(x).lower())==target].copy()
    try: machine_id_col=find_column(line_rows,["Machine ID","Machine No","Machine Number","Equipment ID"])
    except ValueError: machine_id_col=None
    try: count_col=find_column(line_rows,["Machine Count","Number of Machines","No. of Machines","Machines","Machine Qty","Qty"])
    except ValueError: count_col=None
    line_rows["_Machine Count"]=pd.to_numeric(line_rows[count_col],errors="coerce").fillna(0) if count_col else 1
    op_summary=line_rows.groupby(machine_col,dropna=False)["_Machine Count"].sum().reset_index()
    op_summary.columns=["Operation","Number of Machines"]
    st.subheader(f"Selected line details — {selected_line}")
    c1,c2=st.columns(2)
    c1.metric("Different operations",len(op_summary)); c2.metric("Total machines",int(op_summary["Number of Machines"].sum()))
    st.dataframe(op_summary,use_container_width=True,hide_index=True)
except Exception as e: st.warning(f"Could not display machine summary: {e}")

left,right=st.columns([2,1])
with left: apply_clicked=st.button("🚀 APPLY & ANALYSE",type="primary",use_container_width=True, disabled=(punches is None))
with right: attendance_clicked=st.button("📋 ATTENDANCE DETAILS",use_container_width=True)
if attendance_clicked:
    st.session_state["page"]="attendance"; st.rerun()
if apply_clicked:
    try:
        result,summary=recommend_for_line(selected_line,skills,lines,eff,req,line_col,machine_col,emp_id_sk,emp_name_sk,op_sk,skill_col,emp_id_eff,efficiency_col, eligible_employee_ids=punched_employee_ids)
        st.session_state["result"]=result; st.session_state["summary"]=summary; st.session_state["selected_line"]=selected_line
    except Exception as e: st.error(f"Could not calculate recommendations: {e}")
if "result" in st.session_state and st.session_state.get("selected_line")==selected_line:
    r=st.session_state["result"]; s=st.session_state["summary"]
    st.header(f"Employee recommendations for {selected_line}")
    a,b,c,d=st.columns(4)
    a.metric("Required operator slots",s["required_slots"]); b.metric("Assigned employees",s["assigned"])
    c.metric("Unfilled slots",s["unfilled"]); d.metric("Machines on line",s.get("machine_count",0))
    if s.get("assumption"): st.warning(s["assumption"])
    st.dataframe(r,use_container_width=True,hide_index=True)
    st.download_button("Download recommendations (CSV)",r.to_csv(index=False).encode("utf-8-sig"),f"{normalize_text(selected_line).replace(' ','_')}_recommendations.csv","text/csv")
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as writer:r.to_excel(writer,index=False,sheet_name="Recommendations")
    st.download_button("Download recommendations (Excel)",buf.getvalue(),f"{normalize_text(selected_line).replace(' ','_')}_recommendations.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
