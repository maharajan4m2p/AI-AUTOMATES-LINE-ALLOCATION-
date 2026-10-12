import re
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

def normalize_text(v):
    if pd.isna(v): return ""
    return re.sub(r"\s+", " ", str(v)).strip()

def normalize_id(v):
    if pd.isna(v): return ""
    s=str(v).strip().upper()
    # Excel sometimes reads IDs as numeric floats; preserve alphanumeric IDs and remove separators.
    if re.fullmatch(r"\d+\.0", s): s=s[:-2]
    return re.sub(r"[^A-Z0-9]", "", s)

def find_column(df, candidates):
    lookup={normalize_text(c).lower():c for c in df.columns}
    for x in candidates:
        if normalize_text(x).lower() in lookup: return lookup[normalize_text(x).lower()]
    def compact(x): return re.sub(r"[^a-z0-9]", "", normalize_text(x).lower())
    lookup2={compact(c):c for c in df.columns}
    for x in candidates:
        if compact(x) in lookup2: return lookup2[compact(x)]
    raise ValueError("Could not find columns: "+", ".join(candidates)+". Available columns: "+", ".join(map(str,df.columns)))

def to_num(s):
    return pd.to_numeric(s.astype(str).str.replace('%','',regex=False).str.replace(',','',regex=False).str.strip(),errors='coerce')

def is_positive_skill(v):
    n=pd.to_numeric(pd.Series([v]),errors='coerce').iloc[0]
    if pd.notna(n): return n>0
    return normalize_text(v).lower() in {'yes','y','true','1','skilled'}

def build_machine_slots(lines, selected_lines, line_col, machine_col, serial_col=None, count_col=None):
    slots=[]
    for line in selected_lines:
        lr=lines[lines[line_col].map(lambda x:normalize_text(x).lower())==normalize_text(line).lower()].copy()
        for _,row in lr.iterrows():
            typ=normalize_text(row[machine_col])
            if not typ: continue
            count=pd.to_numeric(row[count_col],errors='coerce') if count_col else 1
            count=int(count) if pd.notna(count) else 0
            count=max(0,count)
            serials=[]
            if serial_col and pd.notna(row.get(serial_col,'')):
                serials=[x.strip() for x in str(row[serial_col]).split(',') if x.strip() and x.strip().lower()!='nan']
            for i in range(count):
                serial=serials[i] if i<len(serials) else 'Not recorded in machine inventory'
                slots.append({'Line':line,'Operation':typ,'Machine Slot':i+1,'Machine Serial Number':serial,'Machine Type':typ})
    return slots

