# FairPanel — complete UI implementation prompt

Copy everything below the divider into your coding tool. This is a proposed product specification, not additional official hackathon rules. It targets a complete T1 followed by T2; later-tier features are deliberately deferred.

---

Act as a senior product designer and frontend engineer. Implement FairPanel, an open-source, self-hosted hackathon submission and judging portal. Produce working code and integrate it with the backend contract below. Complete the work in phases; do not stop at a landing page, mockup, or implementation plan.

Read any repository instructions and existing code first. Preserve working backend behavior. If the companion backend is not implemented yet, create the templates, assets, and integration layer against the specified contract, document unavailable endpoints, and never represent mock behavior as working integration.

## 1. Product and implementation choices

The product has exactly three user-facing workspaces: Organizer, Judge, and Participant. Each has its own dashboard, navigation, settings, and permitted actions. Visitors browse public pages without a workspace; platform administration remains a separate maintenance interface. The main journey is event discovery → registration → team formation → project submission → judge assignment → scoring → organizer review → published results.

### Required separation of the three workspaces

Do not create one mixed dashboard with three role tabs. Use separate layouts and route families:

| Workspace | Home | Navigation | Settings |
|---|---|---|---|
| Organizer | `/organizer/` | My Events, Submissions, Judges & Assignments, Results, Audit, Settings | `/organizer/settings/`: organizer-specific display/timezone preferences; `/organizer/events/{id}/settings/`: event dates, tracks, prizes, questions, rubric, team limits, and publication policy |
| Judge | `/judge/` | Assigned Events, Review Queue, My Reviews, Settings | `/judge/settings/`: own reviewer bio, expertise tags, display/timezone preferences; expertise is descriptive and cannot grant track access |
| Participant | `/participant/` | My Events, My Team, My Submission, Published Results, Settings | `/participant/settings/`: own participant bio, skills, display/timezone preferences; team and submission edits remain in their event pages |

Settings pages expose only fields permitted for that workspace. Each may link to shared Account Security for password/session management, clearly labeled as applying to the whole account. Role-specific preferences never overwrite another workspace's preferences. Do not display controls for features that are not implemented.

Provide `/login/organizer/`, `/login/judge/`, and `/login/participant/` entry pages with consistent branding and role-specific copy. They use the same secure authentication system; choosing an entry page is a navigation choice, never a permission grant. `/login/` can offer the three entry choices. Participants can register and join events; organizers can create events they own; judges require a valid event invitation. Show a clear access/invitation message for a login without the required membership.

After login, route to the authorized workspace. `/dashboard/` is a redirect/resolver, not a fourth dashboard. A user with different roles in different events can use `/workspaces/` to choose only an already-authorized role/event. One account has one operational role per event. Show current workspace and selected event prominently. Workspace changes must warn about unsaved work, abort obsolete requests, clear private screen state, and load fresh data. Context lives in the current route/request so changing one browser tab does not change another tab's role or event.

Organizers configure and supervise their own events; judges independently author their own ballots; participants author their own team's submission. Organizers can inspect authorized ballots and manage assignments but cannot impersonate judges or edit their scores. Public galleries and published results remain intentionally shared. Keep private drafts, peer ballots, account settings, and event administration isolated.

Use Django templates, semantic HTML, CSS, and vanilla JavaScript. Do not introduce React, a separate frontend server, or a required Node build. Use Django template inheritance and partials. Put assets under `static/fairpanel/` and templates under `templates/fairpanel/`. The backend serves pages and same-origin `/api/v1/` endpoints on localhost:8080. The backend companion prompt defines the same routes and schemas.

Use server rendering for essential content, particularly gallery project titles. Use JavaScript for progressive enhancement, draft saves, filtering, and scoring interactions. Never embed secrets, private ballots, or private aggregates in public HTML or script data.

Build and verify T1 first, then T2. No community voting, comments, certificates, pairwise comparisons, AI scoring, blockchain, paid subscriptions, or fabricated analytics in this scope.

## 2. Landing page: closely follow these coordinates

Only `/` uses the cinematic single-viewport composition. Document title: `FairPanel — Every Project Deserves a Fair Review`.

