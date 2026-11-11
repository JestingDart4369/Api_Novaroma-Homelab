# Security hardening review and deployment notes

Scope: local review of `legacy/app`, based on commit
`baa64ada52d57b88017166afd872fbae93497bc1`. No production database,
production environment, live authentication, paid provider request, commit, push,
or deployment was performed. This is a bounded hardening patch, not a claim that
the service is fully secure. Parent/independent review is required before release.

## Confirmed findings and fixes

Evidence below refers to **baseline** file lines at the above commit (not shifted
lines in this patch). Regression tests are in `legacy/tests`.

| Finding | Baseline evidence | Change / regression coverage |
|---|---|---|
| Unlimited unauthenticated password attempts | `app/main.py:110-116`, `app/auth.py:44-50`; authenticated proxy rate limits do not cover login | Atomic SQLite UPSERT budgets before account lookup/password verification: 10/account and 50/socket peer per 15-minute fixed window. Counters persist across workers/restarts. Both unknown and disabled accounts count. Tests exercise competing connections, source/account separation, expiry and spoofed forwarding headers, and HTTP hashing call counts. |
| Missing pepper and broken long-password verification | `app/auth.py:14-22` hashes long UTF-8 passwords with SHA-256 before bcrypt but verification does not | New versioned `v1$argon2id$...` hashes use Argon2id (64 MiB, 3 iterations, parallelism 1), random library-generated salt, and HMAC-SHA256 of the password under a separate mandatory pepper. Exact legacy bcrypt / SHA-256-before-bcrypt compatibility is retained and successful login upgrades with compare-and-swap; failed login never changes the stored hash. Pepper can come from environment or a secret file. Optional one previous pepper supports gradual rotation. |
| Admin can create Root; superAdmin can reset/promote Root; lower administrators can disable higher accounts | `app/routes/settings/users.py:76-99`, `103-128`, `131-163` | Non-Root administrators may only create/manage strictly lower-ranked accounts and grant strictly lower roles. Self-role/self-disable restrictions remain; self-password reset remains possible for superAdmin/Root. Root is explicitly trusted. New/reset passwords must be 12–4096 characters; existing shorter passwords are still accepted and migrated. |
| Missing JWT required claims / no durable revocation | `app/auth.py:25-41`, `app/security.py:14-20` | Independent signing secret minimum 32 bytes, known template placeholders rejected; HS256 allowlist, required issuer/audience/expiry/issued-at/subject/JTI/credential-version; bounded numeric subject and one-hour maximum lifetime. DB credentials and durable per-account nonce bind tokens to current password/role/state. Password/role changes and enable/disable invalidate old tokens, including disable→enable and role roundtrips. Deleted/inactive users rejected. Old-format tokens deliberately require re-login. |
| Archive redirects can fetch an arbitrary redirect target | `app/routes/library.py:278-281`, `300-303`, `332-339` | GET/HEAD/DELETE no longer follow redirects. Mock upstream proves a redirect to loopback is rejected without a second request. Buckets validated and file paths URL-quoted so query/fragment characters cannot change request semantics. Redirecting archive objects now return 502; see compatibility notes below. |
| Secrets can be reflected in errors / notifications | `app/routes/pushcut.py:84-92`, `app/routes/email.py:89-90,131-132`, `app/notifications.py:26-27,39-45,67-71`, `app/main.py:88-90`; framework validation reflects submitted `input` | Generic provider errors, sanitized request-validation responses, and handled HTTPX transport errors. Alerts contain exception class, not raw exception/traceback; HTML body escaped. Tests use secret canaries. Docker disables Uvicorn access logging because legacy Grade URLs contain credentials. |
| Wrong reset timestamp on non-UTC hosts | `app/rate_limit.py:95-96,110-111` | Use timezone-aware UTC timestamps; regression switches process TZ to Europe/Zurich. |
| Dependency advisory findings in freshly resolved environment | Original `requirements.txt` uses python-jose and passlib | Replace python-jose with PyJWT and remove passlib; use bcrypt directly only for legacy verification and add argon2-cffi. Initial pip-audit reported python-jose and its ecdsa dependency; the final audited dedicated environment reports no known vulnerabilities. This does not establish the package versions installed in production. |

### SQL injection review

No confirmed SQL injection was found in this scope. Existing user and settings
queries use SQLAlchemy expression-bound parameters; new login budget/revocation
writes also use bound SQLAlchemy statements. A regression submits `' OR 1=1 --`
as the username and proves authentication is denied and the users table unchanged.
Do not describe this as fixing a demonstrated SQLi, or as proving all SQL paths safe.

## Migration and release checklist (operator actions; not executed here)

1. Review this diff and run the tests on a disposable copy. Install the updated
   `legacy/requirements.txt` in a clean environment/image; do not reuse an old
   environment containing python-jose/passlib. Dependencies are not fully locked;
   record/pin the release's resolved versions and re-audit before building.
