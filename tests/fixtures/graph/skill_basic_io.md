---
name: basic-io-skill
version: 1.0.0
description: Runs a database query and writes a report.
author: test
tags: [db, reporting]
---

## Inputs

- `db_client` - database access tool
- DB_URL - database connection URL
- schema.sql - SQL schema file path

## Generate report

Connects via `db_client` and writes results to `report.json`.

## Outputs

- report.json - generated output file
- execution summary - brief summary of the run
- record_count - number of processed records
