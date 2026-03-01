# Frontend Changes: Dark / Light Theme Toggle

## Summary

Added a theme toggle button that lets users switch between the existing dark mode and a new light mode. The chosen theme is persisted in `localStorage` and applied immediately on page load to prevent a flash of unstyled content (FOUC).

---

## Files Changed

### `frontend/style.css`

1. **Added `[data-theme="light"]` CSS variable block** (after `:root`)
   Overrides all colour variables for light mode:
   - `--background: #f8fafc` — near-white page background
   - `--surface: #ffffff` — white card / sidebar surface
   - `--surface-hover: #f1f5f9` — light hover state
   - `--text-primary: #0f172a` — dark slate text (high contrast)
   - `--text-secondary: #64748b` — medium grey secondary text
   - `--border-color: #e2e8f0` — subtle light border
   - `--assistant-message: #f1f5f9` — light assistant bubble
   - `--shadow: 0 4px 6px -1px rgba(0,0,0,0.08)` — softer shadow
   - `--welcome-bg: #eff6ff`, `--welcome-border: #3b82f6` — light welcome card
   - `--focus-ring: rgba(37,99,235,0.15)` — slightly more subtle focus ring

2. **Added `.theme-transitioning` animation rule**
   A `body.theme-transitioning, body.theme-transitioning *` rule that temporarily forces `background-color`, `color`, `border-color`, and `box-shadow` to transition over 0.3 s (using `!important` so it overrides per-component transitions). The class is added/removed by JavaScript around the toggle.

3. **Added `.theme-toggle` button styles**
   - `position: fixed; top: 1rem; right: 1rem; z-index: 100` — always visible top-right floating button
   - Circular (40 × 40 px, `border-radius: 50%`) with a 1 px border, surface background, and drop-shadow
   - Hover: scales to 1.1×, adopts `--primary-color` colour and border
   - Focus: blue `box-shadow` focus ring for keyboard navigation
   - Smooth `transition` on background, colour, border, and transform

4. **Icon visibility rules**
   - Default (dark): sun icon visible, moon icon hidden
   - `[data-theme="light"]`: moon icon visible, sun icon hidden

5. **Fixed hardcoded `.source-chip` background**
   `background: #1e293b` → `background: var(--surface)` so source chips take the correct colour in both themes.

6. **Added `[data-theme="light"] a.source-chip:hover` colour fix**
   Overrides the dark-optimised `#93c5fd` hover text to `var(--primary-color)` (dark blue) for proper contrast on a light background.

7. **Added light-theme contrast fixes for status messages**
   The hardcoded pastel colours used by `.error-message` (`#f87171`) and `.success-message` (`#4ade80`) are low-contrast on a light background. Light-mode overrides set them to darker, WCAG-compliant equivalents:
   - Error: `#dc2626` (dark red)
   - Success: `#16a34a` (dark green)

---

### `frontend/index.html`

1. **Inline FOUC-prevention script in `<head>`**
   A synchronous `<script>` block reads `localStorage.getItem('theme')` before the page renders. If the value is `'light'`, it sets `data-theme="light"` on `<html>` immediately, so the correct variables are applied before any paint.

2. **Theme toggle `<button>` element**
   Added just before the `<script>` tags at the bottom of `<body>`:
   - `id="themeToggle"`, `class="theme-toggle"`
   - `aria-label="Toggle light/dark theme"` and `title` for accessibility
   - Contains two inline SVG icons: a sun (Feather Icons style, 8-ray) and a crescent moon
   - Both SVGs carry `aria-hidden="true"` (the button label describes the action)

3. **Cache-busted asset URLs** — `style.css?v=12` and `script.js?v=12`

---

### `frontend/script.js`

1. **Added `themeToggle` DOM reference** to the global element cache.

2. **Wired up the click handler** in `DOMContentLoaded`:
   ```js
   themeToggle.addEventListener('click', toggleTheme);
   ```

3. **Added `toggleTheme()` function**:
   - Reads `data-theme` from `document.documentElement` (`<html>`)
   - Adds `theme-transitioning` class to `body` for the smooth colour animation
   - Toggles `data-theme="light"` attribute on `<html>` (set or remove)
   - Persists the new theme (`'light'` or `'dark'`) to `localStorage`
   - Removes `theme-transitioning` after 350 ms (slightly longer than the 0.3 s CSS transition)

---

## Design Decisions

| Decision | Rationale |
|---|---|
| Attribute on `<html>` element | Allows the FOUC-prevention script in `<head>` to set it before `<body>` exists |
| Dark mode as default (no system-preference check) | The app is designed dark-first; users opt in to light |
| Sun icon = "switch to light", Moon = "switch to dark" | Common convention: icon shows the mode you'll *switch to* |
| Temporary `theme-transitioning` class rather than permanent transitions | Avoids interfering with per-component `transition: all` rules during normal interaction |
| `var(--surface)` for `.source-chip` background | Eliminates the only hardcoded colour that broke theming |

---

# Code Quality Changes

## Overview

Added Black for automatic Python code formatting and a development script for running quality checks.

## Changes Made

### 1. Added Black as a dev dependency (`pyproject.toml`)

- Added `black>=26.1.0` to the `[dependency-groups] dev` section.
- Added `[tool.black]` configuration:
  - `line-length = 88` (Black default)
  - `target-version = ["py313"]`

### 2. Formatted all Python files with Black

Black reformatted 11 files in `backend/`:

- `backend/ai_generator.py`
- `backend/app.py`
- `backend/models.py`
- `backend/rag_system.py`
- `backend/search_tools.py`
- `backend/session_manager.py`
- `backend/vector_store.py`
- `backend/tests/conftest.py`
- `backend/tests/test_ai_generator.py`
- `backend/tests/test_course_search_tool.py`
- `backend/tests/test_rag_system_query.py`

### 3. Created quality check script (`scripts/quality.sh`)

A shell script to run Black in check mode (no changes applied, exits non-zero if formatting differs). Run with:

```bash
./scripts/quality.sh
```

To auto-format instead:

```bash
uv run black backend/
```
