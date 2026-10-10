# Sewing Line AI Operator Allocation (No Supabase)

## Deploy
1. Upload/commit all files in this folder to the GitHub repository root.
2. Ensure `app.py`, `allocation.py`, `01_Employee_Skills.xlsx`, `02_Line_Machine_Details.xlsx`, `03_Employee_Efficiency.xlsx`, and `Employee_Details_Master.xlsx` are committed.
3. Render should install packages from `requirements.txt` and run `streamlit run app.py`.
4. Each day, upload only the daily punching file (`.xlsx`, `.xls`, `.csv`, or `.ods`) in the app.

Master workbooks are read from the repository bundle. No Supabase account, URL, key, or bucket is required. To update master data, replace the corresponding workbook in GitHub and redeploy.


## Allocation policy update

- No Supabase or external database is used. Master Excel files are bundled with the app.
- Upload only the daily punching file.
- Global assignment across selected lines balances slot priority across lines and prevents duplicate employee assignments.
- Strict skill policy: an employee can be assigned only when their positive skill score/YES status matches the exact operation name (case, spaces, and punctuation are normalized). No broad-skill fallback is used.
- The bundled line-machine master currently uses machine family names such as Singer / Over Lock / Flat lock, while the skill matrix may use garment operations such as TOP STITCH / SLEEVE JOINT. If names do not match, strict mode correctly leaves those slots unfilled. Update the master data to a common operation vocabulary or add a verified mapping before expecting those slots to fill.
