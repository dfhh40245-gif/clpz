# R06 — support bundle privacy

Date: 2026-09-18

## Contract

The support bundle is an allowlisted diagnostic artifact. It includes only:

- machine and approved tool-status fields;
- the presence of a fixed set of non-secret environment settings, never their
  values or arbitrary environment names;
- typed job fields: opaque ID, stage, error code, bounded timings, lifecycle
  timestamps, progress, input kind, and clip count; and
- known application-log presence and byte-count metadata.

It excludes log text, free-form errors, transcripts, URLs, media paths,
account fields, raw API fields, database exception text, and all environment
values. Redaction helpers exist solely as defense in depth and cannot cause
untrusted text to enter a bundle.

## Verification

`backend/tests/test_support_bundle.py` uses synthetic values only and proves:

1. `redact_text` removes secrets from quoted JSON, authorization and API-key
   headers, multiline assignments, URLs with credentials, and Dodo, Gumroad,
   and Supabase-style provider tokens;
2. job summaries discard error text, transcript content, URLs, paths, account
   data, and unapproved timing/stage values;
3. diagnostics and environment summaries retain only approved fields; and
4. an emitted offline bundle has log metadata but no log body or synthetic
   password/transcript/environment value; and
5. a live bundle never echoes credentials supplied in the local API URL.

Command from the repository root:

```text
.venv\Scripts\python.exe -m pytest backend/tests/test_support_bundle.py -q --tb=short
```

Result: **9 passed in 0.09s**.
