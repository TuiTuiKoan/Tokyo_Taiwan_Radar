---
title: Authenticated Intake Smoke Closeout
description: Outcome, correction record, evidence, and production footprint for the event intake placeholder campaign
ms.date: 2026-08-11
ms.topic: reference
keywords:
  - authenticated smoke
  - playwright storage state
  - event intake
  - i18n placeholders
estimated_reading_time: 8
---

## Outcome

The event intake placeholder work is now complete in production. Three hardcoded
Japanese example placeholders resolve through the shared three-locale catalogs. All
input and textarea placeholders use a dedicated matcha token with WCAG AA contrast in
both themes. The login-gated forms that render the localized examples are covered by an
authenticated browser smoke on every `web/**` push to `main`.

The campaign started as a small i18n and visual-tone request. It grew because verifying
the login-gated form required authentication infrastructure the repository did not have.
It then required a corrective phase after the user demonstrated that the first styling
change had produced no visible difference.

## Correction record

The first closeout at `e3135b90` was incomplete. It correctly reported the localization
and authenticated test infrastructure, but it incorrectly treated the visual-tone work
as complete.

Before the correction, the global `::placeholder` rule used `#9ca3af`. The added
`placeholder:text-fg-subtle` utility resolved to that same `#9ca3af`, so the visual delta
was exactly zero. The earlier test asserted the utility class and a difference between
placeholder text and entered text. Both conditions were already satisfied by the old
global rule, so the test passed without proving a new painted color.

Commit `dc1d2387` corrected the requirement at its controlling surface:

* Added a dedicated placeholder token for both light and dark themes
* Applied the token globally to `input::placeholder` and `textarea::placeholder`
* Added `-webkit-text-fill-color` so WebKit uses the same hint color
* Removed five component utilities that would override the global token
* Replaced the class assertion with a computed `::placeholder` color assertion
* Proved the assertion with a mutation test that restores the old gray and must fail

## Shipped

| Commit | Change |
|----------|--------------------------------------------------------|
| `438578b1` | Localize the three intake placeholders; its styling utility was a visual no-op |
| `e5ad08f2` | Add the storage-state script and the authenticated smoke spec |
| `0b205d02` | Wire the smoke into CI as `web-auth-smoke` |
| `0bc86fd1` | Move the CI job to Node 22 |
| `7683e89e` | Cover the admin intake and the organizer role gate |
| `dc1d2387` | Apply global matcha placeholder colors and assert the computed result |

## Verification

| Check | Result |
|-----------------------------------|-----------------------------------|
| Authenticated smoke, local | 11 of 11 against the corrected local build |
| Authenticated smoke, initial CI | 11 of 11, run `31406766468` |
| Authenticated smoke, corrective CI | 11 of 11, run `31410471982` on `dc1d2387` |
| Mutation control | Restoring the old gray makes the computed-color assertion fail |
| Production placeholders | `ja`, `zh`, `en` assert distinct strings |
| Production light color | `rgb(109, 123, 74)` (`#6D7B4A`), contrast 4.50:1 |
| Production dark color | `rgb(168, 191, 111)` (`#A8BF6F`), contrast 7.62:1 |
| Role gate | Organizer session denied the admin route |
| Unauthenticated | Admin redirects to login, organizer form absent |
| Type check, build, lint delta | Type check and build passed; changed-file lint delta was zero |
| Vercel production | Success on `dc1d2387` |

## Production footprint

Two accounts exist solely for this suite. Both use the reserved `.test` TLD, so neither
can receive mail.

| Account | Id | Role |
|-----------------------------------|----------------------------------------|---------|
| `e2e-organizer@tokyotaiwanradar.test` | `e8a6bd56-7ed8-4502-89e8-1aabb125a9cf` | none |
| `e2e-admin@tokyotaiwanradar.test` | `5936fb07-d1a1-41f1-a326-4e1ba5d28cf5` | `admin` |

Neither profile is publicly listed, because `public_creator_profiles` requires
`is_self_registered = true` and both rows keep the default `false`. Neither account owns
an event. The admin grant does not widen the attack surface: there is no password, the
mailbox is unroutable, and the only path to a session is the service role key, which
already carries full database access.

To revoke, delete the `user_roles` row and the account. The next run of the state script
recreates whatever it needs.

## Lessons

**A design-token class does not prove a visual change.** Resolve the token to its final
painted value and compare that value with the pre-change baseline. Here, the old global
rule and the new utility both resolved to `#9ca3af`, so the implementation changed code
without changing the screen.

**Visual requirements need computed-style and mutation evidence.** A browser assertion
now reads the `::placeholder` pseudo-element color. Replacing the matcha rule with the old
gray makes the test fail, which proves the assertion detects the original regression.

**A localized string in HTML does not prove the form rendered it.** The first production
check grepped for the Japanese placeholder and found the next-intl message payload, which
is embedded even while logged out. Only an assertion against the input element
distinguishes a rendered form from a shipped catalog.

**Sign-in that a browser cannot drive still permits an authenticated test.** Login is
Google OAuth or magic link, so there is no password for Playwright to type. Minting the
session with the service role and letting `@supabase/ssr` serialize the cookies avoids
reimplementing the `base64-` prefix and the chunking rules, and it stays correct when the
library changes them.

**`supabase-js` needs the native WebSocket that arrives in Node 22.** The first CI run
failed with `Node.js detected but native WebSocket not found` after every infrastructure
step passed, because the runner used Node 20 while the workstation used Node 22. Any job
that executes `supabase-js` outside the Next.js runtime needs Node 22.

## Remaining work

No functional campaign work remains.

`deps-verify.yml` and `web-darkmode-smoke.yml` still pin Node 20. Neither runs the
authenticated storage-state generator, so this is a non-blocking runtime-modernization
observation rather than an open campaign defect. Any future workflow step that executes
`supabase-js` outside Next.js must use Node 22.

## Worktree closure

The three campaign worktrees and their local feature branches are closed:

| Worktree | Branch | Final state |
|----------|--------|-------------|
| `ttr-event-intake-placeholder-worktree` | `feat/event-intake-placeholder` | Removed |
| `ttr-auth-smoke-worktree` | `feat/auth-smoke` | Removed |
| `ttr-placeholder-matcha-worktree` | `feat/placeholder-matcha` | Removed |

Final reconciliation found an unregistered four-file skeleton at the last worktree path.
Each file's Git blob exactly matched `origin/main`, and the directory contained no
`tmp/` or unique audit artifacts. The skeleton was removed. No campaign worktree or
branch reference remains.