Desktop landing body is black with a 100vh/100dvh composition. `.page` uses a centered flex column and padding `clamp(16px, 2.4vh, 28px) clamp(14px, 3vw, 32px)`. Its three regions are a nonshrinking header, flexible centered hero, and nonshrinking metric footer. Put content at z-index 1 over the video at z-index 0.

Avoid global overflow rules affecting the app. At short viewport heights, text zoom, or mobile landscape, allow natural vertical scrolling instead of clipping controls. Other pages always scroll normally.

Preserve these reference tokens:

```css
--bg: #000000;
--text: #ffffff;
--muted: #8e8e8e;
--nav-text: #2e2e2e;
--pill-dark: #28282a;
--sign-in-text: #c8c8c8;
--nav-shadow: 0 4px 14px rgba(0, 0, 0, 0.16);
--trust-bg: #28282a;
--trust-border: rgba(255, 255, 255, 0.4);
--trust-text: #c4c2c3;
--font-sans: "Inter", "Segoe UI", system-ui, sans-serif;
--font-display: "BubbledotICG-FinePos", "Geist Pixel Circle", monospace;
```

Background: absolute inset 0, full-size cover video, muted, loop, playsinline, pointer-events none, enclosed by a black overflow-hidden `.bg`. Add a static dark overlay only as necessary for text contrast. The exact reference video is:

`https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260809_012548_ef22562c-c0ae-4816-ad9d-f8922af4e6a7.mp4`

Support that URL as an optional online enhancement, never a runtime prerequisite. Default to a bundled, authorized local video/poster if available; otherwise show an elegant black/CSS background. Do not download remote media merely to bypass display restrictions. Do not invent an asset or claim it exists. Reduced-motion and data-saving preferences use the static background. Autoplay denial must leave readable, functional content.

Typography references:

- Inter 400/500/600: `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap`.
- BubbledotICG-FinePos: `https://db.onlinewebfonts.com/c/8cb707a9b8a73f8a7403336b861c3074?family=BubbledotICG-FinePos`.
- Optional supplied local fallback: `fonts/GeistPixel-Circle.woff2`, weight 400, font-display swap.

Preserve Bubbledot as the optional online display face; do not fetch or redistribute its font files. Use a supplied licensed local Geist font or monospace fallback offline. Use local licensed Inter if provided, otherwise system sans. Do not require a CDN to render. UI icons should be small inline SVGs with accessible labels where needed; do not add a Font Awesome dependency solely for decoration.

### Header

Centered desktop row, max-width 720px, gap `clamp(18px, 2.8vw, 28px)`.

- Logo: white circular link sized `clamp(40px, 4.4vw, 46px)`, soft nav shadow. Use supplied `assets/logo.webp` if present; otherwise create a simple original inline SVG circular FairPanel mark. The mark occupies 72% of its circle. Give the link an accessible name. Hover scale 1.04.
- Navigation: white pill, height `clamp(44px, 5.2vw, 48px)`, max-width 430px, flex 1, padding 4px 8px, radius 999px. Links: Home `/`, Events `/events/`, Projects `/projects/`, How it works `/how-it-works/`. Font 500, `clamp(13px, 1.4vw, 15px)`, letter-spacing -0.01em. Default opacity .5, hover .75, active 1. Active indicator: three 3px black dots, spaced 5px, bottom 5px. Include aria-current.
- Sign in: dark pill to `/login/`, same height, #c8c8c8 text. Hover #323234, white text, translateY(-1px). Authenticated users see Dashboard instead.
- Entrance: slideDown .7s cubic-bezier(.22,1,.36,1), opacity 0 and translateY(-18px) to final.

### Hero

Centered column, max-width 900px. No hero cards or dashboard screenshot replacing the video composition.

Replace enterprise endorsements with truthful product language. Use three small generic inline SVG symbols for teams, reviews, and results in overlapping rings. Do not show Microsoft/Amazon/Google as customers or claim thousands of users.

Trust row size `clamp(36px, 4.5vw, 42px)`, 34px at ≤420px. Dark outer rings with a 1px rgba(255,255,255,.4) border, 5px padding, white inner circles, black symbols. Later rings overlap by -.42 of ring size. Pill uses the same height, negative overlap, and .58 ring-size left padding. Text: `Open source. Self-hosted. Transparent.` Margin below: `clamp(16px, 2.5vh, 26px)`.

