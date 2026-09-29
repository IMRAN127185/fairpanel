# FairPanel — complete backend implementation prompt

Copy everything below the divider into your coding tool. This is a proposed implementation contract, not additional official hackathon rules. It matches FAIRPANEL-UI-PROMPT.md. Implement the real T1 workflow before extending to T2.

---

Act as a senior backend engineer. Implement the backend for FairPanel, an open-source, self-hosted hackathon submission and judging portal. Produce working code, migrations, fixtures integration, tests, Docker configuration, and documentation. Continue through integration and verification; do not stop at a plan or scaffold.

Read repository instructions and inspect existing code first. Preserve the frontend's routes, template context, CSS, and shared API contract. Complete one vertical workflow at a time. Do not claim a feature works before verifying it. Do not deploy publicly or send external emails/messages as part of implementation.

## 1. Scope and architecture

Target complete T1, then complete T2. The proposed extra differentiator is an organizer-only Results Review page with raw versus adjusted rankings, coverage warnings, duplicate flags, and recorded publication decisions. Defer voting, comments, certificates, webhooks, embedding, pairwise judging, and AI evaluation.

Use a supported Django version, server-rendered templates, vanilla browser JS, and SQLite for the small single-instance baseline. Use ordinary Django migrations and ORM relationships; retain portability to PostgreSQL. Add Django REST Framework only if it simplifies the existing codebase; it is not required. No hosted authentication/database, required Redis/Celery, cloud API, or paid service.

Organize a modular monolith: accounts, events, teams, projects, judging, audit. Put business rules in reusable services called by HTML and API views. Use explicit serializers/response projections so public pages cannot leak internal model fields. Do not create different permission behavior for HTML and API routes.

Serve on localhost:8080 using Docker Compose. Persist database and local uploads in volumes. At container startup apply migrations, idempotently seed the bundled official fixture data in demo mode, then start the server. Do not download data, packages, fonts, or secrets at runtime. Bundle static assets. Missing decorative video or fonts must not impair the workflow.

Distinguish an internet-connected image build from offline runtime. Document required prebuilt images and provide an image export/import path if fully disconnected installation is needed. Never claim a clean disconnected laptop can pull an image. Verify the loaded-image startup path with network access unavailable.

## 2. Domain model and invariants

Use opaque string IDs and ISO-8601 UTC timestamps. Add indexed foreign keys, appropriate unique/check constraints, and explicit object ownership. Support exactly three user-facing workspaces with event-specific roles: organizer, judge, participant. A user may participate in one event and judge another, but has only one operational role within a given event. Visitors remain public readers and platform admin remains a separate maintenance privilege.

Models:
- User: Django user, unique normalized email, display name, hashed password.
- Event: organizer owner, name/description, timezone, registration/submission/judging dates, status, team capacity, minimum review coverage, gallery policy, publication metadata.
- EventMembership: user, event, role (participant/judge/organizer), unique on user/event. Reject conflicting role grants and invitation acceptance within the same event. Do not silently convert memberships or combine role permissions. Any future role reassignment needs a separately designed, audited migration policy protecting existing submissions and ballots; omit that feature from this scope.
- WorkspaceSettings: user, workspace_type (organizer/judge/participant), allowlisted preferences/profile fields, version; unique on user/workspace_type. Settings belong to the authenticated user. Judge expertise is descriptive and grants no permissions. Event configuration remains on Event/Rubric/etc., and global identity/password/session data remains on User/session models.
- Track and Prize: event-scoped configuration.
- CustomQuestion: event, stable key, label, type, required, choices, order; validate answers server-side.
- Team and TeamMembership: event, captain, name, capacity, members. Prevent a participant joining multiple teams in one event unless a documented event policy permits it. Captain is a member.
- Invitation: event/team or judge scope, hashed random token, intended role/email if applicable, creator, expiry, usage limit, revoked_at. Token grants only its recorded scope.
- Project: event/team/track, required submission fields, draft/submitted status, eligibility state and reason, submitted_at, version. Keep lifecycle status separate from eligibility and result publication.
- ProjectMedia: local image file, type/size metadata, ownership, ordering.
- Rubric and Criterion: version, event, scale and weight, guidance. Weights nonnegative with positive total; scales valid. Freeze rubric after first submitted review.
- JudgeTrackScope; Assignment: event/project/judge, assigned_at, state, conflict reason. Unique judge/project assignment; event and track consistency enforced.
- Review and CriterionScore: one review per assignment, draft/submitted state, rubric version, numeric scores, feedback, revision/version. Persist edits and audit meaningful submissions/changes.
- ResultSnapshot and ResultRow: immutable publication revision, source/input fingerprint, algorithm version/parameters, ranking method, rows, actor/time, warnings acknowledged.
- AuditEvent: actor, event, target, action, server timestamp, safe before/after data and reason. Append-only through application code; do not claim tamper-proof storage.

