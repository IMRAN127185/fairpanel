# FairPanel demo script

This narration accompanies [fairpanel-demo.mp4](fairpanel-demo.mp4), recorded from the live Docker app. Runtime is approximately five minutes and sixteen seconds. The demo uses bundled synthetic fixtures and does not publish results or send invitations.

## 00:00–00:25 — FairPanel: every project deserves a fair review

Screen: `/` (introduction).

Welcome to FairPanel, a self-hosted hackathon portal for three distinct groups: organizers, participants, and judges. The public site introduces events and projects, while each role gets its own workspace. This walkthrough uses the bundled synthetic data and a live Docker container. It shows the submission journey, private judging, and transparent result review.

## 00:25–00:48 — Explore the public project gallery

Screen: `/projects/` (public showcase).

The project gallery is open to everyone. Teams appear as visual cards with a title, short description, event, and track. Visitors can search by project or team, filter by event and track, and sort the entries. Submitted, eligible projects are visible here; private drafts do not appear in the public showcase.

## 00:48–01:10 — Read a project story

Screen: `/projects/prj_01/` (project detail).

Opening a project shows its longer description, team, technologies, and any repository, live demo, or video links supplied by its creators. Teams can add a cover image and more gallery images when they submit. Organizer-only answers stay private. This lets the public appreciate the work without exposing internal judging material.

## 01:10–01:32 — Discover events and deadlines

Screen: `/events/` (public events).

The events area gives prospective participants a place to discover active hackathons and see key dates. Each event can define tracks, prizes, team limits, questions, and a scoring rubric. A separate open demo event is included for new submissions, while the imported fixture event keeps its original closed deadline.

## 01:32–01:55 — Participant workspace

Screen: `/participant/` (participant).

Participants see only their own event registrations, teams, and submission state. The dashboard calls out whether a deadline is open or closed. A participant can join a team, coordinate with teammates, and continue editing a draft before the deadline. The server enforces those boundaries, even if someone calls the API directly.

## 01:55–02:17 — Build a team

Screen: `/participant/events/evt_demo/team/` (team collaboration).

The team page handles collaboration for a specific event. A captain can invite teammates with a link, subject to the event's team capacity. Membership is checked when links are accepted, so an invitation cannot silently turn an organizer or judge into a participant. Team data stays within its event and workspace.

## 02:17–02:39 — Prepare a submission

Screen: `/participant/events/evt_demo/submission/` (submission wizard).

The submission wizard separates the work into basics, project details, links and media, and a final review. Teams can save drafts, add a cover image and other images, and supply a repository or live demo link. Final submission checks required fields and the server's deadline, not just the browser's controls.

## 02:39–02:58 — Judge workspace

Screen: `/judge/?event=evt_01` (judge).

Judges receive an assigned review queue rather than a list of every private submission. Assignment respects track scope and team conflicts. Each judge sees their own review progress and scores. They cannot create their own assignment, access a peer's ballot, or edit a project as a participant.

## 02:58–03:22 — Score an assigned project

Screen: `/judge/projects/<assigned-project-id>/` (private review).

In the review workspace, the assigned project sits beside the rubric. Judges enter criterion scores and submit their own review. The backend validates ranges, version conflicts, assignment, track scope, and judging dates. Peer reviews stay private during evaluation, preventing scores from influencing another judge's independent decision.

## 03:22–03:42 — Organizer workspace

Screen: `/organizer/` (organizer).

Organizers manage the events they own from a separate dashboard. They can create an event, set its submission window, configure tracks and prizes, and monitor incoming projects. This role has access to event operations, but cannot use the participant editing path to change a team's project content.

## 03:42–04:04 — Monitor the event

Screen: `/organizer/events/evt_01/` (event operations).

The event overview brings together submissions, judges, schedule, and progress. From here, an organizer can inspect the project list, eligibility decisions, judge coverage, audit history, and scoring preview. The demo fixture provides forty synthetic submissions so the workflow is meaningful even before anyone creates a new project.

## 04:04–04:28 — Manage judge coverage

Screen: `/organizer/events/evt_01/judges/` (assignments).

Judge management supports invitations, scoped tracks, conflicts, and assignment coverage. Automatic assignment balances work across eligible judges and reports shortages instead of hiding them. Manual assignment is checked against the same event, track, and team rules. Reviewers cannot simply opt into a project that was never assigned to them.

## 04:28–04:50 — Review results before publishing

Screen: `/organizer/events/evt_01/results/` (scoring).

The results preview ranks projects within their tracks. Raw scores use the weighted rubric; an optional adjustment estimates judge severity only when the shared-review evidence supports it. Ties remain ties, and unreviewed projects have no invented score. Organizers inspect the preview before publication freezes a reproducible result snapshot.

## 04:50–05:16 — Open source and verifiable

Screen: `/projects/` (wrap-up).

FairPanel runs locally with Docker Compose and keeps its database and uploaded files in persistent volumes. The official hackathon checker passes all seven included checks, covering the public gallery, deadline enforcement, private judge access, and CSV export. The repository includes tests, architecture notes, the scoring method, and the full source code.
