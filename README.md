# FairPanel

> **Open-Source, Self-Hosted Hackathon Submission & Judging Portal**  
> Built as a robust Django modular monolith with vanilla JavaScript, modern responsive CSS, embedded SQLite, and zero external runtime dependencies.

[![Tier Status](https://img.shields.io/badge/Acceptance%20Suite-100%25%20PASS-brightgreen)](#acceptance-verification)
[![Claimed Tiers](https://img.shields.io/badge/Claimed-T1%20%7C%20T2-blue)](#claimed-tiers)
[![Verified Tiers](https://img.shields.io/badge/Verified-T1%20%7C%20T2-success)](#acceptance-verification)
[![License](https://img.shields.io/badge/License-Apache%202.0-lightgrey)](file:///d:/Dog%20Food/LICENSE)

---

## 1. Product Overview

FairPanel provides an end-to-end operational platform for running hackathons with institutional integrity. It eliminates the security loopholes, role ambiguities, and scoring biases common in generic event platforms:

- **Strict Workspace Separation**: Dedicated workspaces for **Participants** (`/participant/`), **Judges** (`/judge/`), and **Organizers** (`/organizer/`). No mixed dashboards or shared mutable role state.
- **Cinematic Public Experience**: A responsive, 100vh single-viewport landing page with ambient background video, fallback poster styling, dynamic metric counters, public project showcase, and published results leaderboards.
- **Blinded & Bias-Normalized Judging**: Peer scores are strictly hidden from fellow judges (403 forbidden). The built-in `overlap_bias_v1` algorithm neutralizes harsh and lenient judge biases using empirical Bayes shrinkage ($S = 5$).
- **Tamper-Evident Publishing & Audit**: Frozen result revisions (`ResultSnapshot`) and an append-only operational audit log (`AuditEvent`) capture all administrative decisions with mandatory rationale.
- **Self-Hosted & Offline-First**: Runs standalone on SQLite WAL mode with zero runtime CDN calls or external service requirements.

---

## 2. Acceptance Verification & Tier Status

FairPanel has been evaluated against the official test harness (`spec/run.py .dogfood.toml`). All checks pass with 100% compliance:

```text
DOGFOOD 2026 acceptance report
portal: http://localhost:8080
claimed: T1 T2
fixtures: fixtures.json

T1  gallery is public ................. PASS
T1  project from fixtures shown ....... PASS
T1  closed event refuses submissions .. PASS
T2  judge sees own scores ............. PASS
T2  judge cannot see peer scores ...... PASS
T2  participant blocked ............... PASS
T2  csv export works .................. PASS

claimed T1 T2, verified T1 T2
```

### Claimed & Verified Capabilities
- **T1: Public Discovery & Submission Management**
  - Public gallery accessible to unauthenticated visitors (`/projects/`).
  - Fixture projects (`Glass Signal`, `Solaris OS`, etc.) rendered directly in initial server HTML.
  - Hard submission deadline boundaries (`submissions_close`) rejected with standard error envelopes.
- **T2: Blinded Judging, Role Isolation & Exports**
  - Individual judges view and update their own ballots (`/api/v1/judge/scores`).
  - Blinded review invariant: Probing peer judge scores returns `403 Forbidden`.
  - Non-judging roles (participants) attempting to submit scores return `403 Forbidden`.
  - Official standings and export endpoints generate structured CSV outputs (`/api/v1/events/{id}/exports/results.csv`).

---

## 3. Quick Start & Setup Guide

### Option A: Running with Docker (Recommended)

FairPanel provides a production-ready, self-contained container environment:

```bash
# 1. Clone repository and start container stack
docker compose up --build

# The portal will automatically migrate tables, seed demo fixtures, and launch on port 8080:
# http://localhost:8080
```

### Option B: Local Python Installation

#### Prerequisites
- Python 3.11+
- Git

```bash
# 1. Create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply relational database migrations
python manage.py migrate

# 4. Seed official fixtures and demo data
python manage.py seed_fixtures

# 5. Launch local server
python manage.py runserver 0.0.0.0:8080
```

### Running the Official Acceptance Suite

With the server running at `http://localhost:8080`:

```bash
python spec/run.py .dogfood.toml
```

---

## 4. Pre-Seeded Demo Accounts & Credentials

The fixture seeder initializes authentic accounts for all primary roles:

| Role | Email | Password | Primary Workspace |
| :--- | :--- | :--- | :--- |
| **Organizer** | `organizer@samplehack.org` | `demo-password` | [`/organizer/`](http://localhost:8080/organizer/) |
| **Judge A** | `judge.a@samplehack.org` | `demo-password` | [`/judge/`](http://localhost:8080/judge/) |
| **Judge B** | `judge.b@samplehack.org` | `demo-password` | [`/judge/`](http://localhost:8080/judge/) |
| **Participant** | `participant@samplehack.org` | `demo-password` | [`/participant/`](http://localhost:8080/participant/) |

> **Login Chooser**: Navigate to [`/login/`](http://localhost:8080/login/) to select your role or jump directly via [`/login/organizer/`](http://localhost:8080/login/organizer/), [`/login/judge/`](http://localhost:8080/login/judge/), or [`/login/participant/`](http://localhost:8080/login/participant/).

---

## 5. Five-Minute Walkthrough Script

Follow these steps to experience the complete FairPanel lifecycle:

### Step 1: Public Discovery & Published Results (1 Minute)
1. Open [`http://localhost:8080/`](http://localhost:8080/) to view the cinematic landing page, featuring dynamic metric counters and fast access links.
2. Visit [`http://localhost:8080/projects/`](http://localhost:8080/projects/) to browse the public gallery of submitted projects loaded directly from official fixtures.
3. Visit [`http://localhost:8080/events/evt_01/results/`](http://localhost:8080/events/evt_01/results/) to view the published results leaderboard for the closed fixture event.

### Step 2: Participant Submission Flow (1.5 Minutes)
1. Log in at [`/login/participant/`](http://localhost:8080/login/participant/) with `participant@samplehack.org` / `demo-password`.
2. Access the **Participant Workspace** at [`/participant/`](http://localhost:8080/participant/).
3. Review team members and generate an invitation link at [`/participant/events/evt_demo/team/`](http://localhost:8080/participant/events/evt_demo/team/).
4. Launch the 4-step submission wizard at [`/participant/events/evt_demo/submission/`](http://localhost:8080/participant/events/evt_demo/submission/):
   - **Step 1: Basics** (Title, tagline, track selection).
   - **Step 2: Story & Media** (Markdown description, demo links, screenshots).
   - **Step 3: Verification** (Tech tags, custom question answers).
   - **Step 4: Review & Submit** (Validation check, optimistic concurrency version check, and final submission).

### Step 3: Blinded Judge Evaluation (1 Minute)
1. Log in at [`/login/judge/`](http://localhost:8080/login/judge/) with `judge.a@samplehack.org` / `demo-password`.
2. Access the **Judge Workspace** at [`/judge/`](http://localhost:8080/judge/) to see your queue of assigned projects.
3. Open a review assignment to view the **3-column evaluation workspace**:
   - *Left*: Project overview, video embed, links, and custom answers.
   - *Center*: Rubric criteria with one-click rating buttons and score bounds.
   - *Right*: Qualitative feedback, conflict-of-interest modal, and auto-saving ballot.
4. Attempting to inspect peer judge scores will return `403 Forbidden`.

### Step 4: Organizer Management & Frozen Publishing (1.5 Minutes)
1. Log in at [`/login/organizer/`](http://localhost:8080/login/organizer/) with `organizer@samplehack.org` / `demo-password`.
2. Access the **Organizer Workspace** at [`/organizer/`](http://localhost:8080/organizer/).
3. Navigate to Event Settings (`/organizer/events/evt_demo/settings/`) to manage tracks and rubric criteria.
4. Under Submissions (`/organizer/events/evt_demo/submissions/`), toggle project eligibility with mandatory justification notes.
5. Under Judges (`/organizer/events/evt_demo/judges/`), run the **Balanced Assignment Generator** to distribute reviews.
6. Under Results (`/organizer/events/evt_demo/results/`):
   - Compare **Raw vs. Adjusted (`overlap_bias_v1`)** scores side-by-side.
   - Inspect normalization warnings and judge calibration metrics.
   - Click **Freeze & Publish Official Results** with an audit comment.
   - Download the official CSV export (`/api/v1/events/evt_demo/exports/results.csv`).
7. Review the append-only log under **Audit Trail** (`/organizer/events/evt_demo/audit/`).

---

## 6. Architecture & System Structure

```text
d:/Dog Food/
├── accounts/          # User authentication, profiles, workspace settings
├── api/               # Uniform RESTful API controllers (/api/v1/...)
├── audit/             # Tamper-evident operational event logging
├── events/            # Events, tracks, prizes, questions, rubrics
├── fairpanel_core/    # Django settings, middleware, utility helpers
├── judging/           # Assignments, reviews, overlap_bias_v1 scoring engine
├── projects/          # Submissions, media files, versioning
├── teams/             # Teams, rosters, cryptographically hashed invites
├── spec/              # Official test harness and acceptance fixtures
├── static/fairpanel/  # Static assets (CSS, vanilla JS, SVG logo, fonts)
├── templates/         # Semantic Django templates (Public, Auth, 3 Workspaces)
├── ARCHITECTURE.md    # System design & component architecture
├── DATA-MODEL.md      # Relational schema & role-based projection rules
├── JUDGING.md         # Mathematical formulation & worked normalization example
└── Dockerfile         # Production container definition
```

---

## 7. Testing & Verification

Run the Django automated unit and integration tests:

```bash
python manage.py test
```

Run the official test suite against your running instance:

```bash
python spec/run.py .dogfood.toml
```

---

## 8. License

FairPanel is licensed under the Apache 2.0 Open Source License. See [LICENSE](file:///d:/Dog%20Food/LICENSE) for full details.