Public project fields: title, tagline, long description, thumbnail, ordered image gallery, hosted demo video URL, repository URL, live URL, tech tags, track, team display names. Custom answers have an explicit visibility policy and default to private.

Do not enforce unique project titles or repository URLs. Preserve duplicate fixture records and flag suspected duplicates. Prevent accidental duplicate normal submissions with an explicit team/event rule in the submission service; provide a documented import path for official historical anomalies without removing them.

## 3. Authentication and authorization

Use real password authentication and Django cookie sessions. Browser writes require CSRF. HttpOnly sessions; SameSite=Lax; secure cookies under HTTPS. Rotate sessions on login, invalidate logout, validate return URLs, and rate-limit credential attempts. Public registration never accepts a client-supplied elevated role. Register users as participants; hosting can explicitly create an event owned by that user without granting privileges over existing events.

Registration creates an ordinary account; participant membership is established on joining an event. Host onboarding grants organizer membership only for a newly created owned event. Judge membership requires a valid invitation to that event. Never infer authorization from the selected login page, a requested role, a UI switch, a localStorage value, or a settings field.

Provide three login entry routes `/login/organizer/`, `/login/judge/`, `/login/participant/`, backed by the same authentication implementation. A requested workspace is a return destination hint, checked against server-side membership. Implement `/dashboard/` as an authorized destination resolver and `/workspaces/` as a chooser limited to existing authorized memberships. New accounts may see participant onboarding or create an event; never grant judge access to make a redirect succeed.

Use explicit event/resource scope for each request. Avoid a mutable session-wide active role/event that would affect all browser tabs. Requests from different tabs must remain independent. Event-specific APIs derive the role from membership in the target event. Cross-event lists filter by the route's workspace role. Settings endpoints derive ownership from the session user and workspace type from the server route; reject unexpected identity, role, scope, or event-policy fields.

Require a membership in at least one corresponding event to use organizer/judge settings; ordinary registered accounts can use participant settings for onboarding. Keep each workspace's settings row independent. Provide a clearly separate shared account-security flow for password/session changes, with current-password reauthentication, CSRF, hashed passwords, and revocation of other sessions on password change.

Visitors read only public events, submitted eligible gallery projects, public statistics, and published result snapshots. Participants mutate only their team's allowed records. Judges see their assignments and their own scores within their authorized event/track; deny peer ballots, aggregates, organizer exports, and private material from other tracks. Public project descriptions can remain visible as public content. Organizers access only events they manage. Admin has platform-level access, audited for consequential actions.

Organizers may configure their event, manage assignments, inspect authorized ballots, and publish results. They cannot use review-write endpoints to change a judge's score or impersonate a judge. Organizers cannot edit participant-authored project content; eligibility decisions are separate audited actions. Judges alone author their own reviews, and team members alone edit their authorized team submissions. Admin maintenance must not silently rewrite authorship or bypass ballot immutability. Shared public pages and published results are deliberate read-only overlap, not a permission leak.

Apply authorization at every query, detail endpoint, mutation, export, upload, and template context. Prevent direct-object-reference attacks by changing IDs. Do not use UI visibility as protection. Write explicit negative tests.

