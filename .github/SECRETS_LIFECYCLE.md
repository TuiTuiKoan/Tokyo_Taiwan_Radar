---
description: "Complete secrets lifecycle management for Tokyo Taiwan Radar"
---

# 🔐 Secrets Lifecycle Management — Full Inventory

> **Overview**: Tokyo Taiwan Radar uses 5 critical secrets across scraper, CI/CD, and web layers. Each has different rotation schedules, permissions requirements, and sync points.

## 📊 Secrets Inventory

### 1. GITHUB_TOKEN (Fine-grained PAT) — **[✅ AUDIT COMPLETED]**
| Property | Value |
|----------|-------|
| **Purpose** | Create GitHub Issues from Researcher agent (`--create-issue` flag) |
| **Type** | Fine-grained Personal Access Token (recommended) or Classic token |
| **Scope** | Repository: `TuiTuiKoan/Tokyo_Taiwan_Radar` |
| **Permissions** | Issues: write + Metadata: read (fine-grained) or repo (classic) |
| **Rotation cycle** | Every 90 days |
| **Storage** | `scraper/.env` line 11 |
| **Readers** | `scraper/update_source.py::create_github_issue()` |
| **Used in** | Local dev only (not in CI/CD workflows) |
| **Sync locations** | 3 places (see `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`) |
| **Monitoring** | `scraper/secret_reminder.py` (via LINE notification) |
| **Current status** | ✅ Audit completed — expiry: 2026-04-28 2027 (1+ year) |
| **Last rotated** | 2026-04-25 (3 days ago) |

---

