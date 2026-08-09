#!/usr/bin/env tsx
/**
 * e2e-auth-state.ts — provision Playwright storage state for authenticated smoke tests.
 *
 * Sign-in is Google OAuth or magic link only, so there is no password flow a browser
 * test can drive. This mints a real session with the service role and lets
 * @supabase/ssr serialize the cookies, so the encoding always matches what the app's
 * server client reads back.
 *
 * Usage:
 *   pnpm e2e:auth-state           organizer state only
 *   pnpm e2e:auth-state --admin   also provision an admin-role state
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { createServerClient } from "@supabase/ssr";
import { createClient, type SupabaseClient, type User } from "@supabase/supabase-js";

const ROOT = process.cwd();
const AUTH_DIR = join(ROOT, "tests/e2e/.auth");
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const WITH_ADMIN = process.argv.includes("--admin");

/** Reserved TLD: these addresses can never receive real mail. */
const ORGANIZER_EMAIL = process.env.E2E_ORGANIZER_EMAIL ?? "e2e-organizer@tokyotaiwanradar.test";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "e2e-admin@tokyotaiwanradar.test";

function loadEnvLocal(): void {
  const file = join(ROOT, ".env.local");
  if (!existsSync(file)) return;
  for (const line of readFileSync(file, "utf8").split("\n")) {
    const match = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim());
    if (!match) continue;
    const [, key, rawValue] = match;
    if (process.env[key]) continue;
    process.env[key] = rawValue.replace(/^["']|["']$/g, "");
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required (set it in web/.env.local)`);
  return value;
}

async function findUserByEmail(admin: SupabaseClient, email: string): Promise<User | null> {
  const target = email.toLowerCase();
  for (let page = 1; page <= 25; page += 1) {
    const { data, error } = await admin.auth.admin.listUsers({ page, perPage: 200 });
    if (error) throw error;
    const hit = data.users.find((user) => user.email?.toLowerCase() === target);
    if (hit) return hit;
    if (data.users.length < 200) return null;
  }
  return null;
}

async function ensureUser(admin: SupabaseClient, email: string): Promise<User> {
  const { data, error } = await admin.auth.admin.createUser({ email, email_confirm: true });
  if (!error && data.user) return data.user;

  const existing = await findUserByEmail(admin, email);
  if (existing) return existing;
  throw error ?? new Error(`could not provision ${email}`);
}

/** The organizer intake page requires a creators row with a handle. */
async function ensureOrganizerProfile(
  admin: SupabaseClient,
  user: User,
  handle: string,
): Promise<void> {
  const { error } = await admin.from("creators").upsert(
    {
      user_id: user.id,
      user_handle: handle,
      organizer_name_ja: "E2E テスト主催者",
      organizer_name_zh: "E2E 測試主辦方",
      organizer_name_en: "E2E Test Organizer",
      // Keep false so public_creator_profiles never exposes the test account.
      is_self_registered: false,
    },
    { onConflict: "user_id" },
  );
  if (error) throw error;
}

async function ensureAdminRole(admin: SupabaseClient, user: User): Promise<void> {
  const { error } = await admin
    .from("user_roles")
    .upsert({ user_id: user.id, role: "admin" }, { onConflict: "user_id" });
  if (error) throw error;
}

async function writeStorageState(
  admin: SupabaseClient,
  supabaseUrl: string,
  anonKey: string,
  email: string,
  statePath: string,
): Promise<void> {
  const { data: link, error: linkError } = await admin.auth.admin.generateLink({
    type: "magiclink",
    email,
  });
  if (linkError) throw linkError;

  const tokenHash = link.properties?.hashed_token;
  if (!tokenHash) throw new Error(`no hashed_token returned for ${email}`);

  const jar = new Map<string, string>();
  const client = createServerClient(supabaseUrl, anonKey, {
    cookies: {
      getAll: () => [...jar].map(([name, value]) => ({ name, value })),
      setAll: (cookies) => {
        for (const cookie of cookies) jar.set(cookie.name, cookie.value);
      },
    },
  });

  const { data: session, error: verifyError } = await client.auth.verifyOtp({
    token_hash: tokenHash,
    type: "magiclink",
  });
  if (verifyError) throw verifyError;
  if (jar.size === 0) throw new Error(`no auth cookies produced for ${email}`);

  const target = new URL(BASE_URL);
  const expires = session.session?.expires_at ?? Math.floor(Date.now() / 1000) + 3600;

  const storageState = {
    cookies: [...jar].map(([name, value]) => ({
      name,
      value,
      domain: target.hostname,
      path: "/",
      expires,
      httpOnly: false,
      secure: target.protocol === "https:",
      sameSite: "Lax" as const,
    })),
    origins: [],
  };

  mkdirSync(AUTH_DIR, { recursive: true });
  writeFileSync(statePath, `${JSON.stringify(storageState, null, 2)}\n`);
  console.log(`  wrote ${statePath} (${storageState.cookies.length} cookies)`);
}

async function main(): Promise<void> {
  loadEnvLocal();
  const supabaseUrl = requireEnv("NEXT_PUBLIC_SUPABASE_URL");
  const anonKey = requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY");
  const serviceKey = requireEnv("SUPABASE_SERVICE_ROLE_KEY");

  const admin = createClient(supabaseUrl, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  console.log(`organizer: ${ORGANIZER_EMAIL}`);
  const organizer = await ensureUser(admin, ORGANIZER_EMAIL);
  await ensureOrganizerProfile(admin, organizer, "e2eorganizer");
  await writeStorageState(
    admin,
    supabaseUrl,
    anonKey,
    ORGANIZER_EMAIL,
    join(AUTH_DIR, "organizer.json"),
  );

  if (WITH_ADMIN) {
    console.log(`admin: ${ADMIN_EMAIL}`);
    const adminUser = await ensureUser(admin, ADMIN_EMAIL);
    await ensureOrganizerProfile(admin, adminUser, "e2eadmin");
    await ensureAdminRole(admin, adminUser);
    await writeStorageState(
      admin,
      supabaseUrl,
      anonKey,
      ADMIN_EMAIL,
      join(AUTH_DIR, "admin.json"),
    );
  } else {
    console.log("admin state skipped (pass --admin to provision it)");
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
