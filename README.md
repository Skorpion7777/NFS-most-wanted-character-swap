# Need for Speed video swap

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
This is the prompt I used in Google Gemini to generate the reference image of my character:

```
Use the uploaded photographs as identity references to create a character version of me in the original visual style of Need for Speed: Most Wanted (2005). Study my facial structure across all reference images and preserve my recognizable identity: face shape, proportions, jawline, cheekbones, nose, eyes, eyebrows, lips, skin tone, and hairstyle. Do not replace my features with a generic game character or exaggerate them.

Translate my real-life appearance into a convincing mid-2000s video-game character render—not a photograph, modern AAA character, cartoon, or illustration. Match the original game’s aesthetic: moderately low-poly geometry, visibly textured skin and clothing, slightly angular contours, baked shading, restrained facial detail, gritty street-racing atmosphere, strong contrast, and muted yellow-green/sepia color grading. The result should feel like an authentic character asset from the 2005 game, not a photorealistic portrait with a filter.

Produce one image arranged as a clean 2×2 character reference sheet with four distinct views:

Front-facing.
Left three-quarter view.
Right three-quarter view.
Exact side profile.
Use consistent chest-up framing, camera distance, lighting, neutral expression, hairstyle, and clothing across all four views. Keep the character’s facial geometry and identity consistent as the angle changes. Use understated street-racing clothing appropriate to the game’s setting, without distracting accessories. Place each view against the same simple, subdued background so the face remains the focal point. Provide them in the original vivid color scheme from the nfs era.

Prioritize recognizable likeness and faithful 2005-era game graphics over beautification or added detail. No text, labels, numbers, logos, watermarks, HUD elements, or interface graphics anywhere in the image. 
```

<img width="2048" height="2048" alt="Basti" src="https://github.com/user-attachments/assets/530cdd8e-bcee-4139-adeb-021929977dc0" />

## Generating the car
This is the prompt I used in Google Gemini to generate the reference image of my car:

```
Generate the fiat 500e in green as a need for speed most wanted (2005) car in that original style. Provide 4 different angles. No writing on the image!
```

<img width="2600" height="1632" alt="Fiat 500" src="https://github.com/user-attachments/assets/9314369a-b536-4674-8ac3-3d8a28ac829f" />


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
