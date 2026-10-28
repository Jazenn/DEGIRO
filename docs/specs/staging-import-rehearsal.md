# Manual synthetic staging import rehearsal

This package verifies the hosted Python publisher for ticket #47 using invented
CSV records and the real canonical calculation boundary. It does not enable
private browser imports, alter production workflow flags, configure real broker
evidence, or establish private financial reconciliation.

Use the existing approved synthetic staging destination only. In the GitHub
environment `synthetic-staging`, configure these separate secrets privately:

- `STAGING_PUBLISHER_DATABASE_URL`: existing staging schema-owner direct URL.
- `STAGING_EXPECTED_HOST`: independently checked direct staging endpoint hostname.
- `STAGING_EXPECTED_DATABASE`: independently checked database name.

Do not replace `HOSTED_PUBLISHER_DATABASE_URL` or `IMPORT_CALCULATION_SETTINGS`,
enable `HOSTED_IMPORTS_ENABLED`, add credentials to YAML, or point this rehearsal
at a private/production destination. No shared production settings are read.

Run **Synthetic staging import rehearsal** manually from a reviewed main or
integration revision. The workflow has no scheduled or repository-dispatch trigger.
Its `contents: read` token has no repository write permission. Local equivalent:
set the three staging values privately, set
`STAGING_IMPORT_REHEARSAL_APPROVED=synthetic-staging-only`, then run
`python -m backend.staging_imports`.

The runner rejects mismatched destinations and pooled URLs before connecting. It
requires a nonempty, entirely synthetic public Snapshot collection and an
accepted public generation. It creates a unique `staging_import_<uuid>` schema,
applies the existing Snapshot/target/import schemas there, and runs real
`process_next` transactions with invented EUR1,000 acquisition / EUR5 fee /
EUR1,100 value records. It verifies failure/retry retention, exact-upload job
idempotency, completed-job non-replay, overlapping-CSV accounting, explicit
unavailable history, and publication provenance. Only sanitized pass/fail status
and check descriptions are printed; credentials, raw rows and read models are
never logged or uploaded as artifacts.

The disposable schema is removed in `finally`; the public accepted generation is
checked afterward. The publisher internally labels its outputs `private`, so all
invented test generations stay inside that disposable namespace and never replace
the public synthetic Snapshot. If a runner is forcibly terminated, cleanup may
not execute: a schema owner must identify the exact run-owned namespace before
removing it. Never drop a namespace based only on a prefix match.

Local tests verify the destination refusal through the CLI and the hand-computed
overlap example through the canonical import/calculation boundary. Actual Actions
execution against the authorized staging database remains a separate evidence
gate until a successful workflow run is recorded. This rehearsal does not yet
exercise the deployed upload HTTP route, which remains disabled until its
publisher configuration and complete upload/publication workflow pass.
