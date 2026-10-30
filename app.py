"""
app.py
------
Manager Performance Analytics Dashboard (Streamlit).

Pages:
  1. Dashboard             - KPIs and charts from live MySQL data
  2. Employees             - searchable, filterable employee directory
  3. Add Employee          - validated form that inserts into MySQL
  4. Tasks                 - view, create, update, edit and delete tasks
  5. Performance Analysis  - rankings, department comparison, distribution

All database work lives in database.py; this file only handles the UI.
Run with:  python -m streamlit run app.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import database as db

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Manager Performance Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

STATUS_COLORS = {
    "Completed": "#2E8B57",
    "In Progress": "#2F6FB5",
    "Pending": "#D4A017",
}
SCORE_BANDS = [
    (90, "Excellent"),
    (80, "Good"),
    (70, "Satisfactory"),
    (0, "Needs improvement"),
]

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 3rem;}
      [data-testid="stMetricValue"] {font-size: 1.9rem; font-weight: 600;}
      [data-testid="stMetricLabel"] p {font-size: 0.9rem; opacity: 0.8;}
      h1 {font-weight: 700; letter-spacing: -0.01em;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data loading (cached for 30 s; cleared straight after every write)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30, show_spinner=False)
def load_employees() -> pd.DataFrame:
    df = db.get_employees()
    if not df.empty:
        df["performance_score"] = pd.to_numeric(df["performance_score"], errors="coerce")
    return df


@st.cache_data(ttl=30, show_spinner=False)
def load_tasks() -> pd.DataFrame:
    df = db.get_tasks_with_employees()
    if df.empty:
        return df
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["employee_id"] = df["employee_id"].astype("Int64")
    df["employee_name"] = df["employee_name"].fillna("Unassigned")
    today = pd.Timestamp(date.today())
    df["is_overdue"] = (
        df["due_date"].notna()
        & (df["due_date"] < today)
        & (df["task_status"] != "Completed")
    )
    return df


def refresh_data() -> None:
    st.cache_data.clear()


def get_data_or_stop() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load both tables; show a clear error and stop the page if MySQL fails."""
    try:
        return load_employees(), load_tasks()
    except db.DatabaseError as err:
        st.error(f"❌ {err}")
        st.info("See the troubleshooting section of the README, then press **Refresh data** in the sidebar.")
        st.stop()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def set_flash(kind: str, message: str) -> None:
    """Store a message so it survives st.rerun()."""
    st.session_state["flash"] = (kind, message)


def show_flash() -> None:
    flash = st.session_state.pop("flash", None)
    if flash:
        kind, message = flash
        getattr(st, kind)(message)


def score_band(score: float) -> str:
    if pd.isna(score):
        return "No score"
    for threshold, label in SCORE_BANDS:
        if score >= threshold:
            return label
    return "Needs improvement"


def fmt_score(value) -> str:
    return "–" if value is None or pd.isna(value) else f"{value:.1f}"


def options_from(series: pd.Series) -> list[str]:
    return sorted(series.dropna().astype(str).unique().tolist())


def kpi(column, label: str, value, help_text: str | None = None) -> None:
    with column.container(border=True):
        st.metric(label, value, help=help_text)


def style_fig(fig, height: int = 360):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        legend_title_text="",
        title_font_size=16,
    )
    return fig


def show_chart(fig, height: int = 360) -> None:
    st.plotly_chart(style_fig(fig, height), width="stretch")


def employee_label_map(employees: pd.DataFrame) -> dict:
    """{employee_id: 'Name (Department)'} for select boxes."""
    return {
        int(r.employee_id): f"{r.employee_name} ({r.department or 'No department'})"
        for r in employees.itertuples()
    }


def as_python_date(value):
    return None if value is None or pd.isna(value) else pd.Timestamp(value).date()


TASK_TABLE_CONFIG = {
    "task_id": st.column_config.NumberColumn("Task ID", format="%d"),
    "task_name": "Task",
    "employee_name": "Assigned to",
    "project_name": "Project",
    "task_status": "Status",
    "due_date": st.column_config.DateColumn("Due date", format="DD MMM YYYY"),
    "overdue": "Overdue",
}


