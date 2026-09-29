"""Record a narrated FairPanel walkthrough from the running local portal.

Optional recording dependencies: playwright, Pillow, and imageio-ffmpeg.
Run after seeding the demo and starting the server on 127.0.0.1:8080.
"""

import os
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
import imageio_ffmpeg


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "demo_work"
FRAMES = WORK / "frames"
AUDIO = WORK / "audio"
OUTPUT = ROOT / "demo" / "fairpanel-demo.mp4"
BASE = "http://127.0.0.1:8080"
PASSWORD = os.environ.get("FAIRPANEL_DEMO_PASSWORD", "DemoPassword2026!")
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
FONT = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")

SCENES = [
    {
        "title": "FairPanel: every project deserves a fair review",
        "label": "INTRODUCTION",
        "url": "/",
        "role": None,
        "narration": "Welcome to FairPanel, a self-hosted hackathon portal for three distinct groups: organizers, participants, and judges. The public site introduces events and projects, while each role gets its own workspace. This walkthrough uses the bundled synthetic data and a live Docker container. It shows the submission journey, private judging, and transparent result review.",
    },
    {
        "title": "Explore the public project gallery",
        "label": "PUBLIC SHOWCASE",
        "url": "/projects/",
        "role": None,
        "narration": "The project gallery is open to everyone. Teams appear as visual cards with a title, short description, event, and track. Visitors can search by project or team, filter by event and track, and sort the entries. Submitted, eligible projects are visible here; private drafts do not appear in the public showcase.",
    },
    {
        "title": "Read a project story",
        "label": "PROJECT DETAIL",
        "url": "/projects/prj_01/",
        "role": None,
        "narration": "Opening a project shows its longer description, team, technologies, and any repository, live demo, or video links supplied by its creators. Teams can add a cover image and more gallery images when they submit. Organizer-only answers stay private. This lets the public appreciate the work without exposing internal judging material.",
    },
    {
        "title": "Discover events and deadlines",
        "label": "PUBLIC EVENTS",
        "url": "/events/",
        "role": None,
        "narration": "The events area gives prospective participants a place to discover active hackathons and see key dates. Each event can define tracks, prizes, team limits, questions, and a scoring rubric. A separate open demo event is included for new submissions, while the imported fixture event keeps its original closed deadline.",
    },
    {
        "title": "Participant workspace",
        "label": "PARTICIPANT",
        "url": "/participant/",
        "role": "participant",
        "narration": "Participants see only their own event registrations, teams, and submission state. The dashboard calls out whether a deadline is open or closed. A participant can join a team, coordinate with teammates, and continue editing a draft before the deadline. The server enforces those boundaries, even if someone calls the API directly.",
    },
    {
        "title": "Build a team",
        "label": "TEAM COLLABORATION",
        "url": "/participant/events/evt_demo/team/",
        "role": "participant",
        "narration": "The team page handles collaboration for a specific event. A captain can invite teammates with a link, subject to the event's team capacity. Membership is checked when links are accepted, so an invitation cannot silently turn an organizer or judge into a participant. Team data stays within its event and workspace.",
    },
    {
        "title": "Prepare a submission",
        "label": "SUBMISSION WIZARD",
        "url": "/participant/events/evt_demo/submission/",
        "role": "participant",
        "narration": "The submission wizard separates the work into basics, project details, links and media, and a final review. Teams can save drafts, add a cover image and other images, and supply a repository or live demo link. Final submission checks required fields and the server's deadline, not just the browser's controls.",
    },
    {
        "title": "Judge workspace",
        "label": "JUDGE",
        "url": "/judge/?event=evt_01",
        "role": "judge",
        "narration": "Judges receive an assigned review queue rather than a list of every private submission. Assignment respects track scope and team conflicts. Each judge sees their own review progress and scores. They cannot create their own assignment, access a peer's ballot, or edit a project as a participant.",
    },
    {
        "title": "Score an assigned project",
        "label": "PRIVATE REVIEW",
        "url": "__judge_review__",
        "role": "judge",
        "narration": "In the review workspace, the assigned project sits beside the rubric. Judges enter criterion scores and submit their own review. The backend validates ranges, version conflicts, assignment, track scope, and judging dates. Peer reviews stay private during evaluation, preventing scores from influencing another judge's independent decision.",
    },
    {
        "title": "Organizer workspace",
        "label": "ORGANIZER",
        "url": "/organizer/",
        "role": "organizer",
        "narration": "Organizers manage the events they own from a separate dashboard. They can create an event, set its submission window, configure tracks and prizes, and monitor incoming projects. This role has access to event operations, but cannot use the participant editing path to change a team's project content.",
    },
    {
        "title": "Monitor the event",
        "label": "EVENT OPERATIONS",
        "url": "/organizer/events/evt_01/",
        "role": "organizer",
        "narration": "The event overview brings together submissions, judges, schedule, and progress. From here, an organizer can inspect the project list, eligibility decisions, judge coverage, audit history, and scoring preview. The demo fixture provides forty synthetic submissions so the workflow is meaningful even before anyone creates a new project.",
    },
    {
        "title": "Manage judge coverage",
        "label": "ASSIGNMENTS",
        "url": "/organizer/events/evt_01/judges/",
        "role": "organizer",
        "narration": "Judge management supports invitations, scoped tracks, conflicts, and assignment coverage. Automatic assignment balances work across eligible judges and reports shortages instead of hiding them. Manual assignment is checked against the same event, track, and team rules. Reviewers cannot simply opt into a project that was never assigned to them.",
    },
    {
        "title": "Review results before publishing",
        "label": "SCORING",
        "url": "/organizer/events/evt_01/results/",
        "role": "organizer",
        "narration": "The results preview ranks projects within their tracks. Raw scores use the weighted rubric; an optional adjustment estimates judge severity only when the shared-review evidence supports it. Ties remain ties, and unreviewed projects have no invented score. Organizers inspect the preview before publication freezes a reproducible result snapshot.",
    },
    {
        "title": "Open source and verifiable",
        "label": "WRAP-UP",
        "url": "/projects/",
        "role": None,
        "narration": "FairPanel runs locally with Docker Compose and keeps its database and uploaded files in persistent volumes. The official hackathon checker passes all seven included checks, covering the public gallery, deadline enforcement, private judge access, and CSV export. The repository includes tests, architecture notes, the scoring method, and the full source code.",
    },
]


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)


