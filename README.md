# higgsfield video swap

Puts your own character and car into a Blacklist scene from *Need for Speed: Most Wanted* (2005), using the Higgsfield API.

This is a swap, not a remake. The scene is passed to Seedance 2.5 (`bytedance/seedance-2.5/video-edit`) as the video to edit, so the model works from the original footage instead of generating a new clip. Only three things change:

1. The main character is replaced with your character.
2. The car is replaced with your car.
3. All visible text is removed.

Everything else (shots, cuts, camera movement, timing, lighting) stays as close to the original as possible. Output is 480p.

## Requirements

- Python 3.9+
- `pip install -r requirements.txt`
- `ffmpeg` / `ffprobe` on `PATH` (only needed for `--duration`)
- A Higgsfield API key ID and secret

## Setup

Put your credentials in a `.env` file or set them as environment variables:

```
HF_KEY=KEY_ID:KEY_SECRET
```

`HF_API_KEY` + `HF_API_SECRET` also work.

## Generating the character

## Generating the car

## Usage

Inputs live in `content/`:

```
content/
├── original.mp4   # NFS Most Wanted Blacklist scene
├── basti.jpg      # replacement character
└── fiat500.jpg    # replacement car
```

With those files in place, this is all you need:

```bash
python swap_video.py --output outputs/result.mp4
```

To use other inputs, pass them explicitly:

```bash
python swap_video.py \
  --video content/other.mp4 \
  --character content/someone.jpg \
  --car content/car.jpg \
  --output outputs/result.mp4
```

| Flag | Description |
|---|---|
| `--video` | Source video to edit (default `content/original.mp4`) |
| `--character` | Image of the replacement character (default `content/basti.jpg`) |
| `--car` | Image of the replacement car (default `content/fiat500.jpg`) |
| `--output` | Output path (default `swapped_video_480p.mp4`) |
| `--duration N` | Trim the source to N seconds (4–30) before uploading |
| `--no-generate-audio` | Turn off audio generation (on by default) |
| `--resume REQUEST_ID` | Fetch the result of a request you already submitted |

The script writes two files next to the output:

- `<output>.request.json`: the request ID, saved as soon as the job is queued
- `<output>.result.json`: the raw API response

## Avoiding duplicate charges

Every submission is a paid generation, so the script refuses to:

- overwrite an existing output file
- submit again when a `.request.json` already exists for that output name

If a run gets interrupted, don't resubmit. Resume it instead:

```bash
python swap_video.py --resume <REQUEST_ID> --output outputs/result.mp4
```

To start a new generation on purpose, pick a new `--output` name.

## Google Colab

[`swap_video.ipynb`](swap_video.ipynb) mounts Google Drive, reads the inputs from `MyDrive/higgsfield/content/`, asks for your credentials with `getpass` and runs the script.

## Notes

- The prompt is hardcoded in `swap_video.py` and expects a Fiat 500 as the car. Edit `PROMPT` if you use another car.
- Output length follows the source video. The API caps it at 30 seconds.
- The endpoint needs HTTP(S) media URLs. `asset://` references are rejected.
