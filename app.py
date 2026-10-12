import re
from io import BytesIO
from pathlib import Path
import pandas as pd
import streamlit as st
from allocation import normalize_text, normalize_id, find_column, build_machine_slots, allocate_all_slots

st.set_page_config(page_title='Sewing Line AI Operator Allocation',page_icon='🧵',layout='wide')
st.title('🧵 Sewing Line AI Operator Allocation')
st.caption('Upload daily punching data. Machine serial numbers are loaded from the bundled Line Machine Details workbook.')
ROOT=Path(__file__).parent
DATA=ROOT/'data'

def load_master(candidates):
    for folder in [ROOT, DATA, DATA/'master_data']:
        if folder.exists():
            files={p.name.lower():p for p in folder.iterdir() if p.is_file()}
            for name in candidates:
                p=files.get(name.lower())
                if p:
                    try: return pd.read_excel(p)
                    except Exception as e: st.warning(f'Could not read {p.name}: {e}')
    return None

def read_upload(file):
    if file is None: return None
    n=file.name.lower()
    if n.endswith('.csv'): return pd.read_csv(file)
    if n.endswith('.ods'): return pd.read_excel(file,engine='odf')
    return pd.read_excel(file)

def get_punch_columns(df):
    idc=find_column(df,['Employee ID','Emp ID','EmployeeID','Emp Code','Employee Code','Employee No','Emp No','Employee Number'])
    datec=find_column(df,['Punch Date','Date','Attendance Date','Log Date'])
    namec=None
    try: namec=find_column(df,['Employee Name','Emp Name','Name'])
    except ValueError: pass
    return idc,datec,namec

with st.sidebar:
    st.header('Daily Allocation')
    st.caption('Master files are bundled. Upload only the daily punching file.')
    punch_file=st.file_uploader('Daily Punching Machine Data',type=['xlsx','xls','csv','ods'],key='daily_punch_upload')
    st.caption('No Supabase or database connection is required.')

skills=load_master(['01_Employee_Skills.xlsx','Employee_Skill_Data.xlsx','Employee_Skill.xlsx','Employee_Skills.xlsx'])
lines=load_master(['02_Line_Machine_Details.xlsx','Line_Machine_Details.xlsx','Line_Machine_Details_Converted.xlsx'])
eff=load_master(['03_Employee_Efficiency.xlsx','Employee_Efficiency.xlsx','Employee_Efficiency_Data.xlsx'])
employees=load_master(['Employee_Details_Master.xlsx','EMP DETAILS.xlsx','EMP MASTER.xlsx'])
requirements=load_master(['04_Staffing_Requirements.xlsx'])
# Read the two added sheets from the machine workbook when present.
approved_mapping=None
machine_inventory=None
for p in [ROOT/'02_Line_Machine_Details.xlsx',DATA/'Line_Machine_Details.xlsx',DATA/'master_data'/'Line_Machine_Details.xlsx']:
    if p.exists():
        try:
            xl=pd.ExcelFile(p)
            if 'Machine Skill Mapping' in xl.sheet_names: approved_mapping=pd.read_excel(p,sheet_name='Machine Skill Mapping')
            if 'Machine Register' in xl.sheet_names: machine_inventory=pd.read_excel(p,sheet_name='Machine Register')
            break
        except Exception: pass

if any(x is None for x in [skills,lines,eff]):
    st.error('A required bundled master file is missing. Ensure 01_Employee_Skills.xlsx, 02_Line_Machine_Details.xlsx, and 03_Employee_Efficiency.xlsx are in the project root.')
    st.stop()

try:
    line_col=find_column(lines,['Line','Candidate Line'])
    machine_col=find_column(lines,['Machine Type','Operation','Required Operation'])
    count_col=find_column(lines,['No. of Machines','Machine Count','Number of Machines','Qty'])
    serial_col=None
    try: serial_col=find_column(lines,['Machine Serial Numbers','Machine Serial Number'])
    except ValueError: pass
    sid=find_column(skills,['Employee ID','Emp ID','EmployeeID'])
    sname=find_column(skills,['Employee Name','Name','Employee'])
    sop=find_column(skills,['Operation','Machine Type','Skill Operation'])
    sscore=find_column(skills,['Skill Score','Skill','Skill Status','Score','YES/NO'])
    eid_eff=find_column(eff,['Employee ID','Emp ID','EmployeeID'])
    ecol=find_column(eff,['Average Efficiency (%)','Average Efficiency','Avg Efficiency','Avg Eff (%)','Efficiency','Average Efficiency (Source Ratio)'])
    emid=emname=None
    if employees is not None:
        try: emid=find_column(employees,['Employee ID','Emp ID','EmployeeID']); emname=find_column(employees,['Employee Name','Name','Employee'])
        except ValueError: employees=None
