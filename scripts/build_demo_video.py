"""Build a labelled demo from real captures, frozen results and local synthetic voice.

No browser control, requests, API use, package installation, or secret access.
Requires Pillow and an existing ffmpeg/ffprobe installation. Existing outputs
are never overwritten. Scene timing follows the seven narration word counts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"
SIZE = (1280, 720)
NAVY = "#111c30"
INK = "#192a43"
MUTED = "#516079"
BLUE = "#335edc"
BG = "#edf2fa"
FONT_DIR = Path("C:/Windows/Fonts")


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(FONT_DIR / ("segoeuib.ttf" if bold else "segoeui.ttf")), size)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def paragraph_counts() -> list[int]:
    started = False
    paragraphs = []
    for line in (ROOT / "docs" / "demo_narration.md").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("["):
            started = True
        elif started and line and not line.startswith("#"):
            paragraphs.append(len(line.split()))
    if len(paragraphs) != 7 or not 350 <= sum(paragraphs) <= 375:
        raise ValueError("Expected the approved seven-paragraph, 350-375-word narration.")
    return paragraphs


def wrap_text(draw, text: str, face, width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=face) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


def text_block(draw, text, box, size=25, bold=False, fill=INK, spacing=7):
    x, y, width, height = box
    face = font(size, bold)
    lines = wrap_text(draw, text, face, width)
    line_height = size + spacing
    if len(lines) * line_height > height:
        raise ValueError(f"Text does not fit: {text[:70]}")
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill)
        y += line_height


def base_frame(title, caption, badge="REAL APP CAPTURE"):
    frame = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(frame)
    draw.rectangle((0, 0, 1279, 98), fill=NAVY)
    draw.text((34, 10), "GEN ACADEMY  /  ENTERPRISE POLICY Q&A", font=font(16, True), fill="#b5c8ff")
    text_block(draw, title, (32, 36, 1190, 54), 34, True, "white", 6)
    draw.rounded_rectangle((32, 107, 1248, 589), radius=12, fill="white", outline="#d4dfef", width=2)
    draw.rectangle((0, 604, 1279, 719), fill="white")
    text_block(draw, caption, (34, 613, 1210, 61), 23, False, INK, 5)
    draw.text((34, 688), "LOCAL SYNTHETIC VOICE  |  SAVED RESULTS, NO NEW API REQUESTS", font=font(16, True), fill=MUTED)
    face = font(14, True)
    width = draw.textlength(badge, font=face)
    draw.text((1244 - width, 690), badge, font=face, fill=BLUE)
    return frame


def screenshot_frame(title, caption, path, badge="REAL APP CAPTURE", crop=None):
    frame = base_frame(title, caption, badge)
    with Image.open(path) as image:
        image = image.convert("RGB")
        if crop is not None:
            left, top, right, bottom = crop
            if left < 0 or top < 0 or right > image.width or bottom > image.height:
                raise ValueError(f'Crop exceeds actual capture bounds: {path}')
            image = image.crop(crop)
        fitted = ImageOps.contain(image, (1204, 470), Image.Resampling.LANCZOS)
        frame.paste(fitted, (38 + (1204 - fitted.width) // 2, 113 + (470 - fitted.height) // 2))
    return frame


def comparison_frame(p0, p1, config):
    frame = base_frame(
        "Measured improvement — with the trade-offs visible",
        "Same 15 previously inspected questions: a diagnostic follow-up, not a fresh held-out test.",
        "SAVED-JSON SUMMARY",
    )
    draw = ImageDraw.Draw(frame)
    draw.text((61, 127), "MEASURE", font=font(18, True), fill=MUTED)
    draw.text((665, 127), "P0 · DENSE 384/64", font=font(20, True), fill=INK)
    draw.text((963, 127), "P1 · HYBRID 256/48", font=font(20, True), fill=BLUE)
    rows = [
        ("Gold evidence found · Hit@5", f"{p0['hit_at_5']:.1%} · 7/9", f"{p1['hit_at_5']:.1%} · 8/9"),
        ("Answerable questions answered", f"{p0['answerable_count'] - p0['false_refusal_count']}/9", f"{p1['answerable_count'] - p1['false_refusal_count']}/9"),
        ("Correct expected fallbacks", f"{p0['correct_fallback_count']}/6", f"{p1['correct_fallback_count']}/6"),
        ("Provider errors", str(p0['service_error_count']), str(p1['service_error_count'])),
    ]
    for i, (label, before, after) in enumerate(rows):
        y = 180 + i * 63
        if i % 2 == 0:
            draw.rectangle((49, y - 8, 1230, y + 43), fill="#f1f5fc")
        draw.text((61, y), label, font=font(25), fill=INK)
        draw.text((683, y), before, font=font(29, True), fill=INK)
        draw.text((989, y), after, font=font(29, True), fill=BLUE)
    text_block(draw, "P1 released 9 total answers: 8 supported answers plus the original B1 scope error.", (61, 443, 1160, 65), 23, True)
    automatic = config['automatic_development_selector']
    text_block(draw, f"Development selector: {automatic['profile']} {automatic['retrieval']}. Delivered hybrid is an explicit product choice; 256 uses fewer tokens within hybrid.", (61, 511, 1156, 66), 20, False, MUTED, 5)
    return frame


def correction_frame(b1, correction, ui):
    frame = base_frame(
        "A real failure — then a separately verified correction",
        "Original B1 failure is preserved. Targeted checks are not a new complete evaluation.",
        "SAVED-JSON SUMMARY",
    )
    draw = ImageDraw.Draw(frame)
    text_block(draw, b1['question'], (57, 123, 1160, 68), 27, True)
    draw.rounded_rectangle((52, 207, 625, 566), radius=12, fill="#fff0ef")
    draw.rounded_rectangle((648, 207, 1227, 566), radius=12, fill="#eaf5ef")
    draw.text((72, 224), "ORIGINAL RUN · FAILED SCOPE", font=font(21, True), fill="#a53330")
    answer = re.sub(r"\[([^\]]+)\]\([^)]+\)", "", b1['response']['answer']).strip()
    text_block(draw, answer, (72, 266, 529, 190), 23)
    text_block(draw, "Real company-policy quotes did not establish personal statutory entitlement.", (72, 469, 529, 86), 22, True, "#a53330", 6)
    draw.text((668, 224), "AFTERWARD · SCOPE GUARD", font=font(21, True), fill="#216344")
    checks = correction['targeted_scope_results']
    passed = sum(row['status'] == 'fallback' and not row['api_called'] for row in checks)
    b1_ui = next(row for row in ui['rows'] if row['id'] == 'B1')['response']
    text_block(draw, f"{passed}/{len(checks)} targeted formulations fell back before retrieval or generation.\n\n0 additional API calls.\n\nSeparate real UI B1 status: {b1_ui['status']}.", (668, 266, 533, 208), 24)
    text_block(draw, "Not a general legal or semantic checker.", (668, 500, 533, 57), 21, True, "#216344")
    return frame


def conclusion_frame(review, verification):
    frame = base_frame(
        "Inspectable evidence. Honest limits. Reproducible delivery.",
        "AI coding assistance and synthetic narration are disclosed. Student review remains necessary.",
        "SAVED-JSON SUMMARY",
    )
    draw = ImageDraw.Draw(frame)
    summary = review['summary']
    budget = verification['api_budget']
    cards = [
        ("SUPPORTED ANSWERS", str(summary['supported_and_correct_answers']), "AI-assisted source review; not independent human scoring."),
        ("P1 CHECKPOINT TESTS", str(verification['offline_tests']['passed']), "Historical P1 checkpoint; later delivery tests are separate."),
        ("API ATTEMPTS", f"{budget['total_used']} / {budget['limit']}", f"Recorded checkpoint: {budget['remaining']} remaining; this video uses saved results."),
    ]
    for i, (label, value, detail) in enumerate(cards):
        x = 57 + i * 399
        draw.rounded_rectangle((x, 139, x + 371, 411), radius=12, fill="#f0f4fc")
        text_block(draw, label, (x + 19, 158, 335, 36), 18, True, BLUE)
        draw.text((x + 19, 204), value, font=font(55, True), fill=INK)
        text_block(draw, detail, (x + 19, 288, 333, 112), 22, False, MUTED, 6)
    text_block(draw, "Still limited: cafe/laptop false refusal, a small static corpus, and no semantic guarantee from quotation matching.", (60, 440, 1157, 88), 26, True)
    text_block(draw, "Included: source · setup · corpus attribution · architecture · measured evaluation · failure analysis", (60, 543, 1157, 33), 20, False, MUTED)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures', type=Path, default=ROOT / 'artifacts/demo/captures')
    parser.add_argument('--audio', type=Path, default=ROOT / 'artifacts/demo/synthetic_narration_3min.wav')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/demo/enterprise-policy-rag-demo.mp4')
    parser.add_argument('--ffmpeg', type=Path, default=Path('C:/Program Files/FebBox/FFmpeg/ffmpeg.exe'))
    parser.add_argument('--check', action='store_true', help='Validate inputs and print plan only; write nothing.')
    args = parser.parse_args()
    output = args.output.resolve()
    demo_root = (ROOT / 'artifacts/demo').resolve()
    if not output.is_relative_to(demo_root) or output.suffix.lower() != '.mp4':
        raise ValueError('Output must be an MP4 under this project artifacts/demo directory.')
    frame_dir = output.with_suffix('')
    if output.exists() or frame_dir.exists():
        raise FileExistsError('Output or frame directory exists; choose a fresh --output filename.')
    if not args.ffmpeg.is_file():
        raise FileNotFoundError(args.ffmpeg)
    required = [args.captures / f'{name}.png' for name in ('overview', 'n1', 'u1', 'architecture')]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    evidence_path = args.captures / 'n1_evidence.png'
    has_evidence_capture = evidence_path.is_file()
    audio_metadata = read_json(args.audio.with_suffix('.json'))
    if audio_metadata.get('synthetic_voice') is not True:
        raise ValueError('Synthetic narration must have an explicit disclosure metadata file.')
    with wave.open(str(args.audio), 'rb') as audio:
        duration = audio.getnframes() / audio.getframerate()
    if not 165 <= duration <= 195:
        raise ValueError('Narration is outside the approved approximately three-minute range.')
    counts = paragraph_counts()
    paragraph_times = [duration * words / sum(counts) for words in counts]
    p0 = read_json(RESULTS / 'dense_evaluation.json')
    p1 = read_json(RESULTS / 'p1_hybrid_256_evaluation.json')
    review = read_json(RESULTS / 'p1_evidence_review.json')
    correction = read_json(RESULTS / 'p1_corrections_verification.json')
    ui = read_json(RESULTS / 'p1_ui_smoke.json')
    verification = read_json(RESULTS / 'p1_verification.json')
    config = read_json(RESULTS / 'p1_active_configuration.json')
    b1 = next(row for row in p1['rows'] if row['id'] == 'B1')
    scenes = [
        ('overview', paragraph_times[0]), ('profile', paragraph_times[1]),
        ('architecture', paragraph_times[2]),
        ('n1', paragraph_times[3] * (.34 if has_evidence_capture else .58)),
    ]
    if has_evidence_capture:
        scenes.append(('n1_evidence', paragraph_times[3] * .24))
    scenes.extend([('u1', paragraph_times[3] * .42), ('comparison', paragraph_times[4]),
                   ('correction', paragraph_times[5]), ('conclusion', paragraph_times[6])])
    start = 0.0
    scene_plan = []
    for name, seconds in scenes:
        scene_plan.append({'scene': name, 'start_seconds': round(start, 4), 'duration_seconds': round(seconds, 4)})
        start += seconds
    plan = {'duration_seconds': duration, 'size': list(SIZE), 'fps': 24,
            'voice': audio_metadata, 'spoken_paragraph_words': counts, 'scenes': scene_plan,
            'timing_note': 'Scene lengths proportional to seven paragraph word counts, not forced word-level alignment.',
            'disclosures': ['Local synthetic voice, not a recording of the student.',
                            'Real application captures display saved evaluation replay, not new live inference.',
                            'Metrics and correction cards are drawn from saved JSON, not simulated application screens.',
                            'Camera-style crops enlarge actual capture regions; source PNGs are preserved unchanged.'],
            'capture_crop_pixels': {'profile': [24, 108, 1256, 282], 'architecture': [24, 294, 1256, 735],
                                    'n1': [416, 540, 1166, 892], 'u1': [416, 540, 1166, 892],
                                    'n1_evidence': [428, 310, 1150, 625]},
            'api_calls': 0, 'created_utc': datetime.now(timezone.utc).isoformat()}
    if args.check:
        print(json.dumps(plan, indent=2))
        return
    frame_dir.mkdir(parents=True, exist_ok=False)
    frames = [
        screenshot_frame('Enterprise Policy Q&A', '12 public GitLab policy pages · static snapshot · evidence-linked answers', required[0]),
        screenshot_frame('A local, source-traceable corpus', '364 heading-aware chunks · 256-token limit · 48-token overlap · local BGE + Chroma', required[3], 'ACTUAL DIAGRAM · OFFLINE LANE', crop=(24, 108, 1256, 282)),
        screenshot_frame('LangGraph: retrieval → evidence → generation → checks', 'Dense + BM25 + RRF run sequentially in one retrieval node. Quote checks are not semantic proof.', required[3], 'ACTUAL DIAGRAM · ONLINE LANE', crop=(24, 294, 1256, 735)),
        screenshot_frame('Supported question: minimum password length', 'Saved P1 evaluation replay — not a live request. The answer and cited excerpt are real saved output.', required[1], 'SAVED EVALUATION REPLAY', crop=(416, 540, 1166, 892)),
    ]
    if has_evidence_capture:
        frames.append(screenshot_frame('Inspect the source quotation and section', 'Real saved citation and evidence excerpt. Quotation presence verifies provenance, not every inference.', evidence_path, 'SAVED EVALUATION REPLAY', crop=(428, 310, 1150, 625)))
    frames.extend([
        screenshot_frame('Unsupported question: paid pet-adoption leave', 'Saved P1 evaluation replay — not a live request. The model returned insufficient evidence.', required[2], 'SAVED EVALUATION REPLAY', crop=(416, 540, 1166, 892)),
        comparison_frame(p0['summary'], p1['summary'], config),
        correction_frame(b1, correction, ui),
        conclusion_frame(review, verification),
    ])
    if len(frames) != len(scenes):
        raise ValueError('Frame and scene counts must match exactly.')
    concat = []
    for index, ((name, seconds), frame) in enumerate(zip(scenes, frames), 1):
        filename = f'{index:02d}_{name}.png'
        frame.save(frame_dir / filename)
        concat.extend([f"file '{filename}'", f'duration {seconds:.9f}'])
    concat.append(f"file '{len(scenes):02d}_{scenes[-1][0]}.png'")
    concat_path = frame_dir / 'frames.ffconcat'
    concat_path.write_text('\n'.join(concat) + '\n', encoding='utf-8')
    input_paths = [*required, args.audio, RESULTS / 'p1_hybrid_256_evaluation.json', RESULTS / 'dense_evaluation.json']
    if has_evidence_capture:
        input_paths.append(evidence_path)
    plan['input_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in input_paths}
    (frame_dir / 'storyboard.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    command = [str(args.ffmpeg), '-hide_banner', '-n', '-f', 'concat', '-safe', '1',
               '-i', str(concat_path), '-i', str(args.audio.resolve()), '-vf', 'fps=24,format=yuv420p',
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-b:a', '128k',
               '-movflags', '+faststart', '-t', f'{duration:.6f}', str(output)]
    process = subprocess.run(command, capture_output=True, text=True)
    (frame_dir / 'encoding.log').write_text(process.stderr, encoding='utf-8')
    if process.returncode:
        raise RuntimeError(f'Encoding failed; inspect {frame_dir / "encoding.log"}')
    probe = subprocess.run([str(args.ffmpeg.with_name('ffprobe.exe')), '-v', 'error', '-show_entries',
                            'format=duration,size:stream=codec_name,width,height,sample_rate,channels',
                            '-of', 'json', str(output)], check=True, capture_output=True, text=True)
    media = json.loads(probe.stdout)
    media['sha256'] = digest(output)
    media['api_calls'] = 0
    media['synthetic_voice'] = True
    (frame_dir / 'verification.json').write_text(json.dumps(media, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'verification': media, 'storyboard': str(frame_dir / 'storyboard.json')}, indent=2))


if __name__ == '__main__':
    main()
