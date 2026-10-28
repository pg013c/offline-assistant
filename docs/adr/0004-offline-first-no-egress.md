# 0004. Offline first: no network egress at runtime

- Status: accepted
- Date: 2026-10-28
- Related: NFR-01, NFR-02, FR-41, FR-52

## Context

The product promise is that no data leaves the machine and that it runs in an air-gapped environment. This is easy to claim and easy to break: a library downloads a tokenizer on first use, a container sends anonymous usage statistics, a model is pulled lazily.

## Decision

1. **No runtime downloads.** Every model and asset is fetched by an explicit `make models` step into a local directory. At runtime, libraries run with offline flags (e.g. `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) and fail loudly if something is missing.
2. **No telemetry.** Telemetry is disabled in configuration for every component that has it. The list lives in the offline install guide and is checked in review.
3. **One exception, explicit.** The cloud model adapter exists only in comparison mode. It is enabled by `ASSISTANT_ALLOW_NETWORK=1`; without it the adapter refuses to start. The UI shows when network mode is on.
4. **Verified, not promised.** CI starts the stack with container networking disabled (`network_mode: none` or an internal-only network) and runs the end-to-end suite. A test that makes an outbound connection fails.

## Alternatives considered

- **Documented convention only** – breaks silently on the first dependency update.
- **Firewall rules on the host** – useful for the demo recording, but not reproducible in CI.

## Consequences

- Good: the offline claim is a test result, which is the strongest thing to show.
- Bad: first-time setup has an extra step (`make models`), and some libraries need care to stop them reaching out.
- Follow-up: `make offline-check` target, offline install guide (milestone 4).
