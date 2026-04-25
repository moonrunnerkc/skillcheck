---
name: sql-formatter
description: Formats SQL queries for readability and validates syntax against common dialects.
allowed-tools:
  - read_file
---

## Usage

Provide a SQL string or a file path containing SQL. The skill returns the
reformatted query.

## Example

Input:

```sql
SELECT id,name FROM users WHERE active=1 ORDER BY name
```

Output:

```sql
SELECT
    id,
    name
FROM users
WHERE active = 1
ORDER BY name
```

## Supported dialects

PostgreSQL, MySQL, SQLite. MSSQL is not supported.
