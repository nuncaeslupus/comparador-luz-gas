<!-- claude-arsenal: auto-managed -->
## Automatic session protocol

Every session, without waiting to be asked:

1. Read `arsenal/session/handover.md` for the previous session's context.
2. List the repository's issues labelled `arsenal:task` — **open and closed** — and
   save the JSON. Use whatever GitHub access this surface has; run
   `claude-arsenal/bin/github_channel.sh --detect` to find out which. Request
   `number`, `title`, `state`, `labels`, `assignees` and **not `body`** — the bodies
   are the bulk of that fetch and nothing downstream reads them.
3. Run `python3 claude-arsenal/scripts/query_status.py --issues <that file>` for the
   board, and report anything it flags.
4. Pick up work: `python3 claude-arsenal/scripts/task_select.py --issues <that file>`
   returns the next unblocked task, then
   `bash claude-arsenal/bin/claim_task.sh <id>` takes it (see `@claude-arsenal/AGENTS.md`).
   - **Nothing returned + workspace plans exist** → seed tasks from each plan.
   - **Nothing at all** → ask what to work on.
5. Open each task's PR with `Closes #<issue>` so merging it closes the task by itself.
6. After any session with tasks: update `arsenal/session/handover.md`.

@claude-arsenal/AGENTS.md
<!-- /claude-arsenal: auto-managed -->

## Flujo de trabajo de este repo

**Ningún cambio se sube directo a `main`, ni siquiera uno trivial (docs, handover).**
Siempre rama + PR. `main` tiene branch protection: exige PR, que pase el CI (`test`) y
que reporte cualquier check de revisión que el repo tenga configurado; sin eso, ni
siquiera un admin puede mergear (`enforce_admins`).

Antes de mergear, comprueba qué bots de revisión están activos en el repo (no asumas
cuáles — cada repo puede tener otros, o ninguno) y aprovecha sus reglas:

- Si un bot no ha comentado ni dejado check en el PR, puede que no se dispare solo.
  P. ej. **CodeRabbit no revisa automáticamente repos con pocas estrellas** en el plan
  gratuito; pídeselo a mano comentando `@coderabbitai review` (o `full review`) en el PR.
  Otros bots tendrán sus propios disparadores — descúbrelos antes de asumir que "no hay
  bot" cuando puede que solo haga falta pedírselo.
- No des un PR por listo hasta que el/los check(s) de revisión configurados hayan
  reportado, no solo el CI.
