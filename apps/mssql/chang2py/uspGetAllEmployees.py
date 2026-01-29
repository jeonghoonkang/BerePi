"""Python translation of HumanResources.uspGetAllEmployees."""

from __future__ import annotations

from typing import Iterable, Mapping

import pyodbc


def _connect(connection_string: str) -> pyodbc.Connection:
    return pyodbc.connect(connection_string)


def fetch_all_employees(connection_string: str) -> list[Mapping[str, str]]:
    """Return employee rows matching the stored procedure result set."""
    query = """
        SELECT LastName, FirstName, JobTitle, Department
        FROM HumanResources.vEmployeeDepartment;
    """
    with _connect(connection_string) as connection:
        cursor = connection.cursor()
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_all_vemployee_department(connection_string: str) -> list[Mapping[str, str]]:
    """Return all columns from HumanResources.vEmployeeDepartment."""
    query = "SELECT * FROM HumanResources.vEmployeeDepartment;"
    with _connect(connection_string) as connection:
        cursor = connection.cursor()
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def main() -> None:
    connection_string = (
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=localhost;"
        "Database=AdventureWorks;"
        "Trusted_Connection=yes;"
    )

    employees = fetch_all_employees(connection_string)
    print("Stored procedure equivalent results:")
    for row in employees:
        print(row)

    all_rows = fetch_all_vemployee_department(connection_string)
    print("\nFull view results:")
    for row in all_rows:
        print(row)


if __name__ == "__main__":
    main()
