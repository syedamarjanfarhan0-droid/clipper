# Clipper

Turns one long video (a podcast, a stream, an interview) into short vertical clips for TikTok, Instagram Reels and YouTube Shorts.

Give it the long video. It writes a transcript, picks the best moments, crops each one to 9:16 and burns in big word-by-word captions. Everything runs on your own computer; nothing is uploaded unless you turn on the optional Claude picker.

## What you get

- 5 clips (or as many as you ask for), each 20 to 60 seconds, in an `output` folder
- 1080×1920 vertical MP4s that upload straight to TikTok, Reels and Shorts
- Captions three words at a time, with the word being spoken in yellow
- A clips file listing every cut, so you can fix a start or end and run again

## Set up (once)

1. Install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/). On Windows, tick "Add Python to PATH" in the installer.
2. Get **ffmpeg**. Either install it, or download it and put `ffmpeg.exe` (Windows) or `ffmpeg` (Mac) in this folder.
3. Open a terminal in this folder and run:

```bash
pip install -r requirements.txt
```

## Make clips

**Windows, easiest:** drag your video onto `Make Clips.bat`.

**Any computer:**

```bash
python clipper.py show.mp4
```

The first run downloads the speech model (a few hundred MB) and takes a while on a long video. The transcript is saved as `show.transcript.json`, so every run after that starts straight away.

### Options

| Option | What it does |
|---|---|
| `--count 10` | Pick 10 clips instead of 5 |
| `--min 15 --max 45` | Shortest and longest clip, in seconds |
| `--layout fit` | Show the whole picture on a blurred background instead of zooming in. Good for screen shares and wide shots |
| `--no-captions` | Leave the captions off |
| `--model medium` | A more accurate transcript, slower. Choices: `tiny`, `base`, `small` (default), `medium`, `large-v3` |
| `--out clips` | Save to a different folder |

### Fix a cut

Every run writes `output/<video> clips.txt`:

```
0:16.5,1:05.1,Then something crazy happened
1:05.9,2:00.7,Stop doing what everyone else does
```

Change a time or a title, delete lines you don't want, then run:

```bash
python clipper.py show.mp4 --clips "output/show clips.txt"
```

You can also write the file yourself (see `clips.txt`). Times can be seconds (`95`) or minutes:seconds (`1:35`).

### Let Claude pick the moments (optional)

The built-in picker looks for fast, punchy stretches that start and end on a full sentence. For better picks, set an Anthropic API key and Claude reads the transcript and chooses the moments most likely to work as a standalone clip:

```bash
# Mac / Linux
export ANTHROPIC_API_KEY=sk-ant-...
# Windows
set ANTHROPIC_API_KEY=sk-ant-...

python clipper.py show.mp4
```

Only the transcript text is sent, never the video. If the key is missing or the call fails, the built-in picker is used. Add `--no-ai` to skip Claude even when a key is set.

## Requirements

- Python 3.10+
- ffmpeg
- `faster-whisper` (transcript), `anthropic` (optional Claude picker)

Video files, transcripts and generated clips are not tracked in this repository.
