"""
database.py
-----------
All MySQL access for the Manager Performance Analytics Dashboard.

Rules followed in this file:
* Credentials come from .streamlit/secrets.toml (never hardcoded).
* Every value supplied by a user is passed as a query parameter (%s),
  never pasted into the SQL string, which prevents SQL injection.
* Every connection and cursor is closed, even when an error happens.
* Write operations run in a transaction: commit on success, roll back on error.
* Error messages shown to the user never contain the password.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import mysql.connector
from mysql.connector import errorcode
import pandas as pd
import streamlit as st

# Allowed values used by the app (the database itself stores plain text).
TASK_STATUSES = ["Pending", "In Progress", "Completed"]
EMPLOYEE_STATUSES = ["Active", "Inactive", "On Leave"]


class DatabaseError(Exception):
    """A friendly, password-free error that the UI can show directly."""


# ---------------------------------------------------------------------------
# Connection handling
# ---------------------------------------------------------------------------
def _get_config() -> dict:
    """Read the [mysql] section of .streamlit/secrets.toml."""
    try:
        cfg = st.secrets["mysql"]
    except (KeyError, FileNotFoundError) as exc:
        raise DatabaseError(
            "MySQL settings were not found. Create .streamlit/secrets.toml "
            "with a [mysql] section."
        ) from exc
    except Exception as exc:  # Streamlit raises its own error if no secrets file exists
        raise DatabaseError(
            "Could not read .streamlit/secrets.toml. Check that the file exists "
            "inside the project folder and is valid TOML."
        ) from exc

    missing = [k for k in ("host", "user", "password", "database") if k not in cfg]
    if missing:
        raise DatabaseError(
            "secrets.toml is missing these [mysql] keys: " + ", ".join(missing)
        )

    return {
        "host": cfg["host"],
        "port": int(cfg.get("port", 3306)),
        "user": cfg["user"],
        "password": cfg["password"],
        "database": cfg["database"],
        "connection_timeout": 5,
    }


def _friendly_error(err: mysql.connector.Error) -> str:
    """Turn a MySQL error into a helpful message without exposing secrets."""
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        return "MySQL access denied. Check the user and password in .streamlit/secrets.toml."
    if err.errno == errorcode.ER_BAD_DB_ERROR:
        return ("Database not found. Run schema.sql in MySQL Workbench to create "
                "manager_analytics, and check the database name in secrets.toml.")
    if err.errno == errorcode.ER_NO_SUCH_TABLE:
        return "A required table is missing. Run schema.sql in MySQL Workbench to create it."
    if err.errno in (2002, 2003, 2005):  # cannot connect / unknown host
        return "Cannot reach the MySQL server. Make sure MySQL is running and the host/port are correct."
    if err.errno == errorcode.ER_ROW_IS_REFERENCED_2:
        return "This record is still referenced by another table, so it cannot be removed."
    if err.errno == errorcode.ER_NO_REFERENCED_ROW_2:
        return "The selected employee does not exist any more. Refresh the page and try again."
    if err.errno == errorcode.ER_DATA_TOO_LONG:
        return "One of the values is too long for its database column."
    return f"Database error {err.errno}. Please check your input and try again."


@contextmanager
def get_connection():
    """Open a connection and always close it afterwards."""
    conn = None
    try:
        conn = mysql.connector.connect(**_get_config())
        yield conn
    except mysql.connector.Error as err:
        raise DatabaseError(_friendly_error(err)) from None
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


def _clean_value(value):
    """Convert MySQL types (Decimal) into plain Python types for pandas."""
    if isinstance(value, Decimal):
        return float(value)
    return value


def fetch_dataframe(query: str, params: tuple | None = None) -> pd.DataFrame:
    """Run a SELECT query and return the result as a pandas DataFrame."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            columns = list(cursor.column_names)
        except mysql.connector.Error as err:
            raise DatabaseError(_friendly_error(err)) from None
        finally:
            cursor.close()
    cleaned = [{k: _clean_value(v) for k, v in row.items()} for row in rows]
    return pd.DataFrame(cleaned, columns=columns)