except ValueError as e:
    st.error(str(e)); st.stop()

line_values=sorted([x for x in lines[line_col].dropna().unique().tolist() if normalize_text(x).upper()!='IDEAL'],key=str)
selected_lines=st.multiselect('Select one or more sewing lines',line_values,default=line_values,help='Machine slots are assigned globally so one employee is not duplicated across lines.')
punches=read_upload(punch_file)
if punches is None:
    st.info('Upload today’s punching file to enable allocation.')
    st.stop()
try:
    pid,datec,pname=get_punch_columns(punches)
    punch_dates=pd.to_datetime(punches[datec],errors='coerce',dayfirst=True).dropna().dt.strftime('%Y-%m-%d').drop_duplicates().sort_values().tolist()
    if not punch_dates:
        st.error('No valid dates found in the punching file. Check the Log Date column.')
        st.stop()
    chosen=st.selectbox('Allocate using punch attendance date',punch_dates,index=len(punch_dates)-1)
    tmp=punches.copy(); tmp['_id']=tmp[pid].map(normalize_id); tmp['_date']=pd.to_datetime(tmp[datec],errors='coerce',dayfirst=True).dt.strftime('%Y-%m-%d')
    day=tmp[(tmp['_date']==chosen)&(tmp['_id']!='')].copy()
    punched_ids=set(day['_id'])
    skill_ids={normalize_id(x) for x in skills[sid].dropna() if normalize_id(x)}
    matched=len(punched_ids & skill_ids)
    st.info(f'Allocation date: {chosen}. Punch records found: {len(punched_ids)} unique IDs; {matched} IDs match the skill matrix. No employee will be assigned to two machines.')
    if matched<len(punched_ids): st.warning(f'{len(punched_ids)-matched} punched IDs have no skill-matrix record. To keep every machine staffed, the app can allocate these provisionally and clearly flag them for supervisor verification.')
except Exception as e:
    st.error(f'Could not read punching data: {e}'); st.stop()

with st.expander('Machine serial inventory and coverage',expanded=False):
    if machine_inventory is not None:
        st.caption(f'{len(machine_inventory)} physical machine records found in Summery_reports.xlsx. Serial numbers are only shown where recorded; missing inventory serials are labelled.')
        st.dataframe(machine_inventory,use_container_width=True,hide_index=True)
    else: st.warning('Machine Register sheet is missing. Serial numbers will show as not recorded.')
    if serial_col:
        st.dataframe(lines[[line_col,machine_col,count_col,serial_col]+([find_column(lines,['Serial Numbers Available'])] if any(str(c).lower()=='serial numbers available' for c in lines.columns) else [])],use_container_width=True,hide_index=True)

