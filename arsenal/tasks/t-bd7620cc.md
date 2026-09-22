---
id: t-bd7620cc
title: "Scaffold Python (uv/ruff/mypy/Makefile) y repo en GitHub"
priority: 9
tags: [INFRA]
---


## Acceptance gate

```bash
make lint && make test && gh repo view --json name -q .name
```
