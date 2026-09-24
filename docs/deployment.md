# Free hosted demonstration

Deploy `deployment/replay/streamlit_app.py` on **Streamlit Community Cloud**, selecting
**Python 3.12** in Advanced settings. The default public experience is a clearly
labelled replay of saved, previously evaluated examples. It makes **no new Gemini
calls**, loads no embedding model, and needs no API secret. The full live RAG code
remains in the repository; a replay is not represented as a live answer. This
lightweight entrypoint installs only Streamlit and its normal dependencies. It
cannot be switched into live mode through secrets or query parameters.

The separate `deployment/streamlit_app.py` entrypoint preserves the full-stack,
protected live option described below. That is a different deployment target;
the public replay instance must not be described as a running live RAG system.

Hosting is free; Gemini usage is a separate provider concern. Nothing in these
files has published an app or validated a Linux cloud build yet.

## Required repository files

Include `deployment/`, `ui/`, `app/`, `ingestion/`, `evaluation/results/`, the
README, and `THIRD_PARTY_NOTICES.md`. For optional live mode, also include these
**public, frozen** files even though `data/processed/` is normally Git-ignored:

- `data/processed/chunks256/chunks.jsonl`
- `data/processed/chunks256/index_manifest.json`
- `data/processed/corpus_manifest.json`
- `evaluation/results/calibration_p1_256.json`

Preserve snapshot bytes across platforms: add a `.gitattributes` rule
`data/processed/**/*.jsonl -text` **before adding the snapshot to Git**. Otherwise
Git newline normalization can invalidate the recorded SHA256 and calibration.
Do not modify the manifest to disguise a changed snapshot.

Never publish `.env`, `.streamlit/secrets.toml`, model caches, `.venv`, Chroma
databases, API ledgers, browser state, or a real access code. Retain the corpus's
CC BY-SA 4.0 attribution and modification notice. The selected frozen chunks are
about 0.56 MiB; the BGE weight file is about 127 MiB and is not committed.

## Dependencies and cold starts

Community Cloud checks the entrypoint directory before the repository root.
`deployment/replay/requirements.txt` contains only `streamlit==1.64.0`, keeping the
default public build small and avoiding Torch/Chroma/Gemini dependency resolution.
Its runtime needs `ui/streamlit_app.py`, `ui/saved_demo.py`, and the saved
`evaluation/results/p1_hybrid_256_evaluation.json`; the remaining project source
can stay in the repository without being imported.

For the separate protected-live target, `deployment/requirements.txt` supplies
the CPU-only PyTorch index and the measured
runtime versions. It does not install the Windows-only lock file. The official
PyTorch index lists a Python 3.12 Linux x86-64 CPU wheel for `2.12.1+cpu`.
No additional apt packages are expected for these wheels. The Linux dependency
resolution and full hosted launch still need to be verified in the actual build.

If live mode is deliberately enabled, its first authorized visit downloads only
`BAAI/bge-small-en-v1.5` revision
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, then embeds the frozen **364 chunks** on
CPU and constructs the same cosine Chroma collection. It does not refetch live
handbook pages, change chunking, switch models, or call Gemini. Subsequent runs
reuse verified assets; matching partial indexes resume safely. Foreign indexes
are rejected, never deleted. Setup hashes the saved chunks and verifies model,
collection, revision, and chunk-profile metadata.

Treat cloud-local files as disposable: restarts/redeployments can require a fresh
download and index build. CPU setup may take minutes. The model and runtime may
consume roughly 0.6–1.5 GiB RAM (an estimate, not a cloud measurement), so the free
host's changing resource allowance can still cause a failed cold start. Saved
replay avoids model/index memory and startup work.

## Optional protected live mode — disabled by default

This section applies only to `deployment/streamlit_app.py`, not the lightweight
replay entrypoint. Deploying that target installs the full RAG dependencies.

Only the owner should enter root-level TOML secrets in Community Cloud's private
Advanced settings/Secrets interface. Do not add them to Git or paste them into
logs. Streamlit exposes root-level secret values as environment variables, which
the existing settings loader supports without code changes.

