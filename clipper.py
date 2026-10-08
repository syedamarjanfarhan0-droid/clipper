"""
clipper.py  --  v2.0

Turns one long video (a podcast, a stream, an interview) into short
vertical clips for TikTok, Reels and YouTube Shorts.

What it does, in order:
    1. Writes a transcript of the video (on your own computer, free)
    2. Picks the best moments to clip
    3. Crops each clip to 9:16 vertical
    4. Burns big word-by-word captions onto it

Usage:
    python clipper.py show.mp4                  pick 5 clips automatically
    python clipper.py show.mp4 --count 10       pick 10 clips
    python clipper.py show.mp4 --clips my.txt   use your own start/end times

Every run also writes a clips file next to the clips. Edit it and run again
with --clips to fine-tune the cuts. The transcript is saved too, so the
second run starts straight away.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent

WIDTH, HEIGHT = 1080, 1920          # vertical 9:16


# ----------------------------------------------------------------------------
# ffmpeg
# ----------------------------------------------------------------------------

def find_ffmpeg():
    """Use the ffmpeg in this folder. Fall back to a system one."""
    for name in ("ffmpeg.exe", "ffmpeg"):
        local = HERE / name
        if local.exists():
            return str(local)
    found = shutil.which("ffmpeg")
    if found:
        return found
    print("Cannot find ffmpeg.")
    print("Put ffmpeg (ffmpeg.exe on Windows) in this folder, or install it.")
    sys.exit(1)


FFMPEG = None


def video_duration(video):
    """Length of the video in seconds, read from ffmpeg's banner."""
    result = subprocess.run([FFMPEG, "-i", str(video)],
                            capture_output=True, text=True, errors="replace")
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", result.stderr)
    if not match:
        return None
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


# ----------------------------------------------------------------------------
# 1. Transcript
# ----------------------------------------------------------------------------

def transcribe(video, model_name):
    """Word-level transcript, cached next to the video as <name>.transcript.json"""
    cache = video.with_suffix(".transcript.json")
    if cache.exists():
        print(f"Using saved transcript: {cache.name}")
        return json.loads(cache.read_text(encoding="utf-8"))

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("The transcript needs faster-whisper. Install it once with:")
        print("    pip install -r requirements.txt")
        sys.exit(1)

    print(f"Writing the transcript (model '{model_name}'). "
          "The first run downloads the model; long videos take a while.")
    model = WhisperModel(model_name, device="auto", compute_type="auto")
    segments, info = model.transcribe(str(video), word_timestamps=True,
                                      vad_filter=True)

    transcript = {"language": info.language, "segments": []}
    for seg in segments:
        words = [{"start": round(w.start, 2), "end": round(w.end, 2),
                  "word": w.word.strip()}
                 for w in (seg.words or []) if w.word.strip()]
        transcript["segments"].append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": words,
        })
        print(f"  {fmt_time(seg.start)}  {seg.text.strip()[:70]}")

    cache.write_text(json.dumps(transcript, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"Saved transcript: {cache.name}\n")
    return transcript


def all_words(transcript):
    return [w for seg in transcript["segments"] for w in seg["words"]]


# ----------------------------------------------------------------------------
# 2. Picking clips
# ----------------------------------------------------------------------------

def parse_time(text):
    """Accepts 95, 95.5, 1:35 or 0:01:35."""
    text = text.strip()
    parts = text.split(":")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def fmt_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def read_clips(path):
    """Read a clips file. One clip per line:  start,end,title"""
    clips = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 2)
        if len(parts) < 2:
            print(f"  skipping line {line_number}: needs start,end,title")
            continue
        try:
            start, end = parse_time(parts[0]), parse_time(parts[1])
        except ValueError:
            print(f"  skipping line {line_number}: times look wrong")
            continue
        title = parts[2].strip() if len(parts) == 3 else f"Clip {len(clips) + 1}"
        clips.append({"start": start, "end": end, "title": title})
    return clips