def execute_write(query: str, params: tuple | None = None) -> int:
    """
    Run an INSERT, UPDATE or DELETE inside a transaction.
    Returns the new row ID for inserts, otherwise the number of affected rows.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
        except mysql.connector.Error as err:
            conn.rollback()
            raise DatabaseError(_friendly_error(err)) from None
        finally:
            cursor.close()


def test_connection() -> tuple[bool, str]:
    """Check that MySQL is reachable and both tables exist."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM employees")
                emp_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM tasks")
                task_count = cursor.fetchone()[0]
            except mysql.connector.Error as err:
                return False, _friendly_error(err)
            finally:
                cursor.close()
        return True, f"Connected · {emp_count} employees, {task_count} tasks"
    except DatabaseError as err:
        return False, str(err)


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------
def get_employees() -> pd.DataFrame:
    return fetch_dataframe(
        """
        SELECT employee_id, employee_name, department, job_title,
               manager_name, performance_score, status
        FROM employees
        ORDER BY employee_id
        """
    )


def employee_exists(name: str, department: str, job_title: str) -> bool:
    """True if an employee with the same name, department and job title exists."""
    df = fetch_dataframe(
        """
        SELECT employee_id FROM employees
        WHERE LOWER(employee_name) = LOWER(%s)
          AND LOWER(COALESCE(department, '')) = LOWER(%s)
          AND LOWER(COALESCE(job_title, '')) = LOWER(%s)
        LIMIT 1
        """,
        (name, department, job_title),
    )
    return not df.empty


def add_employee(name: str, department: str, job_title: str,
                 manager_name: str, performance_score: float, status: str) -> int:
    return execute_write(
        """
        INSERT INTO employees
            (employee_name, department, job_title, manager_name, performance_score, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (name, department, job_title, manager_name, performance_score, status),
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
def get_tasks_with_employees() -> pd.DataFrame:
    """Tasks joined with the employee each task is assigned to."""
    return fetch_dataframe(
        """
        SELECT t.task_id, t.task_name, t.employee_id,
               e.employee_name, e.department,
               t.project_name, t.task_status, t.due_date
        FROM tasks t
        LEFT JOIN employees e ON e.employee_id = t.employee_id
        ORDER BY t.due_date IS NULL, t.due_date, t.task_id
        """
    )


def task_exists(task_name: str, employee_id: int | None, project_name: str) -> bool:
    df = fetch_dataframe(
        """
        SELECT task_id FROM tasks
        WHERE LOWER(task_name) = LOWER(%s)
          AND employee_id <=> %s
          AND LOWER(COALESCE(project_name, '')) = LOWER(%s)
        LIMIT 1
        """,
        (task_name, employee_id, project_name),
    )
    return not df.empty


def add_task(task_name: str, employee_id: int | None, project_name: str,
             task_status: str, due_date: date | None) -> int:
    return execute_write(
        """
        INSERT INTO tasks (task_name, employee_id, project_name, task_status, due_date)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (task_name, employee_id, project_name, task_status, due_date),
    )


def update_task_status(task_id: int, task_status: str) -> int:
    return execute_write(
        "UPDATE tasks SET task_status = %s WHERE task_id = %s",
        (task_status, task_id),
    )


def update_task(task_id: int, task_name: str, employee_id: int | None,
                project_name: str, task_status: str, due_date: date | None) -> int:
    return execute_write(
        """
        UPDATE tasks
        SET task_name = %s, employee_id = %s, project_name = %s,
            task_status = %s, due_date = %s
        WHERE task_id = %s
        """,
        (task_name, employee_id, project_name, task_status, due_date, task_id),
    )


def delete_task(task_id: int) -> int:
    return execute_write("DELETE FROM tasks WHERE task_id = %s", (task_id,))