def render_frame(source, title, label, number):
    screenshot = Image.open(source).convert("RGB")
    screenshot = screenshot.resize((1280, 800), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1280, 720), "#101915")
    canvas.paste(screenshot.crop((0, 0, 1280, 720)), (0, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rectangle((0, 550, 1280, 720), fill=(13, 25, 18, 245))
    draw.rectangle((0, 550, 1280, 554), fill=(166, 195, 147, 255))
    draw.text((52, 575), label, font=font(19, True), fill="#acc699")
    draw.text((52, 607), title, font=font(36, True), fill="white")
    draw.text((52, 668), "FAIRPANEL  •  LIVE PRODUCT WALKTHROUGH", font=font(16), fill="#bbcbc0")
    draw.text((1135, 668), f"{number:02d} / {len(SCENES):02d}", font=font(16, True), fill="#bbcbc0")
    return canvas


def audio_duration(path):
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def combine_wavs(paths, output):
    with wave.open(str(paths[0]), "rb") as first:
        params = first.getparams()
    with wave.open(str(output), "wb") as joined:
        joined.setparams(params)
        for path in paths:
            with wave.open(str(path), "rb") as wav:
                if wav.getparams()[:3] != params[:3]:
                    raise RuntimeError("Narration WAV formats do not match")
                joined.writeframes(wav.readframes(wav.getnframes()))


def timestamp(seconds):
    whole = round(seconds)
    return f"{whole // 60:02d}:{whole % 60:02d}"


def write_demo_script():
    elapsed = 0.0
    sections = [
        "# FairPanel demo script",
        "",
        "This narration accompanies [fairpanel-demo.mp4](fairpanel-demo.mp4), recorded from the live Docker app. Runtime is approximately five minutes and sixteen seconds. The demo uses bundled synthetic fixtures and does not publish results or send invitations.",
        "",
    ]
    for index, scene in enumerate(SCENES, start=1):
        wav_path = AUDIO / f"scene-{index:02d}.wav"
        duration = audio_duration(wav_path)
        sections.extend([
            f"## {timestamp(elapsed)}–{timestamp(elapsed + duration)} — {scene['title']}",
            "",
            f"Screen: `{'/judge/projects/<assigned-project-id>/' if scene['url'] == '__judge_review__' else scene['url']}` ({scene['label'].lower()}).",
            "",
            scene["narration"],
            "",
        ])
        elapsed += duration
    (ROOT / "demo" / "DEMO-SCRIPT.md").write_text("\n".join(sections), encoding="utf-8")
    print(f"Script: {ROOT / 'demo' / 'DEMO-SCRIPT.md'} ({elapsed:.1f} seconds)")


def main():
    FRAMES.mkdir(parents=True, exist_ok=True)
    AUDIO.mkdir(parents=True, exist_ok=True)
    image_paths = []
    wav_paths = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(CHROME), headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        contexts = {}
        for role, email in (
            ("participant", "participant@fairpanel.local"),
            ("judge", "tomas.varga@example.org"),
            ("organizer", "organizer@fairpanel.local"),
        ):
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.goto(BASE + f"/login/{role}/", wait_until="networkidle")
            page.fill('input[name="email"]', email)
            page.fill('input[name="password"]', PASSWORD)
            page.locator('button[type="submit"]').click()
            page.wait_for_load_state("networkidle")
            contexts[role] = (context, page)
        public = browser.new_context(viewport={"width": 1440, "height": 900})
        public_page = public.new_page()
        participant_page = contexts["participant"][1]
        participant_page.goto(BASE + "/participant/events/evt_demo/team/", wait_until="networkidle")
        if participant_page.locator("#form-create-team").count():
            participant_page.fill('input[name="name"]', "FairPanel Demo Team")
            participant_page.locator("#btn-submit-team").click()
            participant_page.wait_for_load_state("networkidle")
            participant_page.reload(wait_until="networkidle")
        judge_page = contexts["judge"][1]
        judge_page.goto(BASE + "/judge/?event=evt_01", wait_until="networkidle")
        review_link = judge_page.locator('a[href^="/judge/projects/"]').first
        review_url = review_link.get_attribute("href") if review_link.count() else None
        if not review_url:
            raise RuntimeError("No assigned judge review link was found")
        for index, scene in enumerate(SCENES, start=1):
            page = contexts[scene["role"]][1] if scene["role"] else public_page
            route = review_url if scene["url"] == "__judge_review__" else scene["url"]
            response = page.goto(BASE + route, wait_until="networkidle")
            if not response or response.status >= 400:
                raise RuntimeError(f"Cannot capture {route}: HTTP {response.status if response else 'none'}")
            if index in (2, 14):
                page.evaluate("window.scrollTo(0, 500)")
                page.wait_for_timeout(250)
            shot = FRAMES / f"raw-{index:02d}.png"
            page.screenshot(path=str(shot))
            output_frame = FRAMES / f"scene-{index:02d}.png"
            render_frame(shot, scene["title"], scene["label"], index).save(output_frame)
            image_paths.append(output_frame)
            narration_file = AUDIO / f"scene-{index:02d}.txt"
            narration_file.write_text(scene["narration"], encoding="utf-8")
            wav_file = AUDIO / f"scene-{index:02d}.wav"
            subprocess.run([
                "pwsh", "-NoProfile", "-File", str(ROOT / "demo" / "narrate.ps1"),
                str(narration_file), str(wav_file),
            ], check=True, stdout=subprocess.DEVNULL)
            wav_paths.append(wav_file)
            print(f"Captured scene {index:02d}: {scene['title']}", flush=True)
        browser.close()
    joined_audio = WORK / "narration.wav"
    combine_wavs(wav_paths, joined_audio)
    playlist = WORK / "slides.txt"
    lines = []
    for image_path, wav_path in zip(image_paths, wav_paths):
        lines.append(f"file '{image_path.as_posix()}'")
        lines.append(f"duration {audio_duration(wav_path):.3f}")
    lines.append(f"file '{image_paths[-1].as_posix()}'")
    playlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(playlist),
        "-i", str(joined_audio), "-filter:v", "fps=12,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        "-t", f"{audio_duration(joined_audio):.3f}", str(OUTPUT),
    ], check=True)
    write_demo_script()
    print(f"Video: {OUTPUT} ({audio_duration(joined_audio):.1f} seconds)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--script-only":
        write_demo_script()
    else:
        main()