For checker compatibility, peer-score requests by a different judge return 403, and participant requests to judge-score endpoints return 403. Unauthenticated API requests return 401 rather than an HTML login redirect. Browser pages may redirect to login.

Demo-only seed credentials and role headers must work through the ordinary authentication/authorization path, not a bypass. Prefer actual authenticated demo sessions printed by an explicit demo-seeding command. Scope them to localhost evaluation, avoid logging real session tokens outside demo mode, and do not commit production credentials.

## 4. Workflow rules

Events: validate ordered submission and judging windows; represent time in UTC internally. Organizer date changes require an audit entry. Publishing locks the included judging data against silent modification.

Teams: create/join/invite/revoke/accept with expiry, capacity, event membership checks, and race-safe acceptance. A copied invitation must resolve to an actual acceptance page. Offline invitations can be distributed by copying a link; optional delivery must not require SMTP. Never actually contact people during development.

Submissions: allow incomplete drafts. Validate all required fields, custom answers, ownership, track, and dates on final submission. At `now >= submissions_close`, reject project creation, finalization, edits to submitted projects, and media/answer changes with `deadline_passed`. Preserve fixture deadline exactly. Use transactions and compare-and-swap version checks so stale edits return 409. Confirm valid open-window submissions work; do not pass the deadline checker simply because all requests fail validation or CSRF.

Uploads: local storage, size/count limits, approved raster formats verified by decoder, generated filenames, ownership checks, safe serving headers. No arbitrary filesystem paths or server-side URL fetching. Validate external links as HTTP(S), render descriptions safely, and do not execute imported markup. Keep repository/video references as links that may be unavailable offline; core operations must remain usable.

Assignments: support manual batches and deterministic balanced assignment among eligible track judges. Exclude team members and recorded conflicts. Target an organizer-configurable count of reviewers, minimize workload imbalance, and introduce overlapping reviews where feasible for normalization. Use a reproducible seed and record it. Report insufficient judge capacity or disconnected coverage; never silently assign an unauthorized judge. Re-running assignment does not duplicate pairs or discard completed reviews.

Reviews: incomplete draft saves permitted; submitted reviews require every criterion, valid scales, current rubric, active assignment, and judging window. Review submission is atomic. Own submitted reviews may be revised during the window with version checks and audit history; lock after the judging close or publication. Missing reviews are absent evidence, never zero scores. Assignment conflict reports suspend scoring until organizer resolution.

Publication: organizer previews results, resolves eligibility, reviews coverage/method warnings, chooses raw or adjusted ranking, then publishes a frozen snapshot. Require an input fingerprint (`preview_version`) and reject stale publication attempts with 409. An explicit revision creates a new snapshot and audit entry; never silently overwrite published results. Only snapshot-safe fields are public; ballots and judge identities remain private.

## 5. Scoring and conservative normalization

Keep scoring deterministic, isolated from HTTP code, and thoroughly documented. Use criterion weights normalized by their sum. Convert each criterion score from its configured range to [0,1], take the weighted sum, and report 0–100. All submitted complete reviews count equally in the raw project mean. Do not round until display/export boundaries. Rank only within the declared comparable pool; default to per-track rankings.

Implement a transparent, modest adjustment rather than claim guaranteed fairness. Proposed method `overlap_bias_v1`:

1. Within the same event/track/rubric version, compute a judge's weighted score for each reviewed project.
2. For each of that judge's projects with at least one other eligible reviewer, compute the difference between their score and the mean of the other reviewers' scores for that project.
3. Average those differences to obtain a severity estimate. Shrink it toward zero by `n_overlap / (n_overlap + 5)`. The constant 5 is a documented conservative heuristic, not a fitted or proven optimum.
4. Apply the correction only with at least three overlapping reviewed projects, a connected comparison component, and nonconstant judge scores. Subtract the estimated severity from each affected review, then average the adjusted reviews for each project.
5. Judges lacking this support retain their raw scores in the adjusted calculation and receive an `uncalibrated` flag. Constant scorers are flagged for organizer review, never automatically discarded or accused of abuse. Explain mixed calibrated/uncalibrated results explicitly.
6. Do not clip internal adjusted values, since clipping can change ranks; explain that the adjusted index can extend beyond the raw 0–100 scale. Expose both values with labels.
7. Do not present adjusted ranks across disconnected comparison components as comparable. If the requested ranking pool is disconnected, provide raw ranks and a warning, set adjusted ranking unavailable, and require a different policy or more overlap before selecting adjusted publication.

