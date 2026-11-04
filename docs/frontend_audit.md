# Front-end usability audit and overhaul (4 November 2026)

**Method:** the interface was walked through on desktop (1366 px) and phone (390 px) as three users: a guest, a signed-in student and a faculty advisor. We checked onboarding, asking, reading answers, errors, privacy, voice and upload, keyboard use and screen-reader labels.

**Screenshots:** before and after images are in `docs/screenshots/`.

## 1. Findings (before)

| # | Area | Problem | Severity |
|---|---|---|---|
| F1 | Controls | Four technical dropdowns (Model, Advisor, Batch, Semester) sat permanently above the question box. On a phone they filled about 40% of the screen. | High |
| F2 | Sign-in | Login was a strip of placeholder-only inputs squeezed between the dropdowns and the input. There were no labels, the demo hint was cut off, and errors used a browser `alert()`. | High |
| F3 | Readability | Text sat on a campus photo behind frosted glass. The helper text at the bottom was low-contrast white on photo. | Medium |
| F4 | Answers | A decision such as "Decision: NOT ELIGIBLE" looked like any other sentence. Citations appeared as raw `[E1]`. Each answer carried 4 lines of chrome (a token line, an AI label, buttons, a trace link). | High |
| F5 | Trust | Sources and agent steps were shown as raw JSON fragments. The file names were technical (`cleaned/courses.csv row …`). | Medium |
| F6 | Waiting | The 3–15 s wait showed only "Finding guidance", with no sign of progress. | Medium |
| F7 | Errors | Quota or busy errors appeared as a red bubble with technical text ("check the server logs"). There was no retry, so the question had to be retyped. | High |
| F8 | Privacy | Refusals looked like normal answers, and the safeguard note was small blue text. | Medium |
| F9 | Mobile | The heading was clipped, the controls stacked, the placeholder was cut off ("Ask about courses,") and history was not reachable. | High |
| F10 | Discoverability | Voice, upload and charts were unexplained icons. Upload had no drag-and-drop. The suggestions were generic. | Medium |
| F11 | Robustness | Markdown rendering depended on two CDN scripts. When they were blocked, answers showed raw `**`. MathJax loaded for nothing. | Medium |
| F12 | Accessibility | No skip link; emoji-only buttons; mic errors used `alert()`; no focus ring on the hidden file input. | Medium |

**Bugs found during the audit:**

| # | Bug | Severity |
|---|---|---|
| B1 | **Security.** A signed-in student's page always sends their own ID, and in that case the server skipped checking IDs typed in the message. "Show me STU_004's fee dues" was neither refused nor logged. No data leaked, because the model only held the user's own record and the output filter removes other IDs. Fixed in `app.py`; new attack case S21 and two tests added. | High |
| B2 | **Privacy.** Signing out and in on the same browser kept the same anonymous session, so the next person saw the previous person's conversation list. The session ID now changes on every sign-in and sign-out. | High |
| B3 | "New conversation" cleared the advisor's selected student. | Low |
| B4 | The verifier's fallback answer ("Decision: NOT ELIGIBLE for DATA301") was not recognised as a decision. | Low |

## 2. What changed (after)

| Finding | Change |
|---|---|
| F1 | One question box. Batch, semester, model and answer mode moved into a **Settings** sheet (⚙, or click the mode pill or context chips). Small **context chips** above the input show what is active: student, batch, Verified/Quick. |
| F2 | **Sign-in dialog** with labelled fields and inline errors. **One-click demo accounts** are listed with their scenario. A **profile card** in the sidebar shows ID, batch and semester, with Degree progress and Sign out. Advisors pick an advisee there. |
| F3 | Solid, high-contrast light theme in the university navy. No text over photos. Text colour pairs were checked against WCAG AA (4.5:1); the muted grey was darkened to pass on the page background. Disabled controls are exempt. |
| F4 | **Decision badge** (✓ Eligible / ✕ Not eligible / ◐ Conditional / ⚠ Needs review, plus the course). Citations become **numbered chips**; clicking one opens and highlights its source. A single compact footer shows status, model and time, plus Listen, Copy, prerequisite map and Sources & steps. |
| F5 | The **Sources & steps** panel lists sources in plain words ("Eligibility check: DATA301 for STU_017 — calculated from the record", "Student Handbook (Aug 2026) p.21") and the pipeline as a readable timeline. |
| F6 | A **progress line that names the step**: understanding → regulations → record → writing → verifying. Quick mode shows two steps. |
| F7 | An **error card** with plain wording, **Try again**, and **Use Quick mode** (fewer AI calls). The question is kept. The server's messages were rewritten for students. |
| F8 | **Callouts**: 🔒 privacy safeguard (in plain language), "Needs a human decision", and "model X was busy, Y answered". |
| F9 | Phone layout: the sidebar becomes a drawer (☰), the composer stays at the bottom with a short placeholder, suggestions come first and capabilities are compact. Tested at 390 px; nothing scrolls sideways. |
| F10 | The welcome screen explains the three abilities (rules with sources, eligibility checks, voice and documents). **Suggestions change by role**: guest, student or advisor. Drag-and-drop upload. Upload results are shown as a table with ✔ / ✖ confirmation. |
| F11 | A built-in Markdown renderer that **escapes all HTML first**, then applies bold, lists, headings and links. This removes the CDN dependency and the injection risk; MathJax was removed. |
| F12 | Skip link, `aria-label`s on every icon button, `aria-pressed` on the mic, status regions for progress and toasts, visible focus rings (including the upload button), `prefers-reduced-motion` respected. All `alert()` calls replaced with toasts. |

## 3. Files

- `templates/index.html`: new layout (sidebar, top bar, composer, settings sheet, sign-in dialog).
- `static/styles.css`: new stylesheet (≈350 lines, replacing 1,714 lines of stacked overrides).
- `static/ui.js`: new UI layer (replaces `static/extensions.js`).
- `static/app.js`: chat logic kept; it now uses the UI layer for rendering, progress, errors and the welcome screen.
- `app.py`: mentioned-ID authorisation fix, session rotation on sign-in/out, profile in `/api/me`, friendlier errors.

## 4. Still to check by hand

These need a real device: voice input on Android Chrome, read-aloud voices on Windows and macOS, and a screen-reader pass (NVDA or VoiceOver).
