---
name: create-new-project
description: Use when asked to scaffold a new frontend project and immediately work inside it. Creates Next.js apps with create-next-app (or in-place in Webmaker workspaces), then continues work in the project directory.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [nextjs, scaffolding, project-bootstrap, create-next-app, software-development]
    related_skills: [plan, test-driven-development, requesting-code-review]
---

# Create New Next.js Project

## Overview

Use this skill when the user wants a brand-new Next.js app scaffolded and then worked on right away. The goal is not just to generate files; it is to land in the new project directory and continue from there without making the user repeat themselves like a broken onboarding form.

## When to Use

- User asks to create a new Next.js project
- User provides a project name and expects you to scaffold it
- User wants you to continue working inside the newly created app

Do not use this skill for:
- Editing an existing Next.js app unless the task is specifically bootstrap-focused
- Non-Next.js frontend projects
- Projects where the framework or package manager is different

## Workflow

1. Confirm the project name and the destination directory if either is missing.
2. Scaffold the app with the exact command the user requested, e.g.:

   ```bash
   npx create-next-app@latest my-app --yes
   ```

3. Change into the generated project directory:

   ```bash
   cd my-app
   ```

4. Verify the scaffold succeeded by checking for the core files:
   - `package.json`
   - `app/` or `pages/`
   - `next.config.*` if generated

5. Continue all follow-up work inside that project directory.

## Practical Notes

- If the user already supplied a project name, use it exactly unless they ask otherwise.
- If the user did not specify a destination directory, ask before writing files outside the current workspace.
- Prefer the default app-router scaffold unless the user requests pages-router or extra flags.
- After scaffolding, run a quick verification such as:

  ```bash
  npm run build
  ```

  or, if the user only wants a light check:

  ```bash
  npm run dev
  ```

## Common Pitfalls

1. **Scaffolding into the wrong folder.** Always confirm the destination if it is not obvious.
2. **Forgetting to `cd` into the new project.** The whole point is to work inside it, not admire it from afar.
3. **Treating scaffold output as finished work.** Verify the generated project before proceeding.
4. **Using the wrong project name.** Mirror the user’s name exactly unless they tell you to transform it.

## Verification Checklist

- [ ] Project created with `npx create-next-app@latest <name> --yes`
- [ ] Current work is inside the new project directory
- [ ] Core Next.js files exist
- [ ] Project runs or builds successfully if requested

## Webmaker workspace

When running inside Webmaker, the session workspace root **is** the project directory.
Do not create a nested subfolder and do not write to the Webmaker host app.

1. Scaffold in the current directory:

   ```bash
   npx create-next-app@latest . --yes
   ```

2. Verify `package.json`, `app/` (or `pages/`), and `next.config.*` exist.
3. Continue all feature work in the workspace root.
4. Run `npm run build` or `npm run dev` to verify when appropriate.

Webmaker syncs the scaffolded files to StackBlitz for preview after generation.
