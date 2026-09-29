# FairPanel

FairPanel is a self-hosted hackathon submission and judging portal built for the DOGFOOD 2026 brief. It has separate organizer, judge, and participant workspaces, a public event gallery, and a documented scoring engine. The source is licensed under the [MIT License](LICENSE).

## Run locally

With Docker and a locally available Python base image, run:

```bash
docker compose up --build
```

Open <http://localhost:8080>. The container migrates an SQLite database and imports the bundled fixture event and a separate open demo event. Database, uploads, and the generated Django secret persist in Docker volumes. The Compose port is bound to `127.0.0.1`. The background video is an optional remote enhancement; the portal remains usable without it. Image building may need network access to fetch Python and packages. A fully disconnected first install needs preloaded images.

Docker Compose was verified from a fresh named volume on Windows Docker Desktop: the image built, all migrations applied, the bundled fixture seeded, and the HTTP checker passed all seven checks. A container restart preserved two events and 41 projects. The Compose service uses Django's development server for local evaluation; it is not a production deployment.

For local Python development:

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_fixtures
python manage.py runserver 127.0.0.1:8080
```

The local settings use a development-only secret. Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, and a suitable server/static-file setup before any network-facing deployment. The bundled Docker command runs Django's development server and is intended for local evaluation.

## Demo accounts

The seed command prints signed bearer headers for the official checker. They expire after 12 hours; run the seed command again to refresh `.dogfood.toml`. Browser users still use Django sessions and CSRF. Demo passwords are `DemoPassword2026!` for these accounts:

| Workspace | Email |
|---|---|
| Organizer | `organizer@fairpanel.local` |
| Judge A | `tomas.varga@example.org` |
| Judge B | `wei.lindqvist@example.org` |
| Participant | `participant@fairpanel.local` |

The imported `evt_01` fixture has a historical submission deadline and is closed. Use `evt_demo` to exercise an open submission. The seeder preserves previously imported event, project, review, and password changes on repeat runs. It generates refreshed checker tokens on each run and updates `.dogfood.toml` accordingly. Demo accounts and headers are for local evaluation only.

## Three workspaces

- `/organizer/`: create and manage owned events, configure schedule and rubric, invite and assign judges, review eligibility, inspect progress and results, publish a snapshot, and export CSV.
- `/judge/`: see assigned projects in authorized tracks, save/submit own scores, report conflicts, and edit reviewer preferences. Judges cannot create their own assignments or read peer ballots.
- `/participant/`: join events, form teams, accept invitations, save a draft, and submit or edit a project before the deadline.

Public pages include `/events/`, an image-led `/projects/` gallery with search and event/track filters, project details, and results once published. Participants can provide a cover image URL and up to six additional image URLs in the submission wizard. A user has one operational role per event; roles can differ across events. The API checks permissions on requests, not just in page navigation. Account security is shared across workspaces and labeled separately from role preferences.

## Judging

Each criterion has an organizer-set range and weight. Submitted reviews produce weighted scores from 0 to 100. Projects are ranked within their tracks. The optional `overlap_bias_v1` adjustment estimates judge severity from shared projects and shrinks small-sample estimates toward zero. It becomes unavailable when there is insufficient overlap or the reviewer comparison graph is disconnected. Unreviewed projects have no score or rank. See [JUDGING.md](JUDGING.md) for the formula, assumptions, and limits.

Publishing records a result snapshot and a fingerprint of its scoring inputs. Existing published scores, ranks, names, and track labels are read from the snapshot. The audit log records application actions; it is not tamper-proof. This implementation is a local single-instance baseline and has not had a production security review.

## Verification

Run the Django tests:

```bash
python manage.py test
```

With the server running, run the bundled official checker and save its output:

```bash
python spec/run.py .dogfood.toml --fixtures fixtures.json > acceptance-report.txt
```

The [committed acceptance report](acceptance-report.txt) records seven passing checks, including a run against the Docker container. The seed command generates the ignored `.dogfood.toml` file needed by this checker; rerun it when its signed headers expire. For the Docker run, copy the generated file from the container with `docker cp fairpanel_web:/app/.dogfood.toml .dogfood.toml`. The checker tests a small set of public gallery, deadline, judge-isolation, and CSV behaviors. It does not verify every T1/T2 requirement or T3/T4, so the tier claim is limited to what the report and code support. The Python checker may exit with code zero even when individual checks fail; inspect its PASS/FAIL lines.

## Demo walkthrough

The [five-minute narrated video](demo/fairpanel-demo.mp4) was recorded from the running Docker app at 1280×720. The matching [script and timecodes](demo/DEMO-SCRIPT.md) cover the public gallery, participant team and submission flow, private judge reviews, organizer assignments, and the results preview. The video is a screen-based walkthrough with synthesized narration; it does not claim a live human presentation. To regenerate it on Windows, install the optional `playwright`, `Pillow`, and `imageio-ffmpeg` Python packages, start the seeded portal on port 8080, and run `python demo/record_demo.py`. The recorder uses installed Chrome and Windows speech voices; these are recording tools, not application runtime dependencies.

## Data and documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): structure, deployment boundary, and role isolation.
- [DATA-MODEL.md](DATA-MODEL.md): schema and import/export paths.
- [JUDGING.md](JUDGING.md): assignments, scoring, adjustment, and limitations.
- `fixtures.json` and `spec/`: the supplied synthetic data and acceptance checker.

Current limitations: no T3 voting/comments, no T4 webhooks/certificates/embeds, and no email delivery for invitations. Invite links can be copied in the UI. A fully disconnected first Docker image build still requires preloaded base images and Python packages.
