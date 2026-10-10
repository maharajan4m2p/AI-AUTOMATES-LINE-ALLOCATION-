# Sewing Line AI Operator Allocation (No Supabase)

## Deploy
1. Upload/commit all files in this folder to the GitHub repository root.
2. Ensure `app.py`, `allocation.py`, `01_Employee_Skills.xlsx`, `02_Line_Machine_Details.xlsx`, `03_Employee_Efficiency.xlsx`, and `Employee_Details_Master.xlsx` are committed.
3. Render should install packages from `requirements.txt` and run `streamlit run app.py`.
4. Each day, upload only the daily punching file (`.xlsx`, `.xls`, `.csv`, or `.ods`) in the app.

Master workbooks are read from the repository bundle. No Supabase account, URL, key, or bucket is required. To update master data, replace the corresponding workbook in GitHub and redeploy.