Headline, two block spans:

```
Great Ideas.
Fairly Judged.
```

Display face, solid white, no gradient/shimmer/LED scan. Size `clamp(28px, 6.2vw, 80px)`, tracking -.04em, line-height 1.12. At ≤720px tracking -.08em and line-height 1.05; at ≤420px -.09em and 1.04. Keep these short lines intact when space permits, but never clip at increased text size. Each line fades from opacity 0 and translateY(14px) over .85s, delayed .12s and .3s. Do not animate the parent twice.

Subheading: `Bring your hackathon from first submission to final results—with private reviews and judging you can explain.` Max-width min(500px,92%), font size `clamp(calc(13.5px + 2pt), calc(1.55vw + 2pt), calc(16.5px + 2pt))`, #d0d0d0 at .8 opacity, line-height 1.55, delay .28s.

Primary CTA: `Explore Events` → `/events/`. White pill, black text, weight 600, font size `clamp(13.5px,1.5vw,14.5px)`, padding `clamp(11px,1.6vh,13px) clamp(22px,3vw,28px)`. Shadow `0 0 0 1px rgba(255,255,255,.15), 0 0 22px rgba(255,255,255,.32), 0 0 44px rgba(255,255,255,.12)`. Hover translateY(-2px) scale(1.02). Entrance revealPulse delayed .4s. A subdued secondary text link `Host an event` leads to registration or the authorized organizer setup flow.

### Footer metrics

Four columns, max-width 920px; two columns at ≤720px. Show public API-derived counts: Events, Teams, Published Projects, Tracks. Never expose judge counts or private progress through these statistics. If showing fixture-only counts, label the region `Sample event data`. No fabricated uptime, latency, usage, or performance claims.

Symbols use display face at `clamp(22px,3vw,33px)`. Values use sans at `clamp(18px,2.2vw,26px)`, tracking -.025em and tabular numerals. Labels #8e8e8e at `clamp(11px,1.2vw,12.5px)`. Stagger .5/.58/.66/.74s. Optional count-up uses easeOutCubic over 1500+i*80ms, offset 480+i*90ms, once via IntersectionObserver threshold .25. On failure display a clear unavailable state; on reduced motion show final values immediately.

### Mobile and motion

At ≤720px hide desktop nav/sign-in. Header is space-between with 48px logo and 48px dark circular menu button; three white 18×1.5px bars become a black X on white when open. Overlay is fixed rgba(0,0,0,.62), backdrop blur 6px. White menu sheet sits beneath the header, radius 28px, padding 22px 18px 20px, shadow 0 20px 60px rgba(0,0,0,.45). Same route links plus full-width sign-in.

Maintain aria-expanded/controls, focus trap, inert background while open, initial focus, and focus restoration. Close on overlay, Escape, link activation, and resizing above 720px. Prevent scroll only while this overlay is open.

Shared reveal: opacity 0, translateY(22px) scale(.98), blur(6px) → final over .85s cubic-bezier(.22,1,.36,1). Use progressive animation classes so failed JS cannot leave content invisible. Reduced motion disables transitions, count-ups, and video animation. Tighten spacing at heights ≤700px without hiding content.

## 3. Extend the visual language to the application

Use a quiet near-black application background, #121214 surfaces, subtle white borders, white primary text, and high-contrast secondary text. Display type is reserved for page titles and small decorative symbols. Body copy, form fields, tables, and scores use sans. Status colors must include text/icons and meet contrast requirements.

Desktop app shell: roughly 224px sidebar, 64px top bar, content max-width 1440px, spacing 8/12/16/24/32. Mobile sidebar becomes a drawer; forms become one column. Use restrained rounded rectangles for functional panels and pills for actions. Never place animated video beneath forms or scoring tables.

Provide visible focus, semantic landmarks, skip link, labeled inputs, inline errors, error summary, confirmation for destructive actions, appropriate empty/loading/error states, disabled reasons, and retry controls. Use at least 44px touch targets. Toasts supplement persistent status; they do not replace it.

## 4. Pages and complete interactions

