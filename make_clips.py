"""
make_clips.py  --  v1.1

Cuts one long video into several short clips.
You tell it the start and end time of each clip in clips.txt

Usage:
    python3 make_clips.py show.mp4

This version uses the ffmpeg file sitting in the same folder.
"""

import subprocess
import sys
from pathlib import Path

# Where this script lives
HERE = Path(__file__).parent


def find_ffmpeg():
    """Use the ffmpeg in this folder. Fall back to a system one."""
    local = HERE / "ffmpeg"
    if local.exists():
        return str(local)
    return "ffmpeg"


FFMPEG = find_ffmpeg()


def read_clips(path):
    """Read clips.txt. One clip per line:  start,end,title"""
    clips = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()

        # skip blank lines and comments
        if not line or line.startswith("#"):
            continue

        parts = line.split(",", 2)
        if len(parts) != 3:
            print(f"  skipping line {line_number}: needs start,end,title")
            continue

        start, end, title = parts
        try:
            clips.append({
                "start": float(start),
                "end": float(end),
                "title": title.strip(),
            })
        except ValueError:
            print(f"  skipping line {line_number}: times must be numbers")

    return clips


def safe_name(title):
    """Remove characters that are not allowed in filenames."""
    keep = [c for c in title if c.isalnum() or c in " -_"]
    return "".join(keep).strip() or "clip"


def cut_clip(video, clip, number, outdir):
    """Cut one clip out of the video using ffmpeg."""
    duration = clip["end"] - clip["start"]
    if duration <= 0:
        print(f"  skipping '{clip['title']}': end must be after start")
        return

    filename = f"{number:02d} - {safe_name(clip['title'])}.mp4"
    outpath = outdir / filename

    command = [
        FFMPEG,
        "-y",                          # overwrite if the file exists
        "-ss", str(clip["start"]),     # where to start
        "-i", str(video),              # input video
        "-t", str(duration),           # how long the clip is
        "-c:v", "libx264",             # re-encode video
        "-preset", "fast",
        "-crf", "20",                  # quality: lower = better, bigger
        "-c:a", "aac",                 # re-encode audio
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(outpath),
    ]

    print(f"  cutting {filename}  ({duration:.1f}s)")
    try:
        subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as error:
        print(f"  FAILED: {clip['title']}")
        print(error.stderr.decode()[-500:])


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 make_clips.py <video file>")
        sys.exit(1)

    video = HERE / sys.argv[1]
    if not video.exists():
        print(f"Cannot find video: {sys.argv[1]}")
        print("Make sure it is in the same folder as this script.")
        sys.exit(1)

    clips_file = HERE / "clips.txt"
    if not clips_file.exists():
        print("Cannot find clips.txt")
        sys.exit(1)

    clips = read_clips(clips_file)
    if not clips:
        print("No clips found in clips.txt")
        sys.exit(1)

    outdir = HERE / "output"
    outdir.mkdir(exist_ok=True)

    print(f"Using ffmpeg: {FFMPEG}")
    print(f"Found {len(clips)} clips.\n")

    for number, clip in enumerate(clips, start=1):
        cut_clip(video, clip, number, outdir)

    print(f"\nDone. Clips are in the 'output' folder.")


if __name__ == "__main__":
    main()