if st.button('🚀 APPLY & ANALYSE SELECTED LINES',type='primary',use_container_width=True,disabled=not selected_lines):
    # Use the physical Machine Register as the source of truth whenever present.
    # Each register row is one machine slot; serial numbers are never split/guessed.
    if machine_inventory is not None and not machine_inventory.empty:
        reg_line=find_column(machine_inventory,['Line'])
        reg_op=find_column(machine_inventory,['Operation'])
        reg_type=find_column(machine_inventory,['Machine Type'])
        reg_slot=find_column(machine_inventory,['Machine Slot'])
        reg_serial=find_column(machine_inventory,['Machine Serial Number'])
        chosen_norm={normalize_text(x).lower() for x in selected_lines}
        picked=machine_inventory[machine_inventory[reg_line].map(lambda x:normalize_text(x).lower()).isin(chosen_norm)].copy()
        slots=[]
        for _,mr in picked.iterrows():
            serial=normalize_text(mr[reg_serial])
            if not serial or serial.lower() in {'nan','none','n/a','na'}:
                serial='Not recorded in machine inventory'
            slot_number=pd.to_numeric(mr[reg_slot],errors='coerce')
            slots.append({'Line':normalize_text(mr[reg_line]),'Operation':normalize_text(mr[reg_op]),
                          'Machine Type':normalize_text(mr[reg_type]),'Machine Slot':int(slot_number) if pd.notna(slot_number) else 1,
                          'Machine Serial Number':serial})
    else:
        slots=build_machine_slots(lines,selected_lines,line_col,machine_col,serial_col,count_col)
    if not slots:
        st.error('No machine slots found for the selected lines.')
    else:
        try:
            approved=approved_mapping if approved_mapping is not None else None
            result,summary=allocate_all_slots(slots,day,skills,employees,eff,punched_ids,pid,pname,sid,sname,sop,sscore,emid,emname,eid_eff,ecol,approved)
            st.session_state['allocation_result']=result
            st.session_state['allocation_summary']=summary
            st.session_state['allocation_lines']=list(selected_lines)
            st.session_state['allocation_date']=chosen
        except Exception as e: st.error(f'Could not calculate allocation: {e}')

if 'allocation_result' in st.session_state and st.session_state.get('allocation_lines')==list(selected_lines) and st.session_state.get('allocation_date')==chosen:
    r=st.session_state['allocation_result']; summary=st.session_state['allocation_summary']
    a,b,c,d=st.columns(4)
    a.metric('Selected lines',len(selected_lines)); b.metric('Machine slots',summary['required_slots']); c.metric('Allocated',summary['assigned']); d.metric('Unfilled slots',summary['unfilled'])
    st.info(summary['note'])
    if summary.get('provisional',0): st.warning(f"{summary['provisional']} allocations are provisional and require supervisor skill verification. They are assigned to prevent empty machine slots, not certified as qualified.")
    st.subheader('Line summary')
    line_summary=r.groupby('Line',dropna=False).agg(required_slots=('Machine Slot','count'),allocated=('Status',lambda s:(s=='Allocated').sum()),unfilled=('Status',lambda s:(s=='Unfilled').sum()),serials_recorded=('Machine Serial Number',lambda s:(~s.astype(str).str.contains('Not recorded',case=False)).sum())).reset_index()
    st.dataframe(line_summary,use_container_width=True,hide_index=True)
    tabs=st.tabs([str(x) for x in selected_lines])
    for tab,line in zip(tabs,selected_lines):
        with tab:
            view=r[r['Line'].astype(str)==str(line)].copy()
            st.markdown(f'### {line} — {len(view)} machine slots')
            st.dataframe(view,use_container_width=True,hide_index=True)
            buf=BytesIO()
            with pd.ExcelWriter(buf,engine='openpyxl') as w: view.to_excel(w,index=False,sheet_name=str(line)[:31])
            st.download_button(f'Download {line} employee allocation (Excel)',buf.getvalue(),f'{line}_allocation_{chosen}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key=f'dl_{line}')
            st.download_button(f'Download {line} employee allocation (CSV)',view.to_csv(index=False).encode('utf-8-sig'),f'{line}_allocation_{chosen}.csv','text/csv',key=f'dlc_{line}')
    st.subheader('All machine allocations')
    st.dataframe(r,use_container_width=True,hide_index=True)
    st.download_button('Download all allocations (CSV)',r.to_csv(index=False).encode('utf-8-sig'),f'allocation_{chosen}.csv','text/csv')
    xbuf=BytesIO()
    with pd.ExcelWriter(xbuf,engine='openpyxl') as w:
        r.to_excel(w,index=False,sheet_name='All Allocations')
        line_summary.to_excel(w,index=False,sheet_name='Line Summary')
        if machine_inventory is not None: machine_inventory.to_excel(w,index=False,sheet_name='Machine Register')
    st.download_button('Download all allocations (Excel)',xbuf.getvalue(),f'allocation_{chosen}.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    st.caption('Provisional assignments must be checked by a supervisor before the operator runs that machine. Fill the Machine Skill Mapping sheet with factory-approved operation relationships to increase verified assignments.')