Public:
- `/events/`: event list with status, dates/timezone, tracks, and links.
- `/events/{id}/`: overview, rules, schedule, prizes, registration/team CTA, gallery link, and results link only when published.
- `/projects/?event={id}`: server-rendered project gallery, search, track/tag filters, pagination with preserved query parameters, meaningful empty state.
- `/projects/{id}/`: public submitted project description, thumbnail/media, team display names, track/tags, safe repository/live/video links. No private feedback or email addresses.
- `/events/{id}/results/`: published snapshot only; show not-published state before release without leaking ranks.
- `/how-it-works/`: concise participant/organizer workflow; no invented customer claims.
- `/login/`, `/register/`: proper field validation, safe return URL, invalid credentials states.

Participant:
- `/participant/`: event memberships, team, project state, next action, deadline with local timezone and UTC tooltip.
- `/participant/events/{id}/team/`: create team, member list, capacity, generate/copy invitation, accept invite with confirmation, revoke invitation as captain.
- `/participant/events/{id}/submission/`: Basics → Details → Links and media → Review. Include title, tagline, long description, thumbnail, image gallery, demo video URL, repository URL, live URL, tech tags, track, and organizer custom answers. Preserve entered values across step changes and errors. The earlier `/events/{id}/team/` and `/events/{id}/submission/` paths redirect to these participant routes after authorization.
- Explicit Save draft and Submit actions. Save state reflects server confirmation. Use optimistic version numbers to detect conflicting edits. Warn about unsaved changes. Allow editing an already submitted project before deadline without accidentally hiding it. Lock editing afterward and show the server's explanation. No simulated success.

Judge:
- `/judge/`: event picker and assigned review list, pending/draft/submitted statuses, own completion count.
- `/judge/projects/{id}/`: desktop columns approximately 230px / flexible / 360px for queue/project/rubric. Stack on small screens. Present rubric guidance and weights, accessible numeric controls, feedback, Save draft, Submit review, and Next project.
- Never display peers' scores, rankings, organizer-only warnings, or reviews from another track. Explain access denial without exposing the denied data. Conflict-of-interest action records a reason and requests organizer reassignment.

Organizer:
- `/organizer/`: authorized events, create event action.
- `/organizer/events/{id}/`: event overview and actionable counts.
- `/organizer/events/{id}/settings/`: dates, timezone, tracks, prizes, custom questions, rubric criteria/weights. Lock rubric after scoring begins.
- `/organizer/events/{id}/submissions/`: list, filters, eligibility review, duplicate warnings, detail, export. Exclusions require reasons.
- `/organizer/events/{id}/judges/`: invitations, track scopes, assignments, missing coverage, balanced assignment action, conflict reports, progress updated with modest polling paused when tab is hidden.
- `/organizer/events/{id}/results/`: raw and adjusted rank/score, review count, normalization status, exclusion reason, tie marker, warnings. Explicit rank-method selector and publish confirmation. Show frozen publication revision afterward.
- `/organizer/events/{id}/audit/`: filterable actor/action/time/target/reason history, safe before/after summaries, CSV download.
- Platform admin uses Django admin for platform management; event organizers must not gain unrestricted staff access.

## 5. Shared integration contract — use exactly this vocabulary

IDs are opaque strings. Dates are ISO-8601 UTC, displayed in the user's local timezone. JSON fields are snake_case. Same-origin cookie sessions; browser writes include Django CSRF token in `X-CSRFToken`. Do not store authentication tokens in localStorage.

Success: `{"data": <object-or-array>, "meta": {"page":1,"page_size":20,"total":40}}`; meta is optional outside lists. Error: `{"error":{"code":"deadline_passed","message":"Submissions are closed.","fields":{}}}`. Use 401 unauthenticated, 403 forbidden, 404 missing/invisible resource, 409 version/state conflict, 422 validation, 429 rate limited. Project/judge isolation probes specifically need 401/403 as defined by the backend.

