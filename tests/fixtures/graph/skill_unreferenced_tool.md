---
name: unreferenced-tool-skill
version: 1.0.0
description: Declares a tool in allowed-tools but never references it in the body.
author: test
tags: [testing]
allowed-tools: [Bash]
---

## Generate report

Writes a summary without invoking any tool.
The Bash tool is declared in allowed-tools but never backtick-referenced here.