def allocate_all_slots(slots, punches, skills, employee_master, efficiency, date_ids, punch_id_col, punch_name_col=None,
                       skill_id_col=None, skill_name_col=None, skill_op_col=None, skill_score_col=None,
                       emp_master_id_col=None, emp_master_name_col=None, efficiency_id_col=None, efficiency_col=None,
                       approved_mapping=None):
    """Fill every machine slot if there are enough distinct punched IDs.

    Skill-qualified candidates are ranked first. When the source data has no verified machine-to-operation
    mapping or a worker has no skill row, a provisional allocation is made so the slot is not left empty;
    the report explicitly marks that assignment as requiring skill verification.
    """
    # Build punch roster for selected date; caller has already filtered the punch frame.
    pn=punches.copy()
    pn['_id']=pn[punch_id_col].map(normalize_id)
    pn=pn[pn['_id']!=''].drop_duplicates('_id',keep='first')
    punch_names={}
    if punch_name_col:
        punch_names={normalize_id(r[punch_id_col]):normalize_text(r[punch_name_col]) for _,r in pn.iterrows() if normalize_id(r[punch_id_col])}
    ids=set(date_ids) if date_ids is not None else set(pn['_id'])
    pn=pn[pn['_id'].isin(ids)]
    punch_names={normalize_id(r[punch_id_col]):normalize_text(r[punch_name_col]) for _,r in pn.iterrows() if punch_name_col and normalize_id(r[punch_id_col]) and normalize_text(r[punch_name_col])}
    if not ids: return pd.DataFrame(), {'required_slots':len(slots),'assigned':0,'unfilled':len(slots),'note':'No punched employees found for the selected date.'}

    names={}; details={}
    if employee_master is not None and emp_master_id_col and emp_master_name_col:
        for _,r in employee_master.iterrows():
            eid=normalize_id(r[emp_master_id_col]); name=normalize_text(r[emp_master_name_col])
            if eid and name: names[eid]=name; details[eid]={str(c):r[c] for c in employee_master.columns}
    # Add names and job details from every available source, using normalized IDs.
    # Master data wins; efficiency/skills/punching are fallback sources for missing names.
    if efficiency is not None and efficiency_id_col:
        try:
            eff_name_col=find_column(efficiency,['Employee Name','Emp Name','Name'])
            eff_designation_col=find_column(efficiency,['Designation','Job Title'])
        except ValueError:
            eff_name_col=eff_designation_col=None
        for _,r in efficiency.iterrows():
            eid=normalize_id(r[efficiency_id_col])
            if not eid: continue
            nm=normalize_text(r[eff_name_col]) if eff_name_col else ''
            if nm and nm.lower() not in {'nan','none','null'}: names.setdefault(eid,nm)
            if eid not in details: details[eid]={}
            if eff_designation_col and normalize_text(r[eff_designation_col]):
                details[eid].setdefault('Designation',r[eff_designation_col])
    if skill_id_col and skill_name_col:
        for _,r in skills.iterrows():
            eid=normalize_id(r[skill_id_col]); name=normalize_text(r[skill_name_col])
            if eid and name and name.lower() not in {'nan','none','null'}: names.setdefault(eid,name)
    for eid,nm in punch_names.items():
        if nm and nm.lower() not in {'nan','none','null'}: names.setdefault(eid,nm)

    skill_rows=skills.copy() if skills is not None else pd.DataFrame()
    if not skill_rows.empty and skill_id_col:
        skill_rows['_id']=skill_rows[skill_id_col].map(normalize_id)
        skill_rows['_positive']=skill_rows[skill_score_col].map(is_positive_skill) if skill_score_col else False
    else:
        skill_rows=pd.DataFrame(columns=['_id','_positive'])
    positive_ids=set(skill_rows.loc[skill_rows['_positive']==True,'_id']) if not skill_rows.empty else set()
    # Machine family exact mappings are only considered verified when explicitly supplied in the workbook.
    map_by_machine={}
    if approved_mapping is not None and not approved_mapping.empty:
        mc=find_column(approved_mapping,['Machine Type'])
        sc=find_column(approved_mapping,['Approved Skill Operation','Skill Operation'])
        for _,r in approved_mapping.iterrows():
            mt=normalize_text(r[mc]).lower(); so=normalize_text(r[sc]).lower()
            if mt and so: map_by_machine.setdefault(mt,set()).add(so)
    skill_ops={}
    if not skill_rows.empty and skill_op_col:
        for eid,group in skill_rows[skill_rows['_positive']].groupby('_id'):
            skill_ops[eid]={normalize_text(x).lower() for x in group[skill_op_col] if normalize_text(x)}

    efmap={}
    if efficiency is not None and efficiency_id_col and efficiency_col:
        ef=efficiency.copy(); ef['_id']=ef[efficiency_id_col].map(normalize_id); ef['_eff']=to_num(ef[efficiency_col])
        if not ef.empty and ef['_eff'].dropna().size and ef['_eff'].max()<=1.5: ef['_eff']=ef['_eff']*100
        ef['_eff']=ef['_eff'].clip(0,100)
        efmap=ef[ef['_id']!=''].groupby('_id')['_eff'].max().to_dict()

    candidates=sorted(ids)
    if len(candidates)<len(slots):
        # Cannot produce duplicate IDs; report genuine capacity limit.
        capacity_note=f'Only {len(candidates)} distinct employees punched in for {len(slots)} machine slots. {len(slots)-len(candidates)} slots cannot be filled without duplicate employees or another worker.'
    else: capacity_note=''
    # Cost: explicit approved skill mapping first, then employees with a skill record, then employees without a skill record.
    # Efficiency breaks ties; all candidate/slot pairs remain assignable so every slot can be staffed provisionally.
    n_slots=len(slots); n_emp=len(candidates)
    cost=np.zeros((n_slots,n_emp),dtype=float)
    for i,slot in enumerate(slots):
        mt=normalize_text(slot['Machine Type']).lower()
        approved=map_by_machine.get(mt,set())
        for j,eid in enumerate(candidates):
            ops=skill_ops.get(eid,set())
            if approved and ops.intersection(approved):
                tier=0; qual='Verified mapping match'
            elif eid in positive_ids:
                tier=1000; qual='Provisional - machine skill mapping not verified'
            else:
                tier=100000; qual='Provisional - missing positive skill record'
            eff=float(efmap.get(eid,0) or 0)
            # stable deterministic tie break
            cost[i,j]=tier-eff*0.01+j*1e-7
    rows,cols=linear_sum_assignment(cost)
    assigned={int(i):candidates[int(j)] for i,j in zip(rows,cols)}
    output=[]
    for i,slot in enumerate(slots):
        eid=assigned.get(i,'')
        ops=skill_ops.get(eid,set())
        approved=map_by_machine.get(normalize_text(slot['Machine Type']).lower(),set())
        if eid and approved and ops.intersection(approved):
            status='Recommended'; reason='Matched an explicitly approved machine-to-skill mapping.'
        elif eid in positive_ids:
            status='Assigned - Verify skill'; reason='Employee has a positive skill record, but this machine type has no verified matching operation mapping.'
        elif eid:
            status='Assigned - Verify qualification'; reason='No positive skill record found; supervisor must verify qualification before operating this machine.'
        else:
            status='Unfilled'; reason='No distinct punched employee available.'
        d=details.get(eid,{})
        # Pull available worker details, never fabricate missing values.
        output.append({
            'Line':slot['Line'],'Machine Type':slot['Machine Type'],'Operation':slot['Operation'],
            'Machine Slot':slot['Machine Slot'],'Machine Serial Number':slot['Machine Serial Number'],
            'Employee Name':names.get(eid,'Name not found in master data') if eid else '',
            'Employee ID':eid,'Department':normalize_text(d.get('Department','')),
            'Designation':normalize_text(d.get('Designation','')),'Employment Status':normalize_text(d.get('Status','')),
            'Avg Efficiency (%)':round(float(efmap[eid]),2) if eid and eid in efmap and pd.notna(efmap[eid]) else None,
            'Skill Verification Status':status,'Status':'Allocated' if eid else 'Unfilled','Reason':reason
        })
    result=pd.DataFrame(output)
    assigned_count=int((result['Status']=='Allocated').sum()) if not result.empty else 0
    return result, {'required_slots':len(slots),'assigned':assigned_count,'unfilled':int(len(slots)-assigned_count),'provisional':int(result['Skill Verification Status'].astype(str).str.startswith('Assigned - Verify').sum()) if not result.empty else 0,'verified':int((result['Skill Verification Status']=='Recommended').sum()) if not result.empty else 0,'note':capacity_note or 'Assignments are unique by employee ID. Any provisional assignment requires supervisor skill verification before production use.'}
