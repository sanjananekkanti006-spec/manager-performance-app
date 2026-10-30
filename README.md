# Manager Performance Analytics Dashboard

A Streamlit + MySQL dashboard for monitoring employee performance, project progress and task completion.

**Stack:** Python · Streamlit · MySQL · Pandas · Plotly · mysql-connector-python

## Features
- **Dashboard** – live KPIs (employees, active staff, average score, tasks by status, overdue tasks) and interactive Plotly charts, with department / status / project filters
- **Employees** – searchable, filterable, sortable directory with CSV export
- **Add Employee** – validated form (score 0–100) with duplicate protection
- **Tasks** – view with overdue highlighting, create, update status, edit, and delete with confirmation
- **Performance Analysis** – ranking, department comparison, highest/lowest scores, score distribution and rating bands

## Project structure
```
manager-performance-app/
├── app.py                         # Streamlit UI (5 pages)
├── database.py                    # All MySQL access (parameterised queries, transactions)
├── schema.sql                     # Creates the database, tables and sample data (safe to rerun)
├── requirements.txt               # Python dependencies
├── .gitignore                     # Keeps secrets and the virtual environment out of Git
└── .streamlit/
    ├── config.toml                # Theme colour
    ├── secrets.example.toml       # Template for credentials (safe to commit)
    └── secrets.toml               # Your real credentials (NOT committed)
```

## Run locally (macOS)
```bash
cd manager-performance-app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
1. Open `schema.sql` in MySQL Workbench and run it (lightning-bolt icon).
2. Put your MySQL username and password in `.streamlit/secrets.toml`.
3. Start the app:
```bash
python -m streamlit run app.py
```
4. Open http://localhost:8501

## Troubleshooting
| Problem | Fix |
|---|---|
| MySQL access denied | Check `user` / `password` in `.streamlit/secrets.toml` |
| Unknown database / table doesn't exist | Run `schema.sql` in MySQL Workbench |
| Secrets not found | Make sure `.streamlit/secrets.toml` is inside the project folder and you run Streamlit from that folder |
| `ModuleNotFoundError` | Activate the venv (`source .venv/bin/activate`) and reinstall requirements |
| Port 8501 in use | `python -m streamlit run app.py --server.port 8502` |
| Can't reach MySQL server | Start MySQL: System Settings → MySQL → Start, or `brew services start mysql` |
# manager-performance-app
