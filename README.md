# **DashBite — Simple Stage-by-Stage ML Pipeline**

Teaching demo of a modular data + ML application. **DashBite** predicts whether a food-delivery order will be **late**.

Run locally or with Docker Compose. Stages are separate Python modules that share folders under `data/` by default, or under an absolute `DATA_ROOT`. Training and inference are **independent processes** coupled only by timestamped checkpoints in `data/models/`. Inference always uses the **newest** checkpoint.

> **Repository B Note:** This repository builds on the DashBite classroom demonstration. The first section below documents the original classroom pipeline and local workflow. My Repository B extensions are documented separately under **My Repository B Extensions**.

---

# **Original DashBite Classroom Demo**

The following sections describe the original DashBite pipeline, local setup, testing workflow, and design provided as the starting point for this project.

## **Stages**

| Stage | Module | What it does |
|-------|--------|--------------|
| 0 | `pipeline.config`, `pipeline.paths` | Shared config + data folders |
| 1 | `pipeline.simulator` | Writes timed CSV batches to `data/raw/` (“new orders arrived”) |
| 2 | `pipeline.preprocess` | Drops bad rows, adds `hour` / `is_peak` → `data/features/` |
| 3 | `pipeline.train` | Retrains when ≥ `TRAIN_EVERY_N_EVENTS` new labeled rows; writes checkpoints |
| 4 | `pipeline.infer` | Scores unscored rows with newest checkpoint → `data/predictions/` |
| 5 | `pipeline.dashboard` | Streamlit: **Model Pulse** |

## **Setup**

```bash
make install
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## **Makefile shortcuts**

```bash
make help          # list targets
make test          # full pytest gate
make run           # start all stages in background + dashboard
make stop          # stop background pipeline
make clean-data    # wipe runtime CSVs/checkpoints under data/
```

Foreground single stages: `make simulator`, `make preprocess`, `make train`, `make infer`, `make dashboard`.

Agent demo prompts (independent Architect / Implementer / Reviewer chats): `make prompts` → http://localhost:8502

GitHub Pages (static copy of the board): https://kedar-v.github.io/TestingAndContainerisationDemo/

Rebuild after editing prompts: `make prompts-static`

## **Testing gate (required after every stage)**

After each stage you implement or change, run the **full** suite:

```bash
pytest
```

That runs **unit**, **regression**, and **integration** tests together so new work cannot break older stages.

```bash
pytest -m unit
pytest -m regression
pytest -m integration
```

Layout:

```text
tests/
  unit/
  regression/
  integration/
  fixtures/
