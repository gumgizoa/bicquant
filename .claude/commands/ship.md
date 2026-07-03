---
description: Commit working changes, push the current branch, then PR into main and merge
argument-hint: [commit message]
allowed-tools: Bash(git:*), Bash(gh:*)
---

Ship the current working changes all the way to `main`.

Context:
- Current branch: !`git branch --show-current`
- Status: !`git status --short`
- Diff stat vs HEAD: !`git diff --stat HEAD`

Steps:

1. Review the diff above. If there are no changes to ship, stop and report that.
2. Stage only the files relevant to this change (use explicit `git add <path>` — do
   not blindly `git add -A`, since unrelated staged/untracked files may be present).
   Commit with "$ARGUMENTS" as the message if provided; otherwise write a concise
   message following the repo's `[type] summary` convention. End the commit body with:

   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

3. Push the current branch to origin. The pre-push hook runs pytest — if it fails on
   code unrelated to this change (stale tests, drift), investigate and fix it, then
   retry. Do NOT bypass the hook with `--no-verify`.
4. Create a PR from the current branch into `main` with `gh pr create` (reuse an open
   one if it already exists), then merge it with `gh pr merge --merge`. End the PR body
   with the `🤖 Generated with [Claude Code](https://claude.com/claude-code)` trailer.
5. Verify the merge landed on `main` and report the PR number and merge commit.
