# Clipper

Cuts one long video into several short clips automatically.

You write the start time, end time, and title of each clip in a text file. The script does the rest.

Built to solve a real problem: cutting clips by hand takes minutes each. At 50 clips, that is a full day of repetitive work. This makes it one command.

## What it does

- Reads a list of clips from `clips.txt`
- Cuts each one from the source video using ffmpeg
- Re-encodes to H.264 + AAC so the clips play everywhere
- Names each file automatically and puts them in an `output` folder

## Requirements

- Python 3
- ffmpeg

No installation needed if you place an `ffmpeg` binary in the same folder — the script will find and use it.

## How to use

**1. Put your video in the folder** and name it `show.mp4`

**2. Write your clips in `clips.txt`**, one per line:

```
5,25,First clip
30,55,Second clip
```

The format is `start,end,title`. Times are in seconds.

**3. Run it:**

```bash
python3 make_clips.py show.mp4
```

Your clips appear in the `output` folder.

## Finding the length of your video

```bash
ffmpeg -i show.mp4 2>&1 | grep Duration
```

## Roadmap

- [x] Cut clips from manual timestamps
- [ ] Generate the transcript automatically (Deepgram)
- [ ] Let AI suggest the clip boundaries
- [ ] Vertical crop and burned-in captions for Shorts

## Notes

Video files and generated clips are not tracked in this repository.
