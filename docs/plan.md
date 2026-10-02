# DashBite — living plan

Classroom handoff for Architect → Implementer → Reviewer. Stages are appended below; do not wholesale-overwrite earlier sections.

## Finalized assignment plan — Option 1: Extend and Containerize DashBite

Status: Architect stage. This section records the accepted implementation scope; implementation has not begun. The earlier classroom handoff below is retained for context.

### Goal and scope

Containerize the existing application with minimum reasonable changes while satisfying the assignment's Dockerfile, Compose, meaningful tests, documentation, and container-readiness requirements.

The two accepted improvements are:

1. Configurable `DATA_ROOT` backed by a persistent Docker named volume.
2. An isolated containerized test service using the same image as the application.

Use one shared image and five Compose runtime services: simulator, preprocess, train, infer, and dashboard. Preserve the existing file-based handoffs, ML behavior, local commands, and test suite. No new framework, database, queue, Kubernetes deployment, or process supervisor is needed. A dashboard health check is optional and is not part of the required scope.

### Existing functionality and gaps

- The pipeline already generates orders, cleans corrupted rows, creates features and quality records, trains timestamped model checkpoints, scores orders with the newest checkpoint, and displays metrics in Streamlit.
- Runtime settings already support environment variables for batch size, polling, training threshold, corruption rate, and training seed.
- Shared path helpers currently use `<project>/data`. Explicit `base` arguments support isolated test workspaces.
- The dashboard explicitly passes `PROJECT_ROOT` to its loaders, which must change for environment-selected storage to work.
- Existing unit, regression, and integration tests cover pipeline behavior and stage handoffs. Reuse them rather than duplicate them with a new end-to-end test.
- The Docker/Kubernetes guide is conceptual. There is no Dockerfile, Compose configuration, implemented `DATA_ROOT`, persistent container storage, or isolated container test command.

### Implementation steps

1. **Establish the baseline.** Run the full existing pytest suite before changing application behavior. Record and investigate any pre-existing failures.
2. **Add storage-path configuration.** Implement resolution in `pipeline/paths.py`: an explicit `base` keeps the existing `base/data` semantics; otherwise a nonempty `DATA_ROOT` selects the data directory directly; otherwise use `<project>/data`. Treat an empty override as unset. Require an absolute path for a nonempty override and give a clear error for relative values. Resolve the environment when helpers are called, not at module import. Keep all five subdirectories under that root. No additional field in the `Config` dataclass is needed.
3. **Update dashboard path usage.** Use the existing loaders without explicitly passing `PROJECT_ROOT`, so the dashboard follows the same storage resolution as the worker stages. Keep explicit-base loader behavior available to tests.
4. **Add the shared Docker image.** Use a supported Python slim base, install requirements before copying source for build caching, set the working directory and Python import path, and enable unbuffered logs. Include `pipeline/`, `tests/` with fixtures, and `pytest.ini` so the same image can run the existing suite. Use a foreground, exec-form default command that Compose can override. Add `.dockerignore` exclusions for Git metadata, virtual environments, runtime data, logs, and caches; retain tests and fixtures in the build context.
5. **Add Compose runtime services.** Run each existing worker module directly in the foreground. Mount one named volume at `/data` in all five runtime services and set `DATA_ROOT=/data`. Start Streamlit in headless mode, bind to `0.0.0.0`, and publish port `8501` only for the dashboard. Use environment-overridable demo defaults aligned with the existing Makefile, including training threshold `50`, batch size `20`, and polling interval `15` seconds. Preserve defaults in Python code. Keep one instance per stage; let the existing polling behavior handle startup order.
6. **Add the isolated test service.** Put a `tests` service behind a Compose `test` profile. It uses the shared image, runs the full pytest suite, mounts no live pipeline volume or host source directory, and has no runtime-service dependencies. Give it a separate ephemeral `DATA_ROOT`, such as `/tmp/dashbite-test-data`. The command must return pytest's exit status and work without starting the application services.
7. **Add only focused automated coverage.** Extend existing path tests for default resolution, custom and empty overrides, invalid relative paths, explicit-base precedence, and creation of the five subdirectories. Add a focused dashboard-loader path test only if existing coverage does not verify reading from an environment-selected root. Do not add a new complete pipeline integration test or tests that merely assert Docker/YAML text.
8. **Document and verify.** Update the README with local setup and tests, Docker prerequisites, build/run/log/stop commands, isolated container tests, environment settings, persistence, and an explicitly destructive volume reset. Align the existing Docker guide with actual configuration and label Kubernetes material as future guidance. Execute the verification steps below.

### Files to create or modify during implementation

