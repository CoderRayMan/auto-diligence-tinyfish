---
description: "Run a full dev-test-fix-test-enhance cycle: implement a task, open the browser, automatically fix any issues found, re-test, and enhance. Use when you want to build a feature or fix and keep iterating until the browser confirms success."
name: "Dev-Test-Fix-Test-Enhance Cycle"
argument-hint: "Describe the feature or fix to implement and test in the browser"
agent: "agent"
tools: [vscode, execute, read, agent, edit, search, web, azure-mcp/search, browser, ms-python.python/getPythonEnvironmentInfo, ms-python.python/getPythonExecutableCommand, ms-python.python/installPythonPackage, ms-python.python/configurePythonEnvironment, postman.postman-for-vscode/openRequest, postman.postman-for-vscode/getCurrentWorkspace, postman.postman-for-vscode/switchWorkspace, postman.postman-for-vscode/sendRequest, postman.postman-for-vscode/runCollection, postman.postman-for-vscode/getSelectedEnvironment, todo]
---

## User Steering Points

**REQUIRED FIRST STEP**: Before doing anything else, read [.github/notes.md](../../.github/notes.md).
This file contains **user-set steering points** — direct instructions and preferences the user has chosen to carry forward across every session (similar to knowledge items in Devin). Treat each point as a standing instruction from the user, not as documentation.
If the user shares a new important choice or preference during this session, append it to that file before finishing.

---

You are running a **dev → test → fix → test → enhance** cycle. Keep looping until the browser confirms the task is working correctly, then look for one meaningful enhancement opportunity. Your job is to:
1. Read project notes (above — mandatory)
2. Implement the requested task in the codebase
3. Start (or restart) the development server
4. Open the browser and visually test the result
5. **Auto-fix any issues found** — then re-test (repeat until clean)
6. Enhance once the task is confirmed working
7. Record new knowledge in notes

---

## Task

{{input}}

---

## Cycle Steps

### Phase 0 — Load Steering Points

Read [.github/notes.md](../../.github/notes.md) now. Every bullet is a user instruction — apply them all. Do not skip this step.

### Phase 1 — Implement

- Read all relevant files before editing them.
- Make only the changes required by the task. Do not refactor unrelated code.
- After editing, run `get_errors` on changed files to catch compile-time issues.

### Phase 2 — Start / Restart Dev Server

- Check whether a dev server is already running (look for existing terminal output).
- If not running, start it:
  - **Frontend (Vite/React):** run `cd ui ; npm run dev` in a background terminal.
  - **Backend (FastAPI):** run `uvicorn src.api.main:app --reload` in a background terminal.
- Wait for the server to be ready before proceeding (watch for "ready" or the local URL in terminal output).

### Phase 3 — Browser Test

- **Frontend base URL: `http://localhost:5174/`** — always use this URL for the frontend.
- **Backend docs URL: `http://localhost:8000/docs`** — use this for backend-only tasks.
- Open the app at `http://localhost:5174/` to take a baseline screenshot.
- Navigate to the specific page or trigger the specific interaction that exercises the implemented task.
- Take a screenshot after each significant action.
- If the UI has a form or interactive flow, fill it and submit, then screenshot the result.
- **Classify the result as PASS or FAIL** before proceeding.

### Phase 4 — Auto-Fix (repeat until PASS)

If the test result is FAIL:
1. Diagnose the root cause from the screenshot, `read_page` output, terminal logs, and `get_errors`.
2. Apply the fix directly — do not ask for permission for clear bugs.
3. The server hot-reloads automatically; wait for it, then re-screenshot the affected view.
4. Re-classify as PASS or FAIL.
5. **Repeat this loop** (back to step 1) up to **5 iterations**.
   - After 5 failed iterations, stop, surface all findings, and ask the user for guidance.
6. Once PASS is confirmed, move to Phase 5.

> **Fix priority order**: compile errors → runtime console errors → visible UI breakage → wrong data/logic → styling/layout issues.

### Phase 5 — Enhance

Once the task is PASS:
- Identify **one** meaningful enhancement that directly improves the feature just built (e.g., better error state, loading indicator, empty-state copy, accessibility attribute, input validation).
- Implement it, re-screenshot to confirm it looks right.
- Do not add unrelated features or refactor untouched code.

### Phase 6 — Monitor & Report

Summarize the full cycle:
- **What was implemented** — the original task.
- **Fixes applied** — list each issue found and how it was resolved.
- **Enhancement added** — describe the one improvement made.
- **Final browser state** — attach the final confirming screenshot.
- **Remaining concerns** — anything deferred or worth watching.

### Phase 7 — Capture New Steering Points

If the user stated any new preference, choice, constraint, or important context during this session, append it as a bullet under "Captured During Sessions" in [.github/notes.md](../../.github/notes.md) before closing the cycle. Only capture things the user explicitly told you — do not infer or add your own assumptions.

---

## Rules

- Do **not** mark the cycle complete until you have a PASS screenshot **and** the enhancement is confirmed in the browser.
- Auto-fix without asking unless the fix is destructive (deleting data, changing API contracts, altering auth logic) — in those cases, describe the fix and ask first.
- If the server fails to start, surface the terminal output and stop — do not guess at fixes.
- If the task is backend-only and has no visible UI, test via the FastAPI docs UI at `http://localhost:8000/docs` and screenshot the relevant endpoint.
- Maximum 5 fix iterations per cycle. If still failing after 5, escalate to the user.
- Always honour every steering point in [.github/notes.md](../../.github/notes.md) — they are standing user instructions that persist across sessions.