def write_clips(clips, path):
    lines = ["# start,end,title   (edit and run again with --clips this-file)"]
    for c in clips:
        lines.append(f"{fmt_time(c['start'])}.{int(c['start'] % 1 * 10)},"
                     f"{fmt_time(c['end'])}.{int(c['end'] % 1 * 10)},{c['title']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


HOOK_WORDS = {
    "never", "always", "secret", "crazy", "insane", "truth", "honestly",
    "mistake", "best", "worst", "nobody", "everyone", "money", "million",
    "why", "how", "stop", "wrong", "actually", "biggest", "realized",
}


def pick_clips_locally(transcript, count, min_len, max_len):
    """No-AI picker: favours fast, punchy stretches that start and end on a sentence."""
    segs = [s for s in transcript["segments"] if s["words"]]
    candidates = []
    for i, first in enumerate(segs):
        text, words, j = [], 0, i
        while j < len(segs) and segs[j]["end"] - first["start"] <= max_len:
            text.append(segs[j]["text"])
            words += len(segs[j]["words"])
            length = segs[j]["end"] - first["start"]
            if length >= min_len and re.search(r"[.!?]$", segs[j]["text"]):
                joined = " ".join(text)
                lower = re.findall(r"[a-z']+", joined.lower())
                score = words / length                       # pace
                score += 0.6 * joined.count("?") + 0.4 * joined.count("!")
                score += 0.5 * sum(w in HOOK_WORDS for w in lower[:15])  # strong opening
                score += 0.15 * sum(w in HOOK_WORDS for w in lower)
                candidates.append({"start": first["start"], "end": segs[j]["end"],
                                   "score": score, "text": joined})
            j += 1

    chosen = []
    for c in sorted(candidates, key=lambda c: c["score"], reverse=True):
        if all(c["end"] <= o["start"] or c["start"] >= o["end"] for o in chosen):
            chosen.append(c)
        if len(chosen) == count:
            break

    for c in chosen:
        first_sentence = re.split(r"(?<=[.!?])\s", c["text"])[0]
        c["title"] = " ".join(first_sentence.split()[:8]).rstrip(".,!?")
    return sorted(chosen, key=lambda c: c["start"])


def pick_clips_with_claude(transcript, count, min_len, max_len):
    """Asks Claude for the most shareable moments. Needs ANTHROPIC_API_KEY."""
    import anthropic
    from pydantic import BaseModel

    class Clip(BaseModel):
        start: float
        end: float
        title: str
        why: str

    class ClipList(BaseModel):
        clips: list[Clip]

    lines = [f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}"
             for s in transcript["segments"]]
    prompt = (
        f"Below is a timestamped transcript of a long video. Pick the {count} best "
        f"moments to post as standalone short vertical clips (TikTok, Reels, Shorts).\n\n"
        f"A good clip hooks the viewer in the first two seconds, makes sense without "
        f"the rest of the video, and lands a point, a laugh or a strong opinion. "
        f"Each clip must be between {min_len} and {max_len} seconds, start at the "
        f"start of a sentence and end at the end of one. Clips must not overlap. "
        f"Use the timestamps from the transcript. The title is a short, catchy "
        f"caption for the post.\n\nTranscript:\n" + "\n".join(lines)
    )

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
        output_format=ClipList,
    )
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        raise RuntimeError(f"Claude stopped early ({response.stop_reason})")

    clips = []
    for c in response.parsed_output.clips:
        if c.end > c.start:
            clips.append({"start": c.start, "end": c.end, "title": c.title})
            print(f"  {fmt_time(c.start)}-{fmt_time(c.end)}  {c.title}  ({c.why})")
    return sorted(clips, key=lambda c: c["start"])


def pick_clips(transcript, args):
    use_ai = args.ai and os.environ.get("ANTHROPIC_API_KEY")
    if use_ai:
        try:
            print("Asking Claude to pick the best moments...")
            clips = pick_clips_with_claude(transcript, args.count, args.min, args.max)
            if clips:
                return clips
        except Exception as error:   # any failure: fall back to the local picker
            print(f"  Claude could not pick clips ({error}); using the built-in picker.")
    print("Picking clips...")
    return pick_clips_locally(transcript, args.count, args.min, args.max)


# ----------------------------------------------------------------------------
# 3 + 4. Vertical crop and captions
# ----------------------------------------------------------------------------