For the default public replay, **no secrets are required**. Leave
`RAG_CLOUD_LIVE_ENABLED` absent or false on the protected-live target as well
unless live mode has been explicitly authorized. The lightweight replay target
ignores that switch and always stays in saved-demo mode.

The optional live configuration is:

```toml
RAG_CLOUD_LIVE_ENABLED = false  # Enable only after explicit remaining-budget approval.
RAG_CLOUD_ACCESS_CODE = "REPLACE_WITH_A_PRIVATE_RANDOM_CODE_AT_LEAST_16_CHARACTERS"
RAG_CLOUD_BUDGET_ACKNOWLEDGED = false
GOOGLE_API_KEY = "ENTER_THE_REAL_KEY_ONLY_IN_THE_PRIVATE_HOST_SECRET_FORM"
GEMINI_FREE_TIER_CONFIRMED = true
MAX_API_ATTEMPTS = 7
API_MIN_INTERVAL_SECONDS = 5
```

The wrapper checks the private access code **before** loading settings, downloading
weights, or executing a live query. Live mode also requires an explicit budget
acknowledgement and an allowance between 1 and 7. Existing generation safeguards
remain: approved model only, free-tier flag, one SDK attempt per request, at least
five seconds between reserved requests, and no automatic retries.

**Budget limitation:** only seven of the original thirty authorized attempts
remained when deployment preparation began. A fresh cloud ledger cannot know
about local usage, other hosts, or previous discarded cloud instances. Its
per-instance cap is therefore **not a durable combined lifetime cap**. Do not run
local and hosted generation in parallel. Never reboot/redeploy to recover quota.
Disable live mode before a redeploy; reassess the remaining allowance with the
owner before enabling it again. Keep the public app in replay mode if durable
cross-host accounting or further API authorization is unavailable. An access
code reduces casual usage; it is not a complete production authentication system.

## Preserve the local-only network binding

The working project's `.streamlit/config.toml` deliberately binds to
`127.0.0.1`. Keep that local file unchanged. The sanitized publication copy in
`artifacts/publication/` must omit only its `server.address` setting, retaining
the other server, telemetry, and theme settings. This lets the hosted launcher
choose its listening address without exposing the local app on the network.
Do not run the sanitized publication copy locally without explicitly passing
`--server.address 127.0.0.1`.

Community Cloud reads the configuration at the repository root, even when the
entrypoint is in a subdirectory. A nested `.streamlit/config.toml` is not an
isolated cloud override. No official guarantee of a Community Cloud override
for an explicit loopback address was found. Changing the address inside app code
or through app-time secret loading is too late after the server has bound.

## Deployment checklist

1. Review and publish only the approved source/public snapshots to GitHub.
2. In Community Cloud, select the repository, branch, and
   `deployment/replay/streamlit_app.py`; choose Python 3.12.
3. Start with no secrets and verify the saved-demo label, three saved examples,
   fallback example, and source links. This should make zero API calls.
4. Confirm no setup errors or exposed secrets in the app. Review build logs if
   dependency resolution fails; do not switch to paid hosting automatically.
5. Share the resulting `*.streamlit.app` URL only after the actual page works.
   Hosting can sleep after inactivity; availability is not an SLA.

## Official sources checked 2026-09-24

- [Community Cloud overview](https://docs.streamlit.io/deploy/streamlit-community-cloud):
  free hosting linked to GitHub repositories.
- [Deployment settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy):
  select repository, entrypoint, Python version, and private secrets.
- [Dependency discovery](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies):
  Linux environment and entrypoint-directory requirements precedence.
- [File organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization):
  separate dependency files per entrypoint, but one repository-root configuration.
- [Configuration precedence](https://docs.streamlit.io/develop/concepts/configuration/options):
  startup environment variables and CLI flags override project configuration.
- [Secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management):
  keep secrets outside Git; root-level values are exposed as environment variables.
- [Resources and sleep](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app):
  limits can change; documented historical range is 0.078–2 CPU cores,
  690 MB–2.7 GB RAM and up to 50 GB storage; idle apps sleep after 12 hours.
- [CPU PyTorch wheel index](https://download.pytorch.org/whl/cpu/torch/):
  Linux/Python 3.12 CPU wheel availability.