Document assumptions: comparable rubrics, sufficient shared projects, relatively stable additive severity, and the limitations of sparse/nonrandom assignments. The method does not solve collusion, differing judge tastes, or selection bias. Do not describe ranking changes on fixtures as proof of true fairness.

Provide deterministic synthetic cases with known injected judge offsets and shared projects, demonstrating behavior and limitations; retain fixture before/after rankings separately. Test constant scorers, single reviewer, no reviews, disconnected pools, sparse overlap, unequal coverage, ties, identical inputs, and invalid weights. No NaN/infinite results. Preserve true ties; use stable IDs for display order only, not to invent a winner.

`JUDGING.md` must explain assignment, formula, adjustment, fallback, tie policy, publication, and limitations with a worked numerical example. If this method cannot be implemented and defended correctly within available time, ship raw judging with explicit normalization-unfinished status and do not claim complete T2.

## 6. Shared HTTP contract

Prefix `/api/v1`; same-origin cookie sessions; browser writes send `X-CSRFToken`. JSON uses snake_case and opaque string IDs. Lists are paginated with bounded page_size.

Success: `{"data": <object-or-array>, "meta": {"page":1,"page_size":20,"total":40}}`; meta optional outside lists. Error: `{"error":{"code":"deadline_passed","message":"Submissions are closed.","fields":{}}}`. Statuses: 401 unauthenticated; 403 forbidden; 404 missing/invisible object except required isolation probes; 409 stale version/state; 422 validation; 429 rate limit. Avoid stack traces in responses.

Resource vocabulary, matching the UI:
- Event: id,name,description,timezone,submissions_open,submissions_close,judging_open,judging_close,status,tracks,prizes,custom_questions,rubric_version,results_published_at.
- Team: id,event_id,name,captain_id,members,max_members.
- Project: id,event_id,team_id,track_id,title,tagline,description,thumbnail_url,images,video_url,repo_url,live_url,tech_tags,custom_answers,status,eligibility,submitted_at,updated_at,version.
- Rubric: version,criteria [{id,name,description,min_score,max_score,weight}].
- Review: id,project_id,judge_id,rubric_version,criteria_scores,comment,status,version,updated_at.
- Organizer result: project_id,title,raw_score,adjusted_score,raw_rank,adjusted_rank,review_count,eligible_review_count,normalization_status,warnings,tied. Null adjusted fields are valid when unsupported. Public result projection is narrower.

Implement these routes, with role-scoped response fields:

```text
GET    /auth/csrf
POST   /auth/register
POST   /auth/login
POST   /auth/logout
GET    /auth/me
GET    /auth/workspaces
GET    /settings/organizer
PATCH  /settings/organizer
GET    /settings/judge
PATCH  /settings/judge
GET    /settings/participant
PATCH  /settings/participant
POST   /auth/password/change
GET    /auth/sessions
POST   /auth/sessions/revoke-others
GET    /public/stats
GET    /events
POST   /events
GET    /events/{id}
PATCH  /events/{id}
POST   /events/{id}/join
GET    /events/{id}/teams
POST   /events/{id}/teams
POST   /teams/{id}/invites
DELETE /team-invites/{id}
POST   /team-invites/accept
GET    /events/{id}/projects
POST   /events/{id}/projects
GET    /projects/{id}
PATCH  /projects/{id}
POST   /projects/{id}/submit
POST   /uploads
GET    /events/{id}/rubric
PUT    /events/{id}/rubric
POST   /events/{id}/judge-invites
POST   /judge-invites/accept
GET    /events/{id}/assignments
POST   /events/{id}/assignments
POST   /assignments/{id}/conflict
GET    /judge/assignments
GET    /judge/scores
GET    /judges/{id}/scores
PUT    /projects/{id}/review
POST   /projects/{id}/review/submit
GET    /events/{id}/progress
PATCH  /projects/{id}/eligibility
GET    /events/{id}/results/preview
POST   /events/{id}/results/publish
GET    /events/{id}/results
GET    /events/{id}/audit
GET    /events/{id}/exports/{kind}.csv
```