def ass_time(seconds):
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ass_escape(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def write_captions(words, clip, path, words_per_line=3):
    """Big centred captions, a few words at a time, the spoken word in yellow."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {WIDTH}
PlayResY: {HEIGHT}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,3,2,60,60,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    inside = [w for w in words if w["end"] > clip["start"] and w["start"] < clip["end"]]

    # a few words per caption, and a new caption at the end of each sentence
    groups = [[]]
    for w in inside:
        if len(groups[-1]) == words_per_line or (
                groups[-1] and re.search(r"[.!?]$", groups[-1][-1]["word"])):
            groups.append([])
        groups[-1].append(w)

    events = []
    for g, group in enumerate(groups):
        for k, word in enumerate(group):
            start = word["start"] - clip["start"]
            # hold until the next word starts, so the caption never flickers off
            if k + 1 < len(group):
                end = group[k + 1]["start"] - clip["start"]
            elif g + 1 < len(groups):
                end = min(groups[g + 1][0]["start"], word["end"] + 0.6) - clip["start"]
            else:
                end = word["end"] - clip["start"] + 0.4
            parts = []
            for n, w in enumerate(group):
                text = ass_escape(w["word"]).upper()
                parts.append("{\\c&H00E5FF&}" + text + "{\\c&HFFFFFF&}" if n == k else text)
            events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,"
                          + " ".join(parts))
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def safe_name(title):
    keep = [c for c in title if c.isalnum() or c in " -_"]
    return "".join(keep).strip()[:60] or "clip"


def render_clip(video, clip, number, outdir, words, layout, captions):
    duration = clip["end"] - clip["start"]
    if duration <= 0:
        print(f"  skipping '{clip['title']}': end must be after start")
        return False

    filename = f"{number:02d} - {safe_name(clip['title'])}.mp4"
    outpath = (outdir / filename).resolve()

    if layout == "fit":
        # whole picture in the middle, a blurred copy filling the background
        video_filter = (
            f"[0:v]split[a][b];"
            f"[a]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},boxblur=30:2[bg];"
            f"[b]scale={WIDTH}:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        # zoom in on the centre so the picture fills the whole phone screen
        video_filter = (
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT}"
        )

    with tempfile.TemporaryDirectory() as work:
        if captions and words:
            write_captions(words, clip, Path(work) / "captions.ass")
            # a bare file name, run from the temp folder: avoids Windows path escaping
            video_filter += ",ass=captions.ass"
        video_filter += ",setsar=1[v]"

        command = [
            FFMPEG, "-y",
            "-ss", f"{clip['start']:.2f}",
            "-i", str(video.resolve()),
            "-t", f"{duration:.2f}",
            "-filter_complex", video_filter,
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-r", "30",
            "-movflags", "+faststart",
            str(outpath),
        ]
        print(f"  making {filename}  ({duration:.0f}s)")
        result = subprocess.run(command, cwd=work, capture_output=True,
                                text=True, errors="replace")
        if result.returncode != 0:
            print(f"  FAILED: {clip['title']}")
            print(result.stderr[-800:])
            return False
    return True


# ----------------------------------------------------------------------------

def main():
    global FFMPEG
    parser = argparse.ArgumentParser(
        description="Turn a long video into short vertical clips with captions.")
    parser.add_argument("video", help="the long video, e.g. show.mp4")
    parser.add_argument("--clips", help="use your own clips file (start,end,title per line)")
    parser.add_argument("--count", type=int, default=5, help="how many clips to pick (default 5)")
    parser.add_argument("--min", type=float, default=20, help="shortest clip in seconds (default 20)")
    parser.add_argument("--max", type=float, default=60, help="longest clip in seconds (default 60)")
    parser.add_argument("--layout", choices=["fill", "fit"], default="fill",
                        help="fill: zoom to fill the screen (default). "
                             "fit: whole picture on a blurred background")
    parser.add_argument("--no-captions", dest="captions", action="store_false",
                        help="don't burn captions in")
    parser.add_argument("--model", default="small",
                        help="transcript model: tiny, base, small (default), medium, large-v3")
    parser.add_argument("--no-ai", dest="ai", action="store_false",
                        help="don't ask Claude, even if ANTHROPIC_API_KEY is set")
    parser.add_argument("--out", default="output", help="folder for the clips (default 'output')")
    args = parser.parse_args()

    video = Path(args.video)
    if not video.exists() and (HERE / args.video).exists():
        video = HERE / args.video
    if not video.exists():
        print(f"Cannot find video: {args.video}")
        sys.exit(1)

    FFMPEG = find_ffmpeg()
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    need_transcript = args.captions or not args.clips
    transcript = transcribe(video, args.model) if need_transcript else None
    words = all_words(transcript) if transcript else []

    if args.clips:
        clips = read_clips(Path(args.clips))
    else:
        clips = pick_clips(transcript, args)
    if not clips:
        print("No clips to make.")
        sys.exit(1)

    length = video_duration(video)
    if length:
        for c in clips:
            c["end"] = min(c["end"], length)

    clips_file = outdir / f"{video.stem} clips.txt"
    write_clips(clips, clips_file)

    print(f"\nMaking {len(clips)} clips...")
    made = sum(render_clip(video, c, n, outdir, words, args.layout, args.captions)
               for n, c in enumerate(clips, 1))

    print(f"\nDone. {made} clips are in '{outdir}'.")
    print(f"To change the cuts, edit '{clips_file}' and run:")
    print(f'    python clipper.py "{video}" --clips "{clips_file}"')


if __name__ == "__main__":
    main()
