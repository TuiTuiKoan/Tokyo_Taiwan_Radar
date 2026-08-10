---
title: Authenticated Intake Smoke Closeout
description: Outcome, evidence, and production footprint for the event intake placeholder i18n and authenticated smoke campaign
ms.date: 2026-08-11
ms.topic: reference
keywords:
  - authenticated smoke
  - playwright storage state
  - event intake
  - i18n placeholders
estimated_reading_time: 6
---

## Outcome

The event intake placeholder work is complete in production, and the gap it exposed is
closed. Three hardcoded Japanese example placeholders now resolve through the shared
three-locale catalogs, and the login-gated form that renders them is covered by an
authenticated browser smoke that runs on every `web/**` push to `main`.

The campaign started as a small i18n and contrast change. It grew because verifying that
change honestly required authentication infrastructure the repository did not have.

## Shipped

| Commit | Change |
|----------|--------------------------------------------------------|
| `438578b1` | Localize the three intake placeholders and apply the subtle token |
| `e5ad08f2` | Add the storage-state script and the authenticated smoke spec |
| `0b205d02` | Wire the smoke into CI as `web-auth-smoke` |
| `0bc86fd1` | Move the CI job to Node 22 |
| `7683e89e` | Cover the admin intake and the organizer role gate |

## Verification

| Check | Result |
|-----------------------------------|-----------------------------------|
| Authenticated smoke, local | 11 of 11 against production |
| Authenticated smoke, CI | 11 of 11, run `31406766468` |
| Mutation control | Corrupted expectation fails the suite |
| Production placeholders | `ja`, `zh`, `en` assert distinct strings |
| Role gate | Organizer session denied the admin route |
| Unauthenticated | Admin redirects to login, organizer form absent |
| Type check, lint, i18n parity | Clean |
| Vercel production | Success on `7683e89e` |

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

**A localized string in the HTML does not prove the form rendered it.** The first
production check grepped for the Japanese placeholder and found it, which looked like
proof. It was the next-intl message payload, embedded on every page in that namespace,
and it matched even while logged out. Only an assertion against the input element
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

`deps-verify.yml` and `web-darkmode-smoke.yml` still pin Node 20. Neither runs
`supabase-js` from a script today, so both pass, but either would fail the moment it did.