2. Schedule a maintenance stop of **all** old workers. Take an encrypted, consistent
   SQLite backup (SQLite backup API or stop every writer and copy the file; do not
   copy only the main file while WAL writers are active). Preserve the old image,
   config and signing key securely. Test restoring a disposable backup.
3. Generate an **independent** JWT signing key and password pepper using a local
   cryptographic generator. Example command, executed twice for two different values:

   ```sh
   python -c 'import secrets; print(secrets.token_urlsafe(48))'
   ```

   The command is an instruction, not an embedded secret. Do not put generated
   values in tickets, git, terminal transcripts, CI output or this document. Store
   them in your secret manager. Do not reuse provider keys or the signing key as
   the pepper. Minimum configured length is 32 bytes; length checks do not prove
   entropy. Rotate a weak/shared signing key rather than merely padding it.
4. Configure `JWT_SECRET` and **exactly one** of `PASSWORD_PEPPER` or
   `PASSWORD_PEPPER_FILE`. For a file, mount a read-only secret into the container,
   e.g. `/run/secrets/password_pepper`, readable only by the service user/operator.
   The example Compose file does not automatically mount secrets: explicitly add
   the chosen mount/Compose secret before release. A newline at the end of a
   text secret file is stripped. Current pepper is mandatory even with only legacy
   hashes; startup/authentication fail closed when it is absent/invalid. Back up
   pepper(s) separately from the database, encrypted and access-controlled. **Losing
   the pepper makes already-migrated passwords unverifiable**; a database-only
   backup is not sufficient for recovery.
5. Start one new worker first. Startup adds `login_attempts` and `token_state`
   tables using `create_all`; it does not replace/drop/reseed `users` or add columns
   to existing tables. Existing user IDs, roles and password hashes are preserved.
   Ensure the existing SQLite file and directory are writable. SQLite must support
   UPSERT and RETURNING (3.35+); Python 3.12 image/test environment supports them.
   Do not run mixed old/new workers: old workers bypass the new login limits and
   can mint/accept incompatible tokens. After initialization, start other new
   workers sharing that same local SQLite database file. Multi-host deployments
   or independent DB copies require a different central rate-limit backend.
6. Existing bcrypt accounts are migrated lazily on their **successful** login,
   including the original UTF-8 >72-byte SHA-256-before-bcrypt scheme. Do not bulk
   overwrite hashes or force-reset all accounts for this migration. The stricter
   new-password policy does not reject existing short passwords during login.
   Concurrent credential modification may require retrying login; a migration
   does not intentionally reset or permanently lock an account. Test a known
   legacy account on a disposable clone first. Never deploy by deleting the DB.
7. All previously issued JWTs are intentionally invalid after this release (new
   issuer/audience/credential-version required), and after a signing-key rotation.
   Clients retain the same login JSON and bearer response shape, but must log in
   again. Verify a controlled local login and protected request before reopening
   traffic. Revoke/reset suspicious accounts if the prior escalation flaw may
   have been exploited; this patch does not investigate historical compromise.
8. Keep `--no-proxy-headers` with this limiter. It uses the ASGI socket peer and
   ignores CF-Connecting-IP/X-Forwarded-For. The Docker command pins this behavior;
   non-Docker deployments must pass the same flag. Behind a shared Cloudflare
   Tunnel, the 50/source budget is shared by clients behind the tunnel. This is
   deliberately conservative and can cause temporary shared login throttling.
   Do not fix that by trusting arbitrary headers. A future trusted-proxy design
   needs a restricted origin, explicit proxy allowlist and tested header handling.
9. Keep Uvicorn access logs disabled until Grade credentials move out of URLs.
   Independently redact/disable query logging at Cloudflare, reverse proxies,
   traces and monitoring; avoid HTTPX debug/info request logging (provider keys
   may be query parameters). Never enable FastAPI debug tracebacks on this service.
10. Rollback: stop all workers and restore a coherent pre-release DB/image/config
    snapshot. Old code cannot verify new Argon2id hashes. Merely rolling back the
    image after lazy migration will lock migrated accounts out. A rollback of the
    DB also discards subsequent changes, so plan a maintenance window and recovery
    procedure instead of improvising a downgrade.

### Pepper rotation without an immediate mass password reset

- Take/verify backups first. Stop all workers and configure a new current pepper
  plus the old pepper as `PASSWORD_PREVIOUS_PEPPER` or
  `PASSWORD_PREVIOUS_PEPPER_FILE` (exactly one previous source, too). New hashes
  always use current pepper; a successful old-pepper login rehashes to current.
  This also revokes tokens bound to that account's old hash.
- Restart all workers with the same pair. Only one previous key is supported;
  verification work is bounded to at most two Argon2 checks, with login throttling
  ahead of them. Do not rotate again while any account still needs an older key.
- This format has no pepper key ID, so do not infer migration completion from a
  hash prefix or number of logins. Keep the old key until all accounts have a
  known successful post-rotation login or an administrative password reset. For
  dormant/unverified accounts, arrange a controlled reset before removing it.