Key resources:
- Event: id, name, description, timezone, submissions_open, submissions_close, judging_open, judging_close, status, tracks, prizes, custom_questions, rubric_version, results_published_at.
- Team: id, event_id, name, captain_id, members, max_members.
- Project: id, event_id, team_id, track_id, title, tagline, description, thumbnail_url, images, video_url, repo_url, live_url, tech_tags, custom_answers, status, eligibility, submitted_at, updated_at, version. Private fields are omitted from public responses.
- Rubric: version, criteria [{id,name,description,min_score,max_score,weight}].
- Review: id, project_id, judge_id, rubric_version, criteria_scores (criterion-ID to numeric score), comment, status, version, updated_at.
- Result: project_id, title, raw_score, adjusted_score, raw_rank, adjusted_rank, review_count, eligible_review_count, normalization_status, warnings, tied. Rich result rows are organizer-only.

Endpoint groups (prefix `/api/v1`):
- `GET /auth/csrf`, `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`.
- `GET /auth/workspaces`; `GET,PATCH /settings/organizer`; `GET,PATCH /settings/judge`; `GET,PATCH /settings/participant`. `/auth/me` returns identity plus authorized event memberships; `/auth/workspaces` returns authorized role/event destinations only. Settings payloads are allowlisted profile/preferences fields with `version`, never role, scope, assignment, or event-policy fields. Account security uses `POST /auth/password/change`, `GET /auth/sessions`, and `POST /auth/sessions/revoke-others`, with reauthentication for sensitive changes.
- `GET /public/stats`; `GET,POST /events`; `GET,PATCH /events/{id}`; `POST /events/{id}/join`.
- `GET,POST /events/{id}/teams`; `POST /teams/{id}/invites`; `DELETE /team-invites/{id}`; `POST /team-invites/accept`.
- `GET,POST /events/{id}/projects`; `GET,PATCH /projects/{id}`; `POST /projects/{id}/submit`; `POST /uploads`.
- `GET,PUT /events/{id}/rubric`; `POST /events/{id}/judge-invites`; `POST /judge-invites/accept`; `GET,POST /events/{id}/assignments`; `POST /assignments/{id}/conflict`.
- `GET /judge/assignments`; `GET /judge/scores`; `GET /judges/{id}/scores`; `PUT /projects/{id}/review`; `POST /projects/{id}/review/submit`.
- `GET /events/{id}/progress`; `PATCH /projects/{id}/eligibility`; `GET /events/{id}/results/preview`; `POST /events/{id}/results/publish`; `GET /events/{id}/results`; `GET /events/{id}/audit`; `GET /events/{id}/exports/{kind}.csv`.

Every UI write sends explicit data: invitation accept `{token}`, save project `{...fields,version}`, submit `{version}`, review `{criteria_scores,comment,version}`, rubric `{criteria,version}`, eligibility `{eligibility,reason,version}`, assignment `{strategy:"balanced",reviews_per_project:3}` or `{strategy:"manual",pairs:[{judge_id,project_id}]}`, publication `{ranking_method:"raw"|"adjusted",preview_version,acknowledged_warnings:[],reason}`. Backend validates all values independently.

Use one small `api.js` wrapper for CSRF, fetch, errors, aborting stale searches, and response parsing. Render fetched text safely. Refetch server-confirmed state after mutations. Do not derive permissions solely from displayed role labels.

## 6. Verification and handoff

Check 1440×900, 1024×768, 390×844, 360×640, landscape, keyboard-only use, 200% zoom, reduced motion, and unavailable video/fonts. Verify contrast on the actual background. If browser tools are available, capture screenshots and fix visible clipping, overlap, and unreadable text; otherwise explicitly report that visual verification was not run.

Verify the public gallery initial HTTP body contains fixture titles, real login/logout, draft save/reload, team invitation acceptance, submission before deadline and denial afterward, judge save/resume, forbidden score access, organizer export, and unpublished/published result behavior. Run available relevant tests; do not invent passing results.

Also verify all three login destinations, independent workspace settings, forbidden direct navigation/API calls, absence of other roles' controls/private data in initial HTML, two tabs using different authorized events, unsaved-work protection during workspace changes, and rejected attempts to gain a role through login/settings payloads. Judge settings cannot modify assignment scopes; participant settings cannot change event deadlines; organizer settings cannot overwrite a judge ballot.

Finish with a concise list of implemented screens, actual integration status, tests/screenshots completed, missing assets, and unfinished features. Update README with an accurate UI scope. Do not claim T2 completion from appearance alone.
