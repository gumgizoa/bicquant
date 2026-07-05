---
description: Verify the current feature branch and merge it into develop (no push)
argument-hint: [commit message]
allowed-tools: Bash(git:*), Bash(uv:*)
---

Integrate the current `feature/*` branch into `develop`.

This is the develop-integration counterpart to `/ship` (which releases the
current branch to `main` via PR). `/land` stays local: it verifies, merges into
`develop`, deletes the feature branch, and does **not** push.

Context:
- Current branch: !`git branch --show-current`
- Status: !`git status --short`
- Commits ahead of develop: !`git log --oneline develop..HEAD`
- Diff stat vs HEAD: !`git diff --stat HEAD`

Steps:

1. Confirm the current branch is a feature branch. If it is `develop` or `main`,
   stop and report — this command only integrates feature branches (use `/ship`
   for main).
2. If there are uncommitted changes, stage only the files relevant to this change
   (explicit `git add <path>` — never blindly `git add -A`, since unrelated
   staged/untracked files may be present). Commit with "$ARGUMENTS" as the message
   if provided; otherwise write a concise message following the repo's
   `[type] summary` convention. End the commit body with:

   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

   If the working tree is clean and there is nothing ahead of `develop`, stop and
   report that there is nothing to land.
3. Verify before merging: run `uv run pytest -m "not slow"`. If it fails on code
   related to this change, fix it and retry; if it fails on unrelated drift,
   investigate before proceeding. Do not skip this gate.
4. Remember the feature branch name, then `git checkout develop` and merge it with
   `git merge --ff-only <feature-branch>`. If a fast-forward is not possible
   (develop has diverged), stop and report the situation rather than creating a
   merge commit or forcing — let the user decide.
5. Delete the merged feature branch with `git branch -d <feature-branch>`.
6. Do **not** push. Report the result: `develop` now points at which commit, and
   how many commits it is ahead of `origin/develop`. Remind the user they can
   push or `/ship` to main separately when ready.