def task_table(df: pd.DataFrame) -> None:
    """Show tasks with overdue rows highlighted in red."""
    view = df[["task_id", "task_name", "employee_name", "project_name",
               "task_status", "due_date", "is_overdue"]].copy()
    view["overdue"] = view["is_overdue"].map({True: "⚠️ Overdue", False: ""})
    overdue_mask = view["is_overdue"].tolist()
    view = view.drop(columns="is_overdue").reset_index(drop=True)

    def highlight(row):
        colour = "background-color: rgba(220, 53, 69, 0.15)" if overdue_mask[row.name] else ""
        return [colour] * len(row)

    st.dataframe(
        view.style.apply(highlight, axis=1),
        column_config=TASK_TABLE_CONFIG,
        hide_index=True,
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
PAGES = {
    "📊 Dashboard": "dashboard",
    "👥 Employees": "employees",
    "➕ Add Employee": "add_employee",
    "✅ Tasks": "tasks",
    "📈 Performance Analysis": "performance",
}

with st.sidebar:
    st.title("📊 Manager Analytics")
    st.caption("Team performance and task tracking")
    page = PAGES[st.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")]
    st.divider()

    ok, message = db.test_connection()
    if ok:
        st.success(f"🟢 {message}")
    else:
        st.error(f"🔴 {message}")

    if st.button("🔄 Refresh data", width="stretch"):
        refresh_data()
        st.rerun()
    st.caption(f"Today: {date.today():%d %b %Y}")


# ---------------------------------------------------------------------------
# Page 1: Dashboard
# ---------------------------------------------------------------------------
def page_dashboard() -> None:
    st.title("📊 Manager Performance Dashboard")
    st.caption("Live figures from the manager_analytics database.")
    employees, tasks = get_data_or_stop()

    with st.expander("🔎 Filters", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        dept_f = c1.multiselect("Department", options_from(employees.get("department", pd.Series(dtype=str))))
        status_f = c2.multiselect("Employee status", options_from(employees.get("status", pd.Series(dtype=str))))
        project_f = c3.multiselect("Project", options_from(tasks.get("project_name", pd.Series(dtype=str))))
        tstatus_f = c4.multiselect("Task status", db.TASK_STATUSES)

    emp = employees.copy()
    if dept_f:
        emp = emp[emp["department"].isin(dept_f)]
    if status_f:
        emp = emp[emp["status"].isin(status_f)]

    tsk = tasks.copy()
    if not tsk.empty:
        if dept_f:
            tsk = tsk[tsk["department"].isin(dept_f)]
        if status_f:
            tsk = tsk[tsk["employee_id"].isin(emp["employee_id"])]
        if project_f:
            tsk = tsk[tsk["project_name"].isin(project_f)]
        if tstatus_f:
            tsk = tsk[tsk["task_status"].isin(tstatus_f)]

    # KPIs
    total_tasks = len(tsk)
    count = (lambda s: int((tsk["task_status"] == s).sum())) if total_tasks else (lambda s: 0)
    overdue = int(tsk["is_overdue"].sum()) if total_tasks else 0
    avg_score = emp["performance_score"].mean() if not emp.empty else None

    r1 = st.columns(4)
    kpi(r1[0], "👥 Total employees", len(emp))
    kpi(r1[1], "🟢 Active employees", int((emp["status"] == "Active").sum()) if not emp.empty else 0)
    kpi(r1[2], "⭐ Average score", fmt_score(avg_score), "Mean performance score (0–100)")
    kpi(r1[3], "📋 Total tasks", total_tasks)
    r2 = st.columns(4)
    kpi(r2[0], "✅ Completed", count("Completed"))
    kpi(r2[1], "⏳ Pending", count("Pending"))
    kpi(r2[2], "🔧 In progress", count("In Progress"))
    kpi(r2[3], "⚠️ Overdue", overdue, "Past the due date and not completed")

    if emp.empty and tsk.empty:
        st.info("No data matches these filters. Clear a filter or add employees and tasks.")
        return

    st.subheader("Performance")
    c1, c2 = st.columns(2)
    with c1:
        if emp.empty:
            st.info("No employees match the filters.")
        else:
            dept_avg = (emp.groupby("department", dropna=False)["performance_score"]
                        .mean().round(1).reset_index().sort_values("performance_score", ascending=False))
            fig = px.bar(dept_avg, x="department", y="performance_score", text="performance_score",
                         title="Average performance score by department",
                         labels={"department": "Department", "performance_score": "Average score"})
            fig.update_yaxes(range=[0, 100])
            show_chart(fig)
    with c2:
        if not emp.empty:
            comp = emp.sort_values("performance_score")
            fig = px.bar(comp, x="performance_score", y="employee_name", color="department",
                         orientation="h", text="performance_score",
                         title="Employee performance comparison",
                         labels={"performance_score": "Score", "employee_name": "", "department": "Department"})
            fig.update_xaxes(range=[0, 100])
            show_chart(fig)

    st.subheader("Tasks and teams")
    c3, c4, c5 = st.columns(3)
    with c3:
        if tsk.empty:
            st.info("No tasks match the filters.")
        else:
            by_status = tsk["task_status"].value_counts().reset_index()
            by_status.columns = ["task_status", "tasks"]
            fig = px.pie(by_status, names="task_status", values="tasks", hole=0.55,
                         color="task_status", color_discrete_map=STATUS_COLORS,
                         title="Tasks by status")
            fig.update_traces(textinfo="value+percent")
            show_chart(fig)
    with c4:
        if not tsk.empty:
            by_proj = (tsk.groupby(["project_name", "task_status"]).size()
                       .reset_index(name="tasks"))
            fig = px.bar(by_proj, x="project_name", y="tasks", color="task_status",
                         color_discrete_map=STATUS_COLORS, title="Task distribution by project",
                         labels={"project_name": "Project", "tasks": "Tasks", "task_status": "Status"})
            fig.update_yaxes(dtick=1)
            show_chart(fig)
    with c5:
        if not emp.empty:
            by_dept = emp["department"].fillna("No department").value_counts().reset_index()
            by_dept.columns = ["department", "employees"]
            fig = px.bar(by_dept, x="department", y="employees", text="employees",
                         title="Employees by department",
                         labels={"department": "Department", "employees": "Employees"})
            fig.update_yaxes(dtick=1)
            show_chart(fig)

    if not tsk.empty and tsk["is_overdue"].any():
        st.subheader("⚠️ Overdue tasks")
        task_table(tsk[tsk["is_overdue"]])


# ---------------------------------------------------------------------------
# Page 2: Employees
# ---------------------------------------------------------------------------
def page_employees() -> None:
    st.title("👥 Employee Directory")
    employees, _ = get_data_or_stop()

    if employees.empty:
        st.info("No employees yet. Use **➕ Add Employee** to create the first one.")
        return

    c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1.5])
    search = c1.text_input("Search by name", placeholder="e.g. Ananya")
    dept_f = c2.multiselect("Department", options_from(employees["department"]))
    status_f = c3.multiselect("Status", options_from(employees["status"]))
    sort_by = c4.selectbox("Sort by", ["Employee ID", "Name (A–Z)", "Score (high → low)", "Score (low → high)"])

    df = employees.copy()
    if search.strip():
        df = df[df["employee_name"].str.contains(search.strip(), case=False, na=False, regex=False)]
    if dept_f:
        df = df[df["department"].isin(dept_f)]
    if status_f:
        df = df[df["status"].isin(status_f)]

    sorts = {
        "Employee ID": ("employee_id", True),
        "Name (A–Z)": ("employee_name", True),
        "Score (high → low)": ("performance_score", False),
        "Score (low → high)": ("performance_score", True),
    }
    col, asc = sorts[sort_by]
    df = df.sort_values(col, ascending=asc)

    st.caption(f"Showing {len(df)} of {len(employees)} employees")
    if df.empty:
        st.warning("No employees match your search. Try a different name or clear the filters.")
        return

    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "employee_id": st.column_config.NumberColumn("Employee ID", format="%d"),
            "employee_name": "Name",
            "department": "Department",
            "job_title": "Job title",
            "manager_name": "Manager",
            "performance_score": st.column_config.ProgressColumn(
                "Performance score", min_value=0, max_value=100, format="%.1f"),
            "status": "Status",
        },
    )
    st.download_button(
        "⬇️ Download as CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"employees_{date.today():%Y%m%d}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Page 3: Add Employee
# ---------------------------------------------------------------------------
def page_add_employee() -> None:
    st.title("➕ Add Employee")
    st.caption("Fields marked * are required.")
    show_flash()
    employees, _ = get_data_or_stop()

    # A new form key after each successful save gives a fresh, empty form and
    # stops a double-click from submitting the same values twice.
    st.session_state.setdefault("emp_form_n", 0)
    form_key = f"add_employee_{st.session_state['emp_form_n']}"

    with st.form(form_key):
        c1, c2 = st.columns(2)
        name = c1.text_input("Employee name *", max_chars=100)
        department = c2.selectbox(
            "Department *", options_from(employees["department"]) if not employees.empty else [],
            index=None, placeholder="Choose or type a new department", accept_new_options=True)
        job_title = c1.text_input("Job title *", max_chars=100)
        manager = c2.selectbox(
            "Manager name *", options_from(employees["manager_name"]) if not employees.empty else [],
            index=None, placeholder="Choose or type a manager", accept_new_options=True)
        score = c1.number_input("Performance score (0–100) *", min_value=0.0, max_value=100.0,
                                value=None, step=0.5, format="%.1f", placeholder="e.g. 85")
        status = c2.selectbox("Employment status *", db.EMPLOYEE_STATUSES, index=0)
        submitted = st.form_submit_button("Save employee", type="primary")

    if submitted:
        name = (name or "").strip()
        department = (department or "").strip()
        job_title = (job_title or "").strip()
        manager = (manager or "").strip()

        errors = []
        if not name:
            errors.append("Employee name is required.")
        if not department:
            errors.append("Department is required.")
        elif len(department) > 50:
            errors.append("Department must be 50 characters or fewer.")
        if not job_title:
            errors.append("Job title is required.")
        if not manager:
            errors.append("Manager name is required.")
        elif len(manager) > 100:
            errors.append("Manager name must be 100 characters or fewer.")
        if score is None:
            errors.append("Performance score is required.")
        elif not 0 <= score <= 100:
            errors.append("Performance score must be between 0 and 100.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                if db.employee_exists(name, department, job_title):
                    st.warning(f"⚠️ {name} ({job_title}, {department}) already exists, so nothing was saved.")
                else:
                    new_id = db.add_employee(name, department, job_title, manager, round(float(score), 2), status)
                    refresh_data()
                    st.session_state["emp_form_n"] += 1
                    set_flash("success", f"✅ Saved {name} as employee #{new_id}.")
                    st.rerun()
            except db.DatabaseError as err:
                st.error(f"❌ Could not save the employee. {err}")

    st.subheader("Current employees")
    if employees.empty:
        st.info("No employees yet.")
    else:
        st.dataframe(
            employees.sort_values("employee_id", ascending=False),
            hide_index=True, width="stretch",
            column_config={
                "employee_id": st.column_config.NumberColumn("ID", format="%d"),
                "employee_name": "Name", "department": "Department", "job_title": "Job title",
                "manager_name": "Manager",
                "performance_score": st.column_config.NumberColumn("Score", format="%.1f"),
                "status": "Status",
            },
        )


# ---------------------------------------------------------------------------
# Page 4: Tasks
# ---------------------------------------------------------------------------
def page_tasks() -> None:
    st.title("✅ Tasks")
    show_flash()
    employees, tasks = get_data_or_stop()
    emp_labels = employee_label_map(employees)
    assignee_options = [None] + list(emp_labels.keys())

    def assignee_label(emp_id):
        return "Unassigned" if emp_id is None else emp_labels.get(emp_id, f"Employee #{emp_id}")

    tab_view, tab_new, tab_edit, tab_delete = st.tabs(
        ["📋 All tasks", "➕ New task", "✏️ Edit task", "🗑️ Delete task"])

    # ---- View + quick status update ----
    with tab_view:
        if tasks.empty:
            st.info("No tasks yet. Create one in the **➕ New task** tab.")
        else:
            c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1])
            emp_f = c1.multiselect("Employee", options_from(tasks["employee_name"]))
            proj_f = c2.multiselect("Project", options_from(tasks["project_name"]))
            stat_f = c3.multiselect("Status", db.TASK_STATUSES)
            only_overdue = c4.toggle("Overdue only")

            df = tasks.copy()
            if emp_f:
                df = df[df["employee_name"].isin(emp_f)]
            if proj_f:
                df = df[df["project_name"].isin(proj_f)]
            if stat_f:
                df = df[df["task_status"].isin(stat_f)]
            if only_overdue:
                df = df[df["is_overdue"]]

            st.caption(f"Showing {len(df)} of {len(tasks)} tasks · "
                       f"{int(tasks['is_overdue'].sum())} overdue (highlighted in red)")
            if df.empty:
                st.warning("No tasks match these filters.")
            else:
                task_table(df)

            st.subheader("Update task status")
            task_ids = tasks["task_id"].astype(int).tolist()
            names = dict(zip(task_ids, tasks["task_name"]))
            current = dict(zip(task_ids, tasks["task_status"]))
            with st.form("quick_status"):
                c1, c2 = st.columns([2, 1])
                tid = c1.selectbox("Task", task_ids, format_func=lambda i: f"#{i} · {names[i]} ({current[i]})")
                new_status = c2.selectbox("New status", db.TASK_STATUSES)
                if st.form_submit_button("Update status", type="primary"):
                    if current[tid] == new_status:
                        st.info(f"Task #{tid} is already {new_status}.")
                    else:
                        try:
                            db.update_task_status(int(tid), new_status)
                            refresh_data()
                            set_flash("success", f"✅ Task #{tid} is now {new_status}.")
                            st.rerun()
                        except db.DatabaseError as err:
                            st.error(f"❌ Could not update the status. {err}")

    # ---- Create ----
    with tab_new:
        st.session_state.setdefault("task_form_n", 0)
        with st.form(f"new_task_{st.session_state['task_form_n']}"):
            c1, c2 = st.columns(2)
            t_name = c1.text_input("Task name *", max_chars=150)
            t_project = c2.selectbox(
                "Project *", options_from(tasks["project_name"]) if not tasks.empty else [],
                index=None, placeholder="Choose or type a new project", accept_new_options=True)
            t_emp = c1.selectbox("Assign to", assignee_options, format_func=assignee_label)
            t_status = c2.selectbox("Status", db.TASK_STATUSES)
            t_due = c1.date_input("Due date *", value=None, format="DD/MM/YYYY")
            create = st.form_submit_button("Create task", type="primary")

        if create:
            t_name = (t_name or "").strip()
            t_project = (t_project or "").strip()
            errors = []
            if not t_name:
                errors.append("Task name is required.")
            if not t_project:
                errors.append("Project is required.")
            elif len(t_project) > 100:
                errors.append("Project name must be 100 characters or fewer.")
            if t_due is None:
                errors.append("Due date is required.")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                try:
                    if db.task_exists(t_name, t_emp, t_project):
                        st.warning("⚠️ This task already exists for that person and project, so nothing was saved.")
                    else:
                        new_id = db.add_task(t_name, t_emp, t_project, t_status, t_due)
                        refresh_data()
                        st.session_state["task_form_n"] += 1
                        set_flash("success", f"✅ Created task #{new_id}: {t_name}.")
                        st.rerun()
                except db.DatabaseError as err:
                    st.error(f"❌ Could not create the task. {err}")

    # ---- Edit ----
    with tab_edit:
        if tasks.empty:
            st.info("There are no tasks to edit yet.")
        else:
            ids = tasks["task_id"].astype(int).tolist()
            lookup = tasks.set_index("task_id")
            tid = st.selectbox("Task to edit", ids, key="edit_pick",
                               format_func=lambda i: f"#{i} · {lookup.loc[i, 'task_name']}")
            row = lookup.loc[tid]
            current_emp = None if pd.isna(row["employee_id"]) else int(row["employee_id"])
            if current_emp is not None and current_emp not in assignee_options:
                assignee_options.append(current_emp)
            projects = options_from(tasks["project_name"])

            # The form key includes the task ID so defaults reload when you pick another task.
            with st.form(f"edit_task_{tid}"):
                c1, c2 = st.columns(2)
                e_name = c1.text_input("Task name *", value=row["task_name"], max_chars=150)
                e_project = c2.selectbox(
                    "Project *", projects,
                    index=projects.index(row["project_name"]) if row["project_name"] in projects else None,
                    accept_new_options=True)
                e_emp = c1.selectbox("Assign to", assignee_options,
                                     index=assignee_options.index(current_emp), format_func=assignee_label)
                e_status = c2.selectbox(
                    "Status", db.TASK_STATUSES,
                    index=db.TASK_STATUSES.index(row["task_status"]) if row["task_status"] in db.TASK_STATUSES else 0)
                e_due = c1.date_input("Due date *", value=as_python_date(row["due_date"]), format="DD/MM/YYYY")
                save = st.form_submit_button("Save changes", type="primary")

            if save:
                e_name = (e_name or "").strip()
                e_project = (e_project or "").strip()
                if not e_name or not e_project or e_due is None:
                    st.error("Task name, project and due date are all required.")
                else:
                    try:
                        db.update_task(int(tid), e_name, e_emp, e_project, e_status, e_due)
                        refresh_data()
                        set_flash("success", f"✅ Saved changes to task #{tid}.")
                        st.rerun()
                    except db.DatabaseError as err:
                        st.error(f"❌ Could not save the changes. {err}")

    # ---- Delete ----
    with tab_delete:
        if tasks.empty:
            st.info("There are no tasks to delete.")
        else:
            ids = tasks["task_id"].astype(int).tolist()
            lookup = tasks.set_index("task_id")
            tid = st.selectbox("Task to delete", ids, key="delete_pick",
                               format_func=lambda i: f"#{i} · {lookup.loc[i, 'task_name']}")
            row = lookup.loc[tid]
            due = as_python_date(row["due_date"])
            st.warning(
                f"**#{tid} · {row['task_name']}**  \n"
                f"Assigned to {row['employee_name']} · {row['project_name']} · "
                f"{row['task_status']} · due {due:%d %b %Y}" if due else
                f"**#{tid} · {row['task_name']}**  \nAssigned to {row['employee_name']}"
            )
            confirm = st.checkbox("I understand this task will be permanently deleted.", key=f"confirm_del_{tid}")
            if st.button("Delete task", type="primary", disabled=not confirm, key=f"del_btn_{tid}"):
                try:
                    deleted = db.delete_task(int(tid))
                    refresh_data()
                    if deleted:
                        set_flash("success", f"🗑️ Deleted task #{tid}.")
                    else:
                        set_flash("info", f"Task #{tid} had already been deleted.")
                    st.rerun()
                except db.DatabaseError as err:
                    st.error(f"❌ Could not delete the task. {err}")