Write payloads: invitation accept `{token}`; project update `{...fields,version}`; project/review submission `{version}`; review save `{criteria_scores,comment,version}`; rubric `{criteria,version}`; eligibility `{eligibility,reason,version}`; assignments `{strategy:"balanced",reviews_per_project:3}` or `{strategy:"manual",pairs:[{judge_id,project_id}]}`; publication `{ranking_method:"raw"|"adjusted",preview_version,acknowledged_warnings:[],reason}`. For initial resources version starts at 1; a first review save can use version 0 to mean create-if-absent. Document exact create schemas with request/response examples.

`/auth/me` returns identity and authorized event memberships. `/auth/workspaces` returns only authorized role/event destinations. Settings PATCH payloads contain `version` and allowlisted workspace fields: display/timezone preferences for all; reviewer bio/expertise for judges; participant bio/skills for participants. Never accept permission-bearing fields. Reject stale settings versions with 409. Password change accepts `{current_password,new_password}`; revoke-other-sessions accepts `{current_password}`. Session lists expose safe metadata only, never cookies or tokens. Keep shared account security explicitly distinct from workspace settings.

Public stats count public events, registered teams where count disclosure is permitted, published gallery projects, and public tracks. They must not leak judges or private scores. Exports support teams, projects, assignments, reviews, results, and audit where implemented, with stable headers, proper escaping, and spreadsheet-formula injection protection. All sensitive exports require event-organizer access.

Publish an OpenAPI document for implemented endpoints if feasible, but do not claim the API bonus or T4 merely because a partial API exists. Health endpoints `/health/live` and `/health/ready` disclose no secrets.

## 7. HTML integration

Serve the companion frontend's public `/`, `/events/`, `/events/{id}/`, `/projects/`, `/projects/{id}/`, `/events/{id}/results/`, `/how-it-works/`, `/login/`, and `/register/` pages. Implement the three role-specific login entry routes, `/dashboard/` resolver, `/workspaces/` chooser, and separate workspace shells:
- Participant: `/participant/`, `/participant/settings/`, `/participant/events/{id}/team/`, `/participant/events/{id}/submission/`.
- Judge: `/judge/`, `/judge/settings/`, `/judge/projects/{id}/`.
- Organizer: `/organizer/`, `/organizer/settings/`, `/organizer/events/{id}/`, plus event settings/submissions/judges/results/audit subpages.

Authorize before redirecting the legacy `/events/{id}/team/` and `/events/{id}/submission/` routes to their participant equivalents. Do not render a mixed-role dashboard. Ensure all event navigation queries are scoped to the shell's required role. Shared Account Security may be linked from each settings page, clearly labeled as account-wide.

Provide invitation acceptance pages reached from copied links, and document their routes. Return safe, scoped template contexts. Initial public gallery HTML includes real project titles without requiring JavaScript execution. Keep forms usable with server-rendered errors. If frontend files already exist, wire them rather than replacing their design. If absent, provide functional minimal templates matching these routes and leave styling to the UI prompt.

## 8. Official fixtures and checker

Read the latest official materials before implementing assumptions:
- https://dogfoodhack.com/
- https://dogfoodhack.com/spec/
- https://dogfoodhack.com/spec/spec.md
- https://dogfoodhack.com/spec/fixtures.json
- https://dogfoodhack.com/spec/run.py

Download public fixture/checker files during development and bundle them unchanged. Never execute unrelated remote scripts. Inspect run.py before running the official checker against the local portal. Preserve source provenance and any supplied license notices.

