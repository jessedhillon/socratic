---
name: commit
description: Format a git commit message following conventional commit standards
user-invocable: true
---

Format commit messages using this project's conventional commit standard.

## Format

```
type(area[,...])[!]: [{tag}] message
```

## Valid Types

| Type     | Use for                                              |
| -------- | ---------------------------------------------------- |
| `feat`   | New features or capabilities                         |
| `fix`    | Bug fixes                                            |
| `revise` | Amending a previous commit (area is the commit hash) |
| `chore`  | Maintenance, dependencies, tooling, refactoring      |
| `docs`   | Documentation only (area optional)                   |
| `wip`    | Work in progress (area optional)                     |

## Common Areas

Based on project structure: `api`, `cli`, `config`, `core`, `dev`, `frontend`, `lib`, `llm`, `model`, `migrations`, `storage`, `tests`, `typings`, `web`

App-specific: `learner`, `instructor`, `socratic`

Combine areas with commas: `feat(api,storage): add user endpoint`

## Rules

- Message must be at least 8 characters
- For breaking changes, add exclamation before colon: `feat(api)!: remove deprecated endpoint`
- Optional `{tag}` for context: `fix(llm): {tests-failing} update prompt`
- Use lowercase for type, areas, and message start
- Focus on "why" not "what" in the message
- For refactoring, use `chore` not `revise`

## Examples

```
feat(llm): implement AI-driven completion detection
fix(api): handle null timestamps in migration
revise(abc123): forgot to add migration file
chore(storage): refactor query builder pattern
chore(dev): update fastapi to 0.115
docs: add API authentication guide
feat(api,frontend): add synchronized playback demo
```

When invoked, analyze the staged changes and suggest an appropriate commit message.