- Remove the previous source from every worker together after that process. Keep
  historical keys needed by encrypted historical DB backups under the backup's
  retention policy. If a pepper was compromised, retaining it prolongs exposure:
  expedite account resets/re-hashing and revoke affected sessions; graceful
  rotation alone is not a compromise-response guarantee.

## Intentional compatibility/security changes

- Login response remains `{access_token, token_type: "bearer"}`. Malformed login
  field types/oversize values return generic 400, not a 500. Validation stays 422
  but omits original submitted values/context. New/reset passwords require 12–4096
  characters; login accepts existing passwords up to 16 KiB of UTF-8 data.
- Privileged administration now obeys strict hierarchy rather than permitting
  admins to manufacture or take over Root accounts. Root may still create/manage
  privileged users; no single-Root invariant is introduced.
- Repeated **successful and unsuccessful** login attempts both consume the fixed
  15-minute budgets. 429 includes Retry-After; counters are not cleared on success.
  Fixed windows permit boundary bursts; this is not a sliding-window/global DDoS
  defense. Accounts are not permanently disabled by throttling.
- Archive redirects return 502 rather than being followed. Objects depending on
  Internet Archive redirect behavior may no longer download via this endpoint.
  An egress-controlled, validated redirect implementation needs separate design;
  do not re-enable blanket redirects to recover functionality.
- Startup remains import-time initialization, as before; initialization should be
  serialized before running additional workers, rather than racing create/bootstrap.

## Remaining risks / outside this bounded patch

- **Grade credentials still appear in legacy query parameters**, e.g.
  `app/routes/Grade.py:75,92-95,138-139` at baseline. Server access logging is
  disabled but URLs can still leak through other infrastructure/history. Migrating
  to header tokens and JSON password bodies requires coordinated client changes.
- Authenticated proxy API/role quotas remain in-memory/per-worker, unlike the new
  persistent **login** limiter. Restart/multiple workers can exceed provider quotas.
- Hardware/software resources do not have per-device ownership or scoped service
  credentials. Any authenticated account can submit heartbeats; hardware heartbeat
  can overwrite the shared config (`app/routes/hardware.py:103-122` baseline).
  Control-plane config and reported telemetry should be separated in a coordinated
  device-auth redesign. Review who has a normal account before exposure.
- Broad authenticated email/Pushcut/Archive capabilities are retained as the
  existing product contract. Least-privilege per-integration scopes, destination
  policies, payload/download size limits, and upstream response-type controls
  require further work. Archive responses are buffered; egress controls are still
  recommended even though automatic redirects are disabled.
- No MFA, recovery workflow, user-facing per-session logout, central audit trail,
  or timing equalization for unknown accounts was added. Auth responses are generic,
  but timing can still reveal account existence. Account/source throttling can be
  used for temporary denial of login; edge/global abuse protections are needed.
- Compose still publishes port 8080 on all interfaces and the image runs as root.
  Restrict the origin/firewall/LAN publication, use an unprivileged container user
  with planned volume ownership, set resource/body limits, and pin the cloudflared
  image as separate operational hardening. Those deployment changes were not made.
- Dependency audit is advisory-database based, not a proof of exploit absence.
  Full dependency locking, image scanning, live proxy trust verification, production
  schema/version checks, backup restoration and staging load tests remain operator
  acceptance work. Unexpected non-HTTPX/non-provider errors can still reach server
  error logs; restrict log access and configure redaction.

## Reproduction / verification

Use a dedicated local Python 3.12 virtualenv (not the global environment):

```sh
python -m venv /path/to/disposable-venv
/path/to/disposable-venv/bin/pip install -r legacy/requirements.txt pytest pip-audit
/path/to/disposable-venv/bin/pytest legacy/tests -q
/path/to/disposable-venv/bin/python -m compileall -q legacy/app
/path/to/disposable-venv/bin/pip-audit --local
git diff --check
```

Tests override DB_URL, signing/pepper values and provider keys with offline test
fixtures before application imports, use disposable SQLite files, mock HTTP/Resend,
and perform no live login/provider calls. SQLite synchronous writes are disabled
**only on disposable test engines** because host fsync stalls caused lock timeouts;
production SQLite durability settings are not disabled. Locking and atomic UPSERT
behavior are still exercised with concurrent independent connections. The existing
Windows-specific rate-limit script could not collect (removed symbols/nonexistent
methods); it is replaced with real assertion tests of the current interface.

Security behavior changes were introduced with observed failing regression tests
and rerun to green. Supplemental existing-behavior/SQLi characterization tests are
not claims of previously failing vulnerabilities. One test dependency warning
(Starlette TestClient prefers httpx2) is non-fatal; runtime uses HTTPX and no package
switch solely to silence the warning was made.

Final local verification: `pytest legacy/tests -q` returned **48 passed, 1 warning
in 8.48s**; `compileall -q legacy/app` and `git diff --check` exited successfully;
`pip-audit --local` returned **No known vulnerabilities found** in the dedicated
Python 3.12 test environment. No staging/production release acceptance is implied.
