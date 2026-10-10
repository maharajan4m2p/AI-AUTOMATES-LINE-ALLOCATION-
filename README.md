# Sewing Line AI Operator Allocation — Daily Punch Only

## What changed
- Preserves the existing allocation method, line summary, employee recommendations, and CSV/Excel exports.
- Employee Details, Employee Skills, Employee Efficiency, Line Machine Details, and optional Staffing Requirements are bundled with the project.
- The sidebar now asks for only the daily punching file (XLSX, XLS, CSV, or ODS).
- If Supabase is configured, bundled master files are automatically seeded to the private Storage bucket when missing, then reloaded from cloud storage.
- Without Supabase, bundled masters work for local development, but Render Free may lose runtime-local changes during restart/redeploy.

## Run locally (Windows / VS Code)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Render Free persistent storage
1. Create a **private** Supabase Storage bucket named `sewing-master-data`.
2. In Render → your service → Environment, set:
   - `SUPABASE_URL` = your Supabase project URL
   - `SUPABASE_SERVICE_ROLE_KEY` = your Supabase service-role key
   - `SUPABASE_STORAGE_BUCKET` = `sewing-master-data`
3. Redeploy. On startup the app attempts to upload any bundled master file that is missing from the bucket.
4. Verify that the files appear in the bucket and that Render logs show no storage errors.

Keep the service-role key secret. Never commit it to GitHub or expose it in the app UI.

## Daily workflow
1. Open the app.
2. Upload only that day's punching file in the sidebar.
3. Select the sewing lines.
4. Click **APPLY & ANALYSE SELECTED LINES**.
5. Review and export the line summary and employee recommendations.

## Notes
- The allocation uses employees with punching records on the selected attendance date and matching skill records.
- Employee IDs not present in the skill matrix cannot be assigned; check the warning about ID mismatches.
- The first deployment should be tested locally and on Render before relying on the results for production.


## Important for daily use
- Open this project folder (not an older extracted copy) in VS Code.
- Run `streamlit run app.py`.
- The sidebar should show only the Daily Punching Machine Data uploader; the master files are bundled and loaded automatically.
- On Render Free, configure `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET=sewing-master-data` and create a private bucket with that name for persistence across restarts/redeploys.
- `09_punching_data.ods` is included only as a sample/reference; upload the current day's punch file in the app each day.
