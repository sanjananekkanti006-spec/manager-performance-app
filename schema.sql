-- =====================================================================
-- Manager Performance Analytics Dashboard - database setup
-- Safe to run more than once: tables are only created if missing and
-- sample rows are only inserted if they are not already there.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS manager_analytics;
USE manager_analytics;

CREATE TABLE IF NOT EXISTS employees (
    employee_id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    job_title VARCHAR(100),
    manager_name VARCHAR(100),
    performance_score DECIMAL(5,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id INT AUTO_INCREMENT PRIMARY KEY,
    task_name VARCHAR(150) NOT NULL,
    employee_id INT,
    project_name VARCHAR(100),
    task_status VARCHAR(30) DEFAULT 'Pending',
    due_date DATE,
    FOREIGN KEY (employee_id)
        REFERENCES employees(employee_id)
);

-- ---------------------------------------------------------------------
-- Sample employees (each row is inserted only if that employee is missing)
-- ---------------------------------------------------------------------
INSERT INTO employees (employee_name, department, job_title, manager_name, performance_score, status)
SELECT 'Ananya Nair', 'Marketing', 'Marketing Executive', 'Rahul Menon', 88, 'Active'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM employees WHERE employee_name = 'Ananya Nair');

INSERT INTO employees (employee_name, department, job_title, manager_name, performance_score, status)
SELECT 'Arjun Das', 'IT', 'Software Developer', 'Priya Sharma', 92, 'Active'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM employees WHERE employee_name = 'Arjun Das');

INSERT INTO employees (employee_name, department, job_title, manager_name, performance_score, status)
SELECT 'Meera Joseph', 'Finance', 'Financial Analyst', 'Rahul Menon', 78, 'Active'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM employees WHERE employee_name = 'Meera Joseph');

INSERT INTO employees (employee_name, department, job_title, manager_name, performance_score, status)
SELECT 'Vivek Kumar', 'HR', 'HR Executive', 'Priya Sharma', 85, 'Active'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM employees WHERE employee_name = 'Vivek Kumar');

-- ---------------------------------------------------------------------
-- Sample tasks. The employee is looked up by name, so on a fresh database
-- this gives exactly the original IDs (Ananya = 1, Arjun = 2, ...), and
-- it still links correctly if the IDs ever differ.
-- ---------------------------------------------------------------------
INSERT INTO tasks (task_name, employee_id, project_name, task_status, due_date)
SELECT 'Prepare campaign report', e.employee_id, 'Digital Campaign', 'Completed', '2026-10-20'
FROM employees e
WHERE e.employee_name = 'Ananya Nair'
  AND NOT EXISTS (SELECT 1 FROM tasks WHERE task_name = 'Prepare campaign report')
LIMIT 1;

INSERT INTO tasks (task_name, employee_id, project_name, task_status, due_date)
SELECT 'Develop reporting module', e.employee_id, 'Analytics Portal', 'In Progress', '2026-10-25'
FROM employees e
WHERE e.employee_name = 'Arjun Das'
  AND NOT EXISTS (SELECT 1 FROM tasks WHERE task_name = 'Develop reporting module')
LIMIT 1;

INSERT INTO tasks (task_name, employee_id, project_name, task_status, due_date)
SELECT 'Review quarterly budget', e.employee_id, 'Budget Planning', 'Pending', '2026-10-22'
FROM employees e
WHERE e.employee_name = 'Meera Joseph'
  AND NOT EXISTS (SELECT 1 FROM tasks WHERE task_name = 'Review quarterly budget')
LIMIT 1;

INSERT INTO tasks (task_name, employee_id, project_name, task_status, due_date)
SELECT 'Complete onboarding plan', e.employee_id, 'Hiring Project', 'Completed', '2026-10-18'
FROM employees e
WHERE e.employee_name = 'Vivek Kumar'
  AND NOT EXISTS (SELECT 1 FROM tasks WHERE task_name = 'Complete onboarding plan')
LIMIT 1;

-- ---------------------------------------------------------------------
-- Verify
-- ---------------------------------------------------------------------
SELECT * FROM employees;
SELECT * FROM tasks;