# ---------------------------------------------------------------------------
# Page 5: Performance Analysis
# ---------------------------------------------------------------------------
def page_performance() -> None:
    st.title("📈 Performance Analysis")
    employees, _ = get_data_or_stop()

    if employees.empty:
        st.info("Add employees to see performance analysis.")
        return

    c1, c2 = st.columns(2)
    dept_f = c1.multiselect("Department", options_from(employees["department"]))
    status_f = c2.multiselect("Employee status", options_from(employees["status"]))

    df = employees.dropna(subset=["performance_score"]).copy()
    if dept_f:
        df = df[df["department"].isin(dept_f)]
    if status_f:
        df = df[df["status"].isin(status_f)]

    if df.empty:
        st.warning("No employees match these filters.")
        return

    top = df.loc[df["performance_score"].idxmax()]
    low = df.loc[df["performance_score"].idxmin()]
    k = st.columns(4)
    kpi(k[0], "🏆 Highest score", fmt_score(top["performance_score"]), top["employee_name"])
    kpi(k[1], "🔻 Lowest score", fmt_score(low["performance_score"]), low["employee_name"])
    kpi(k[2], "⭐ Average score", fmt_score(df["performance_score"].mean()))
    kpi(k[3], "👥 Employees analysed", len(df))
    st.caption(f"Top performer: **{top['employee_name']}** ({top['department']}) · "
               f"Lowest: **{low['employee_name']}** ({low['department']}).")

    st.subheader("Employee ranking")
    ranking = df.sort_values("performance_score", ascending=False).copy()
    ranking.insert(0, "rank", ranking["performance_score"].rank(ascending=False, method="min").astype(int))
    ranking["band"] = ranking["performance_score"].apply(score_band)
    st.dataframe(
        ranking[["rank", "employee_name", "department", "job_title", "manager_name",
                 "performance_score", "band", "status"]],
        hide_index=True, width="stretch",
        column_config={
            "rank": st.column_config.NumberColumn("Rank", format="%d"),
            "employee_name": "Name", "department": "Department", "job_title": "Job title",
            "manager_name": "Manager",
            "performance_score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.1f"),
            "band": "Rating band", "status": "Status",
        },
    )

    st.subheader("Department comparison")
    dept = (df.groupby("department", dropna=False)["performance_score"]
            .agg(employees="count", average="mean", highest="max", lowest="min")
            .round(1).reset_index().sort_values("average", ascending=False))
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.bar(dept, x="department", y="average", text="average",
                     error_y=dept["highest"] - dept["average"],
                     error_y_minus=dept["average"] - dept["lowest"],
                     title="Average score by department (bars show lowest–highest)",
                     labels={"department": "Department", "average": "Average score"})
        fig.update_yaxes(range=[0, 105])
        show_chart(fig)
    with c2:
        st.dataframe(
            dept, hide_index=True, width="stretch",
            column_config={
                "department": "Department",
                "employees": st.column_config.NumberColumn("Employees", format="%d"),
                "average": st.column_config.NumberColumn("Average", format="%.1f"),
                "highest": st.column_config.NumberColumn("Highest", format="%.1f"),
                "lowest": st.column_config.NumberColumn("Lowest", format="%.1f"),
            },
        )

    st.subheader("Score distribution")
    c3, c4 = st.columns(2)
    with c3:
        fig = px.histogram(df, x="performance_score", color="department",
                           title="Performance score distribution",
                           labels={"performance_score": "Score", "department": "Department"})
        fig.update_traces(xbins=dict(start=0, end=100, size=10))
        fig.update_xaxes(range=[0, 100], dtick=10)
        fig.update_yaxes(title="Employees", dtick=1)
        show_chart(fig)
    with c4:
        bands = ranking["band"].value_counts().reindex(
            [label for _, label in SCORE_BANDS], fill_value=0).reset_index()
        bands.columns = ["band", "employees"]
        fig = px.bar(bands, x="band", y="employees", text="employees",
                     title="Employees by rating band",
                     labels={"band": "Rating band", "employees": "Employees"})
        fig.update_yaxes(dtick=1)
        show_chart(fig)
    st.caption("Rating bands: Excellent ≥ 90 · Good 80–89 · Satisfactory 70–79 · Needs improvement < 70.")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
{
    "dashboard": page_dashboard,
    "employees": page_employees,
    "add_employee": page_add_employee,
    "tasks": page_tasks,
    "performance": page_performance,
}[page]()