Map fixture `summary` to tagline and `team`/`track` references to relationships. Preserve original IDs, timestamps, score values, and historical anomalies. Missing product fields use explicitly documented neutral defaults. Derive the seed rubric from actual criterion keys and validate score ranges. Report mapping assumptions. Do not fabricate reviews to repair incomplete batches or silently extend judge track permissions; inspect and document any conflicts in imported historical records.

Seed import is idempotent and must not reset user edits on every restart. Use import identifiers/checksums. Provide a separate explicit reset-demo command, with clear destructive labeling, rather than resetting automatically. Create an additional open demo event for new submissions without changing the official fixture event.

Generate `.dogfood.toml` using actual working demo headers and routes. Gallery is `/projects/`; submit points to the real fixture event project-creation route; judge_scores points to `/api/v1/judge/scores`; peer_scores points to the actual judge A detail route; csv_export points to the fixture event organizer export. A successful judge A request to peer_scores must return A's own scores while judge B receives 403. Do not invent a permanently forbidden probe-only endpoint.

Run the unmodified checker and save its real output to `acceptance-report.txt`. Inspect PASS/FAIL text, not only exit code. The inspected checker only covers seven T1/T2 checks and can exit zero despite failures; verify the downloaded version rather than assuming this forever. Test more than those seven probes. Never modify the checker, hardcode its project titles, or fabricate a report. If T3/T4 verification is still absent, document that limitation instead of changing the suite.

## 9. Meaningful verification

Test registration/login/session logout; role and object isolation; two distinct judge identities; unauthorized cross-event organizer access; invitation expiry/capacity; valid open submission; exact deadline boundary; post-deadline edits and uploads; custom-field validation; stale version conflicts; rubric locking; track-aware assignments and conflicts; complete/incomplete scoring; normalization edge cases; public response field leaks; CSV authorization/escaping; frozen result snapshots; repeated seed imports; persistence across restart.

Run an end-to-end event lifecycle with organizer, participant, judge A, judge B, and visitor sessions. Run official acceptance checks against the real HTTP app. Verify fresh-volume startup, repeat startup, and local operation without external network requests. Tests for deadline rejection must establish the same otherwise-valid request succeeds before the boundary.

Add isolation tests for all three workspace routes and settings endpoints: unauthorized login destination selection, role injection during registration/settings writes, organizer modification of judge ballots, participant changes to event configuration, judge changes to assignment scopes, conflicting same-event memberships, and cross-user settings access must fail. Verify different roles across two events work without combining permissions; requests in two tabs do not mutate each other's context; one workspace preference change leaves the others unchanged; revoked membership takes effect on the next request; account-wide security changes behave as labeled. Inspect HTML/JSON for private field leaks, not merely HTTP status.

Use database transactions and unique constraints for race-sensitive paths. On SQLite use optimistic updates/conditional writes where row-level locking is unavailable; do not assume select_for_update provides PostgreSQL-style protection. Record SQLite single-instance throughput limitations honestly.

## 10. Required handoff and completion order

Deliver Dockerfile, docker-compose.yml, pinned dependency file, .env.example, migrations, bundled official fixtures/checker, generated .dogfood.toml, actual acceptance report, LICENSE (MIT by default for original project code), README.md, ARCHITECTURE.md, DATA-MODEL.md, JUDGING.md, and a five-minute demo script. Document external asset/dependency licenses independently. Explain startup, demo roles, backups, data export, offline assumptions, limitations, and tier evidence. Do not claim a demo video exists unless one was actually recorded.

Build order:
1. Docker startup, schema, auth, official fixture import, public event/gallery.
2. Teams/invitations, full submission workflow, deadlines, permissions: verify T1.
3. Rubric, judge invitations/assignments, review workflow, progress and exports.
4. Defensible normalization, result review/publication, audit: verify T2.
5. Relevant tests, fresh-start verification, honest report/docs/demo script.

If a hard submission deadline is provided, reserve time for packaging and deliver the verified tier; do not prioritize speculative features over core correctness. Finish with what works, which commands/tests actually ran, known gaps, and the highest honestly completed tier. Do not publish a repository, deploy a site, or submit an entry unless separately requested.
