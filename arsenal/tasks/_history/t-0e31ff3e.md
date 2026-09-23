---
id: t-0e31ff3e
title: "Flujo de PR obligatorio: branch protection, CI y revisi\u00f3n de bot"
priority: 10
tags: [INFRA]
status: merged
---

Se detectó que casi todo el historial de este repo se subió directo a \`main\` sin PR
(el flujo de PR de arsenal solo se activa para tareas reclamadas de la cola;
el trabajo conversacional ad hoc lo esquivaba, y GitHub no tenía branch protection).

Ya aplicado en esta sesión, este gate solo lo deja constancia mecánica:

- Branch protection en \`main\`: PR obligatorio, CI (\`test\`) y el check de CodeRabbit
  como checks requeridos, sin force-push ni borrado, \`enforce_admins\` activo.
- \`arsenal/config.toml\`: \`merge-policy = "after-ci-and-review"\`,
  \`host-gate = "make lint test"\`.
- CLAUDE.md documenta, de forma genérica (no solo para CodeRabbit), que hay que
  descubrir qué bots de revisión tiene el repo y sus reglas de disparo antes de dar
  un PR por listo.


## Acceptance gate

```bash
set -euo pipefail

protection=$(gh api repos/nuncaeslupus/comparador-luz-gas/branches/main/protection)
echo "$protection" | jq -e '.required_status_checks.contexts | index("test")' >/dev/null
echo "$protection" | jq -e '.required_status_checks.contexts | index("CodeRabbit")' >/dev/null
echo "$protection" | jq -e '.enforce_admins.enabled == true' >/dev/null
echo "$protection" | jq -e '.allow_force_pushes.enabled == false' >/dev/null
echo "$protection" | jq -e '.allow_deletions.enabled == false' >/dev/null
echo "$protection" | jq -e '.required_pull_request_reviews != null' >/dev/null

grep -q '^merge-policy = "after-ci-and-review"$' arsenal/config.toml
grep -q '^host-gate = "make lint test"$' arsenal/config.toml

grep -q '## Flujo de trabajo de este repo' CLAUDE.md
```
