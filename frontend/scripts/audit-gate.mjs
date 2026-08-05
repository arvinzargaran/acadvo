#!/usr/bin/env node
/**
 * Fail the build on any high/critical npm advisory that is not explicitly
 * accepted in audit-allowlist.json.
 *
 * `npm audit` alone can't express "we looked at this one and it doesn't apply",
 * so the choice would otherwise be between a permanently red build and dropping
 * the audit altogether. This keeps the gate on while letting a documented,
 * expiring exception through.
 */

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const FAIL_ON = new Set(['high', 'critical']);

function runAudit() {
  try {
    // npm audit exits non-zero when it finds anything, so capture rather than throw.
    return execFileSync('npm', ['audit', '--json'], { cwd: ROOT, encoding: 'utf8' });
  } catch (err) {
    if (err.stdout) return err.stdout;
    throw err;
  }
}

const report = JSON.parse(runAudit());
const allowlist = JSON.parse(readFileSync(join(ROOT, 'audit-allowlist.json'), 'utf8'));

const today = new Date().toISOString().slice(0, 10);
const allowed = new Map();
let expiredEntries = 0;

for (const entry of allowlist.allow ?? []) {
  if (entry.expires && entry.expires < today) {
    console.error(
      `✗ Allowlist entry for ${entry.id} (${entry.package}) expired on ${entry.expires}. ` +
        `Re-check whether it still does not apply, then update or remove it.`
    );
    expiredEntries += 1;
    continue;
  }
  allowed.set(entry.id, entry);
}

const unaccepted = [];

for (const [name, vuln] of Object.entries(report.vulnerabilities ?? {})) {
  if (!FAIL_ON.has(vuln.severity)) continue;

  // `via` is either a string (transitive, via another package) or the advisory
  // object itself. Only the objects carry an advisory id.
  const advisories = (vuln.via ?? []).filter((v) => typeof v === 'object');

  // A purely transitive entry is covered by whichever direct package pulled it
  // in; that package appears in the report on its own.
  if (advisories.length === 0) continue;

  for (const advisory of advisories) {
    const id = advisory.url?.split('/').pop();
    if (id && allowed.has(id)) {
      console.log(`• accepted ${id} (${name}): ${allowed.get(id).title ?? advisory.title}`);
      continue;
    }
    unaccepted.push({ name, severity: vuln.severity, id, title: advisory.title });
  }
}

if (unaccepted.length > 0) {
  console.error('\n✗ Unaccepted high/critical advisories:\n');
  for (const v of unaccepted) {
    console.error(`  ${v.severity.padEnd(8)} ${v.name} — ${v.title} (${v.id})`);
  }
  console.error(
    '\nFix by upgrading, or — only if the advisory genuinely cannot affect this app —\n' +
      'add a justified, expiring entry to frontend/audit-allowlist.json.\n'
  );
  process.exit(1);
}

if (expiredEntries > 0) process.exit(1);

console.log('\n✓ No unaccepted high/critical advisories.');