| File | Planned change |
| --- | --- |
| `Dockerfile` | Create one shared application/test image. |
| `.dockerignore` | Exclude host and generated artifacts while retaining tests and fixtures. |
| `compose.yaml` | Define five runtime services, shared named volume, runtime settings, and profiled isolated test service. |
| `pipeline/paths.py` | Add environment-aware storage resolution and path validation. |
| `pipeline/dashboard/app.py` | Remove the explicit project-root override from runtime loader calls and any unused import. |
| `tests/unit/test_stage0_config.py` | Extend existing path behavior tests. |
| `tests/integration/test_stage0_paths.py` | Extend existing directory-creation coverage for `DATA_ROOT`. |
| Existing dashboard test file, if needed | Add only a focused environment-selected storage loader check. |
| `README.md` | Document actual setup, execution, verification, configuration, persistence, and reset commands. |
| `docs/docker-k8s-guide.md` | Reconcile conceptual guidance with the implemented Compose workflow. |

No Makefile changes are required. Change `requirements.txt` only if baseline/build verification identifies a compatibility issue requiring a tested constraint. The existing local background script remains in use for local execution.

### Tests and acceptance checks

Automated tests must prove:

- Unset or empty `DATA_ROOT` preserves `<project>/data`.
- An absolute `DATA_ROOT` is used directly, without appending another `data` directory.
- A relative nonempty override fails with a clear error.
- An explicit `base` preserves `base/data`, even when `DATA_ROOT` is set.
- All five helpers and directory creation agree on the selected root.
- Dashboard loaders use environment-selected storage where that behavior is not already covered.

Run the full existing suite after each changed application stage, as required by the repository's testing guidance. Existing fixture and stage-handoff tests remain the pipeline behavior gate.

Container verification commands to document and execute:

```bash
docker compose config
docker compose build
docker compose --profile test run --rm --no-deps tests
docker compose up -d
docker compose ps
docker compose logs
docker compose down
```

Verify that:

- The container test command succeeds without starting runtime services and propagates failures through a nonzero exit status.
- The test container has no mount of the live data volume; running tests leaves existing runtime artifacts unchanged.
- A fresh stack produces raw CSVs, features, quality records, a model checkpoint, and predictions after enough polling cycles.
- The dashboard at `http://localhost:8501` displays results.
- Stopping and recreating the stack preserves earlier artifacts and processing resumes with that state.
- The documented reset command, `docker compose down --volumes`, removes persistent state when deliberately used. Perform reset verification only against disposable assignment data.

Docker/Compose verification provides coverage of packaging and orchestration; do not introduce redundant automated pipeline tests for those checks. If Docker cannot run in the implementation environment, report the limitation and distinguish completed checks from outstanding checks.

### Risks and limits

- Workers write directly to final CSV and checkpoint filenames while readers poll. This existing partial-read risk remains; keep one replica per stage. Investigate failures observed during verification before expanding scope to atomic writes.
- A fresh pipeline needs time to accumulate labeled rows and train its first checkpoint. Waiting for a model is expected startup behavior.
- The named volume retains processed markers, training state, and predictions across recreation. Document restart and reset behavior clearly.
- Ensure every runtime service can write to the shared volume. If using a non-root image user, verify named-volume ownership rather than assuming permissions work.
- Open-ended dependency minimums can change build behavior. Validate the chosen Python/dependency combination and add constraints only when justified.
- Foreground commands improve process management but do not guarantee completion of writes during shutdown. Graceful shutdown changes are outside the accepted minimum scope.
- Runtime data grows over time. A documented manual reset is sufficient for this assignment.
- An optional dashboard health check would demonstrate HTTP responsiveness only, not progress of all pipeline stages. Omit it unless it adds clear value without widening the scope.

### Architect handoff

Implement only the accepted scope above. Preserve existing behavior and tests, demonstrate the two improvements through focused tests and container verification, and document any verification limitations. This plan update does not authorize changes to application code during the Architect stage.

## Wrap-up — Run the full stack

### Goal
Run simulator, preprocess, train, infer, and Model Pulse as durable background jobs via the Makefile.

### Architecture / boundaries
- Public interface: `make run`, `make status`, `make stop`
- Implementation helper: `scripts/pipeline_bg.sh` (nohup + PID files + log redirection)
- Foreground single stages remain: `make simulator|preprocess|train|infer|dashboard`
- Default poll cadence: `POLL_INTERVAL_SECONDS=15`
- Dashboard: http://localhost:8501 (Model Pulse only)

### Manual Smoke Test

#### What we're proving
The full pipeline stays up in the background, writes through `data/raw` → `data/features` → `data/predictions`, and Model Pulse updates on :8501.

#### Terminal
```bash
make run
make status
# optional live logs:
tail -f .logs/simulator.log .logs/preprocess.log .logs/train.log .logs/infer.log
# or open http://localhost:8501
```

#### Watch for
- `make status` shows UP for simulator, preprocess, train, infer, dashboard
- New files under `data/raw/`, then `data/features/`, then `data/predictions/`
- Model Pulse at http://localhost:8501 (volume / scores / failures)
- Logs under `.logs/`; PIDs under `.logs/pids/`

#### Stop
```bash
make stop
make status   # expect DOWN
```