### 2. OPENAI_API_KEY — **[AUDIT DEFERRED]**
| Property | Value |
|----------|-------|
| **Purpose** | AI-powered event annotation (GPT-4o-mini) and classification |
| **Used by** | `scraper/annotator.py`, `scraper/translator.py`, `scraper/classifier.py` |
| **Type** | OpenAI API key (standard) |
| **Rotation cycle** | Every 90 days (recommended) |
| **Storage** | `scraper/.env` line 5 |
| **CI/CD usage** | ❌ NOT in workflows (only for local scraper runs) |
| **Readers** | Multiple scraper/*.py files |
| **Sync locations** | 1 place (`.env` only, no docs) |
| **Monitoring** | Manual rotation (no automation) |
| **Status** | ⚠️ **NEEDS AUDIT** — Find all readers + create sync checklist |

---

### 3. DEEPL_API_KEY — **[AUDIT DEFERRED]**
| Property | Value |
|----------|-------|
| **Purpose** | Multi-language translation (fallback to OpenAI) |
| **Used by** | `scraper/translator.py` |
| **Type** | DeepL Free Tier API key |
| **Rotation cycle** | Every 90 days (recommended) or per account billing |
| **Storage** | `scraper/.env` line 4 |
| **CI/CD usage** | ❌ NOT in workflows |
| **Readers** | `scraper/translator.py` |
| **Sync locations** | 1 place (`.env` only) |
| **Monitoring** | Manual rotation |
| **Status** | ⚠️ **NEEDS AUDIT** — Confirm all readers, create sync guide |

---

### 4. LINE_CHANNEL_TOKEN — **[AUDIT DEFERRED]**
| Property | Value |
|----------|-------|
| **Purpose** | Send LINE notifications (backup alerts, weekly reports, secret reminders) |
| **Used by** | `scraper/line_notify.py`, multiple CI/CD workflows |
| **Type** | LINE Bot Channel Access Token |
| **Rotation cycle** | Every 90 days (recommended) or per LINE channel policy |
| **Storage** | `scraper/.env` line 8 **AND** GitHub Secrets |
| **CI/CD usage** | ✅ YES — used in 7+ workflows: |
| | • `.github/workflows/scraper.yml` → `weekly-broadcast`, `backup-check`, etc. |
| | • `.github/workflows/secret-rotation-reminder.yml` |
| | • `.github/workflows/daily-health-check.yml` |
| | • `.github/workflows/weekly-report.yml` |
| **Readers** | `scraper/line_notify.py::send_line_message()` |
| **Sync locations** | 2+ places (`.env`, `secrets.LINE_CHANNEL_TOKEN` in GitHub) |
| **Monitoring** | Manual rotation |
| **Status** | ⚠️ **NEEDS AUDIT** — Full workflow inventory, sync guide required |

---

### 5. SENTRY_DSN — **[AUDIT DEFERRED]**
| Property | Value |
|----------|-------|
| **Purpose** | Error tracking and monitoring for web app (Sentry.io) |
| **Used by** | `web/sentry.*.config.ts`, Vercel env, `scraper/` (if integrated) |
| **Type** | Sentry DSN (Data Source Name) |
| **Rotation cycle** | Every 90 days (recommended) or per Sentry security policy |
| **Storage** | `scraper/.env` line 6 **AND** Vercel environment |
| **CI/CD usage** | ❌ NOT in workflows (only in deployed web app) |
| **Readers** | `web/sentry.client.config.ts`, `web/sentry.server.config.ts`, `web/sentry.edge.config.ts` |
| **Sync locations** | 2 places (`.env`, Vercel env) |
| **Monitoring** | Manual rotation |
| **Status** | ⚠️ **NEEDS AUDIT** — Verify Vercel integration, create rotation guide |

---

### 6. SUPABASE_SERVICE_ROLE_KEY — **[NOT ROTATABLE]**
| Property | Value |
|----------|-------|
| **Purpose** | Supabase backend authentication (bypasses RLS for service functions) |
| **Used by** | `scraper/database.py`, Supabase RPC calls, migrations |
| **Type** | Supabase service role JWT |
| **Rotation cycle** | ⚠️ NOT recommended for rotation (tied to Supabase project) |
| **Storage** | `scraper/.env` line 2 |
| **CI/CD usage** | ✅ Can be used in workflows (currently not) |
| **Security** | **CRITICAL** — Bypass RLS when exposed |
| **Sync locations** | 1 place (`.env` only) |
| **If compromised** | Regenerate in Supabase Dashboard → update all locations |
| **Status** | ℹ️ **NOT PART OF ROTATION** — Document for emergency-only procedures |

---

## 🔄 Rotation Timeline & Responsibilities

### Every 90 Days (Rotation Cycle)
| Day | Task | Who | Status |
|-----|------|-----|--------|
| Day 1–83 | Nothing — tokens are active | — | Normal ops |
| Day 84 | `secret_reminder.py` sends LINE notification listing all secrets | Cron job | Automated |
| Day 85–89 | Developers see notification, plan rotations | Dev team | Manual |
| Day 90 | Execute rotation for each secret (GITHUB_TOKEN, OPENAI_API_KEY, DEEPL_API_KEY, LINE_CHANNEL_TOKEN, SENTRY_DSN) | On-call dev | Manual |
| Day 91–180 | New tokens active for next cycle | — | Normal ops |

---

## 📍 Sync Point Audit Matrix

| Secret | Location 1 | Location 2 | Location 3 | Location 4 | Sync Guide |
|--------|-----------|-----------|-----------|-----------|-----------|
| **GITHUB_TOKEN** | `scraper/.env` (line 11) | `scraper/update_source.py` (L106) | `.github/agents/researcher.agent.md` (L99) | — | ✅ `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` |
| **OPENAI_API_KEY** | `scraper/.env` (line 5) | `scraper/annotator.py` | `scraper/translator.py` | `scraper/classifier.py` | ⏳ **TODO** |
| **DEEPL_API_KEY** | `scraper/.env` (line 4) | `scraper/translator.py` | — | — | ⏳ **TODO** |
| **LINE_CHANNEL_TOKEN** | `scraper/.env` (line 8) | `GitHub Secrets` | `scraper/line_notify.py` | `7+ workflows` | ⏳ **TODO** |
| **SENTRY_DSN** | `scraper/.env` (line 6) | `Vercel env` | `web/sentry.*.config.ts` | — | ⏳ **TODO** |
| **SUPABASE_SERVICE_ROLE_KEY** | `scraper/.env` (line 2) | Emergency only | — | — | ℹ️ N/A |

---

## 🛠️ Next Steps (Roadmap)

### Phase 1: GITHUB_TOKEN (✅ COMPLETED)
- ✅ Audit completed
- ✅ Sync checklist created: `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`
- ✅ Full rotation guide: `.github/instructions/token-rotation.instructions.md`
- ✅ Documentation verified

### Phase 2: LINE_CHANNEL_TOKEN (⏳ RECOMMENDED NEXT)
- [ ] Grep all workflow files for `LINE_CHANNEL_TOKEN` usage
- [ ] Identify all sync locations (`.env`, `GitHub Secrets`, code)
- [ ] Create `.github/LINE_TOKEN_SYNC_CHECKLIST.md`
- [ ] Verify GitHub Secrets is in sync with `.env`
- [ ] Document rotation workflow

### Phase 3: OPENAI_API_KEY (⏳ AFTER LINE_TOKEN)
- [ ] Audit all `scraper/*.py` files for OPENAI_API_KEY usage
- [ ] Identify all readers + create sync checklist
- [ ] Document expected API rate limits (if any)

### Phase 4: DEEPL_API_KEY (⏳ OPTIONAL)
- [ ] Audit `scraper/translator.py` for usage
- [ ] Check if fallback to OpenAI exists
- [ ] Create rotation guide

### Phase 5: SENTRY_DSN (⏳ OPTIONAL)
- [ ] Verify Vercel integration with Sentry
- [ ] Identify all sync locations (`.env`, Vercel, code)
- [ ] Document Sentry project regeneration process

---

## 🚨 Critical Rules

1. **Never commit `.env` to git** — `.gitignore` must include `scraper/.env`
2. **Rotate all secrets together** — Don't stagger 90-day rotations
3. **Test after rotation** — Always verify token works locally before next cycle
4. **GitHub Secrets vs `.env`** — Some secrets exist in both (LINE_CHANNEL_TOKEN, SENTRY_DSN); must stay in sync
5. **If exposed** — Immediately revoke old token/secret, generate new, update all sync locations
6. **Audit quarterly** — Revisit this document every 90 days to ensure sync locations haven't changed

---

## 📝 Audit Trail

| Date | Secret | Action | By | Status |
|------|--------|--------|----|----|
| 2026-05-01 | GITHUB_TOKEN | Audit + sync checklist created | Architect | ✅ Complete |
| 2026-04-25 | GITHUB_TOKEN | PAT rotated | Dev | ✅ Complete |
| 2026-04-28 2027 | GITHUB_TOKEN | Scheduled expiry | — | ℹ️ 1+ year away |
| TBD | LINE_CHANNEL_TOKEN | Audit pending | — | ⏳ TODO |
| TBD | OPENAI_API_KEY | Audit pending | — | ⏳ TODO |

---

**Last updated**: 2026-05-01  
**Maintained by**: Architecture team  
**Review frequency**: Every 90 days (rotation cycle)  
**Related files**:
- `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` (quick reference)
- `.github/instructions/token-rotation.instructions.md` (detailed guide)
- `.github/workflows/secret-rotation-reminder.yml` (automation)
