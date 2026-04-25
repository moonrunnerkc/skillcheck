---
name: code-reviewer
description: Reviews code changes and reports style, correctness, and security issues with line references.
version: "1.0.0"
allowed-tools:
  - read_file
  - list_directory
---

## When to use

Use this skill whenever the user asks to review, check, or audit code. Trigger
phrases include "review this", "check my code", "look for issues", and
"security audit".

## What it produces

A structured report containing:
- Style violations with line numbers
- Correctness issues with explanations
- Security findings with severity ratings

## Limitations

This skill does not modify files. It reports only. If the user wants automated
fixes, use the code-fixer skill instead.

## Input requirements

The user must provide either a file path or inline code. If neither is
present, ask before proceeding.