```

## **Run the pipeline (background stack)**

Classroom default — durable background jobs:

```bash
make run                 # simulator + preprocess + train + infer + Model Pulse
make status              # confirm each stage is UP
open http://localhost:8501
make stop
```

Logs: `.logs/*.log` · PIDs: `.logs/pids/` · Poll default: `POLL_INTERVAL_SECONDS=15`

Foreground single stages (one terminal each): `make simulator`, `make preprocess`, `make train`, `make infer`, `make dashboard`.

## **Config (environment)**

| Variable | Default | Meaning |
|----------|---------|---------|
| `DATA_ROOT` | `<project>/data` | Absolute storage directory; unset or empty uses the default |
| `TRAIN_EVERY_N_EVENTS` | `2000` | Retrain after this many **new** labeled rows |
| `BATCH_SIZE` | `50` | Orders per simulator tick |
| `POLL_INTERVAL_SECONDS` | `15.0` | Sleep between polls/ticks |
| `RANDOM_SEED` | `42` | Training seed |
| `CORRUPT_BATCH_RATE` | `0.25` | Fraction of batches that include NaNs / bad types |

Preprocess logs per-batch **throughput** and **field-level failures** to `data/quality/batch_quality.csv`. Model Pulse shows these live.

## **Design notes for class**

- Intake uses **batch CSV files** under the hood; logs say “new orders arrived”.
- Train **only writes** `data/models/checkpoint_*.joblib`.
- Infer **only reads** that folder and never imports train.
- Dashboards read `data/features/` and `data/predictions/` — test the metric helpers with `pytest`, not the browser UI.

---

# **My Repository B Extensions**

For Repository B, I selected **Option 1: Extend and Containerize DashBite**. I extended the original classroom project using the required AI-assisted development workflow.

My main contributions were:

- Containerizing the application with a shared Docker image
- Creating Docker Compose services for the five DashBite stages
- Adding configurable `DATA_ROOT` storage
- Adding persistent storage using a Docker named volume
- Adding an isolated containerized test service
- Adding focused tests for the new storage behavior
- Updating the documentation for the containerized workflow
- Manually verifying the application, dashboard, tests, and persistent storage

The sections below document these additions and my verification process.

## **Docker Compose**

Prerequisites: Docker Engine with Docker Compose v2 or later (Docker Desktop includes both), a running Docker daemon, and port 8501 available. Run commands from the repository root. Stop a local `make run` stack before using the same dashboard port.

```bash
docker compose config          # validate resolved settings
docker compose build           # build the shared Python 3.13 slim image
docker compose --profile test run --rm --no-deps tests
docker compose up -d           # starts only the five runtime services
docker compose ps
docker compose logs            # inspect all stages
# Follow a stage while the pipeline accumulates data:
docker compose logs -f train infer
docker compose down            # stop/remove containers; retain stored data
```

Open http://localhost:8501 for Model Pulse. Fresh startup needs several 15-second polling cycles to generate enough labeled rows for the first checkpoint; inference waits for that checkpoint. Keep one instance of each stage. Existing polling handles startup order.

All services use `dashbite:latest`. Runtime services share the Compose-managed `dashbite-data` named volume at `/data`, with `DATA_ROOT=/data`. The volume contains `raw/`, `features/`, `quality/`, `models/`, and `predictions/`; host `data/` is separate. Checkpoints, training state, processed markers, and predictions survive `docker compose down` followed by `docker compose up -d`, and processing resumes from those artifacts. Container logs are available through Compose.

The `tests` service is enabled only by the `test` profile. It runs the full existing pytest suite and focused storage tests from the image, with no volume mounts, host source bind mounts, or service dependencies. Its `DATA_ROOT=/tmp/dashbite-test-data` is discarded with the container. The command above returns pytest's exit status (nonzero on failure) and does not start runtime services. Rebuild the image after editing code or tests.

Compose uses the Makefile's demo defaults: `TRAIN_EVERY_N_EVENTS=50`, `BATCH_SIZE=20`, `POLL_INTERVAL_SECONDS=15`, `CORRUPT_BATCH_RATE=0.25`, and `RANDOM_SEED=42`. Override them through your shell or a local `.env` file, for example:

```bash
BATCH_SIZE=30 POLL_INTERVAL_SECONDS=5 docker compose up -d
```

Python defaults in the configuration table above remain unchanged. Local storage can be selected with `DATA_ROOT=/absolute/path make run`; explicit `base` arguments used by tests still mean `base/data` and take precedence over the environment. A relative nonempty `DATA_ROOT` raises a clear error. Compose fixes the runtime mount and root at `/data` so all stages agree.

### **Persistence smoke check**

After logs show training and inference, list the shared artifacts:

```bash
docker compose exec simulator python -c "from pipeline.paths import data_root; print('\n'.join(str(p) for p in sorted(data_root().rglob('*')) if p.is_file()))"

docker compose down
docker compose up -d

# Earlier files should still be present, alongside new output:
docker compose exec simulator python -c "from pipeline.paths import data_root; print('\n'.join(str(p) for p in sorted(data_root().rglob('*')) if p.is_file()))"

docker compose down
```

Confirm raw CSVs, feature CSVs, `quality/batch_quality.csv`, model checkpoints, and prediction CSVs, then check the dashboard displays results. Run the isolated test command while the stack is stopped if comparing artifact checksums; this avoids normal worker writes during the comparison.

**Destructive reset:** the following deletes the named volume and all its pipeline state. Use it only when deliberately resetting disposable data:

```bash
docker compose down --volumes
```

`make clean-data` only clears the default host `data/` directory; it does not reset the Docker volume or a custom `DATA_ROOT`.

## **Manual Smoke Test**

A manual smoke test was performed after the Builder stage to verify the containerized application.

The Docker image built successfully, and the containerized test service completed all **40 tests successfully**. All five runtime services (simulator, preprocess, train, infer, and dashboard) started successfully using Docker Compose.

The Streamlit dashboard was opened at http://localhost:8501 and displayed generated predictions, model metrics, and order-volume data. To verify persistent storage, the containers were stopped and recreated using `docker compose down` and `docker compose up -d`. Previously generated data remained available, and the pipeline resumed processing new data after restart.

These checks confirmed that the documented Docker workflow, main application pipeline, dashboard, tests, and persistent named volume were functioning as expected.

## **AI-Assisted Development Workflow**

This project was completed using **Option 1: Extend and Containerize DashBite**. The goal was to improve the existing DashBite application by creating a reproducible Docker Compose workflow with configurable and persistent data storage.

### **AI Roles**

Three separate AI-assisted stages were used during development:

- **Architect:** Reviewed the existing DashBite project and developed the implementation plan in `docs/plan.md`. The plan focused on using one shared Docker image, five Compose runtime services, configurable `DATA_ROOT` storage, a persistent named volume, and an isolated containerized test service.

- **Builder:** Implemented the approved Architect plan, added the Docker configuration and storage changes, updated the tests and documentation, and verified the implementation.

- **Tester:** Independently compared the completed implementation with `docs/plan.md`, reran the test suite, inspected typical and edge-case behavior, and verified the Docker and Compose configuration.

### **AI Recommendations and My Decisions**

I accepted the Architect's recommendation to implement configurable `DATA_ROOT` storage with a persistent Docker named volume. I chose this improvement because it separates runtime data from the application code and allows pipeline state to survive container recreation.

During the Architect stage, I also chose to keep the implementation relatively minimal. I treated the proposed dashboard health check as optional and decided against adding an unnecessary duplicate end-to-end integration test because the existing suite already covered the pipeline behavior. Instead, focused tests were added for the new storage and path behavior.

During the Tester stage, the Tester suggested optionally clarifying the storage path used in the future Kubernetes documentation. I chose not to make this change because Kubernetes was outside the approved scope of this assignment and the Docker Compose implementation and documentation had already passed verification.

### **Independent Verification**

After the Builder stage, I manually performed a smoke test rather than relying only on the AI-generated test results. I built the Docker image, ran the containerized test suite, and confirmed that all **40 tests passed**. I started all five runtime services and verified that they remained running.

I then opened the Streamlit dashboard at http://localhost:8501 and confirmed that it displayed generated predictions, model metrics, and order-volume data.

Finally, I stopped and recreated the containers using `docker compose down` and `docker compose up -d`. The previously generated data remained available and the pipeline continued processing new data, confirming that the persistent named volume worked as intended.

The independent Tester subsequently found no required corrections and confirmed that the final implementation matched `docs/plan.md`.