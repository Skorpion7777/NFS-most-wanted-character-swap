import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

# Do not override credentials already set in Colab.
load_dotenv(override=False)

import higgsfield_client


MODEL = "bytedance/seedance-2.5/video-edit"
CONTENT_DIR = Path(__file__).resolve().parent / "content"

PROMPT = """
Use the supplied video as the source to edit, not merely as
inspiration. Reproduce it as closely as possible.

Reference assignment:
- The source video is the original video to edit.
- The first image reference is the replacement character.
- The second image reference is the replacement car: a Fiat 500.

Make only these changes:

1. Replace the original main character with the character from the first
image reference. Match that character's identity and appearance while
preserving the original character's actions, poses, expressions, screen
position, movement, and interaction with the scene.

2. Replace the original car with the Fiat 500 from the second image
reference. Match the supplied car's appearance, color, body shape, and
visible details. Preserve the original car's placement, orientation,
movement, timing, and interaction with the character. Adapt perspective,
lighting, reflections, shadows, and occlusion to the original scene.

3. Remove ALL visible text throughout the entire video. This includes
titles, subtitles, captions, credits, names, labels, signs, logos with
lettering, interface text, and any other
readable letters or numbers, whether in the scene or overlaid on it.
Do not replace text with new text. Do not generate any words, letters, digits,
watermarks, or captions. Cleanly reconstruct the background or surface
behind each removed text element so nothing readable remains in any frame.
Preserve the surrounding objects, colors, motion, and visual style.

Except for the character, car, and removal of all visible text, keep the
video as close to the original as possible. Preserve shot order, cuts,
camera movement, framing, pacing, backgrounds, lighting, visual style,
and all other objects. Do not add scenes, objects, captions,
effects, or creative reinterpretations. Just perform the specified swaps.
""".strip()


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Edit a source video to swap a character, car, and text using Seedance 2.5. "
            "Output resolution is locked to 480p."
        )
    )

    parser.add_argument(
        "--video",
        default=str(CONTENT_DIR / "original.mp4"),
        help="Path to the original video.",
    )
    parser.add_argument(
        "--character",
        default=str(CONTENT_DIR / "basti.jpg"),
        help="Path to the character image.",
    )
    parser.add_argument(
        "--car",
        default=str(CONTENT_DIR / "fiat500.jpg"),
        help="Path to the Fiat 500 image.",
    )

    parser.add_argument(
        "--duration",
        type=int,
        help="Trim the source video to this many seconds before uploading (4 to 30).",
    )
    parser.add_argument(
        "--resolution",
        choices=["480p"],
        default="480p",
        help="Only 480p is permitted.",
    )
    parser.add_argument(
        "--generate-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--output",
        default="swapped_video_480p.mp4",
    )
    parser.add_argument(
        "--resume",
        metavar="REQUEST_ID",
        help="Retrieve an existing request instead of submitting another.",
    )

    args = parser.parse_args()

    if not args.resume:
        if args.duration is not None and not 4 <= args.duration <= 30:
            parser.error("--duration must be between 4 and 30")

        for name in ("video", "character", "car"):
            path = Path(getattr(args, name)).expanduser().resolve()

            if not path.is_file():
                parser.error(f"File not found: {path}")

            if path.stat().st_size == 0:
                parser.error(f"File is empty: {path}")

            setattr(args, name, path)

    return args


def check_credentials():
    combined = os.environ.get("HF_KEY")

    if combined:
        key_id, separator, key_secret = combined.partition(":")
        if not separator or not key_id.strip() or not key_secret.strip():
            raise RuntimeError(
                "HF_KEY must contain both credentials in the format "
                "KEY_ID:KEY_SECRET."
            )
        return

    if (
        os.environ.get("HF_API_KEY")
        and os.environ.get("HF_API_SECRET")
    ):
        return

    raise RuntimeError(
        "Missing API credentials. Set HF_KEY=KEY_ID:KEY_SECRET "
        "in the Colab environment or a .env file."
    )


def save_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def upload_reference(path, label):
    print(f"Uploading {label}: {path.name}", flush=True)

    url = higgsfield_client.upload_file(str(path))

    if not isinstance(url, str):
        raise RuntimeError(
            f"{label} upload returned {type(url).__name__}, "
            "not the expected URL string."
        )

    parsed = urlparse(url)

    # Avoid printing full signed URLs.
    print(
        f"{label} reference: scheme={parsed.scheme}, "
        f"host={parsed.netloc}",
        flush=True,
    )

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError(
            f"{label} upload did not return an HTTP(S) URL. "
            "The video-edit endpoint requires accessible "
            "media URLs and does not accept asset:// references."
        )

    return url


def prepare_video(video, duration, temporary_folder):
    """Trim before upload: video-edit derives its length from the source."""
    if duration is None:
        return video

    trimmed = Path(temporary_folder) / "source.mp4"
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", str(video), "-t", str(duration),
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-movflags", "+faststart", str(trimmed),
    ]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg is required for --duration (available in Colab).") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Could not trim the source video with ffmpeg.") from exc

    # A short input cannot be stretched by -t; reject it before a paid request.
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(trimmed)],
            check=True, capture_output=True, text=True,
        )
        actual_duration = float(probe.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
        raise RuntimeError("Could not verify the trimmed video's duration.") from exc
    if actual_duration < duration - 0.1:
        raise RuntimeError(
            f"The source video is too short for --duration {duration} "
            f"(trimmed length: {actual_duration:.2f}s)."
        )
    print(f"Prepared {actual_duration:.2f}s source clip", flush=True)
    return trimmed


def download_video(url, output):
    temporary = output.with_suffix(output.suffix + ".part")

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(30, 300),
        ) as response:
            response.raise_for_status()

            with temporary.open("wb") as file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)

        if temporary.stat().st_size == 0:
            raise RuntimeError("The downloaded video is empty.")

        temporary.replace(output)

    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main():
    args = parse_args()
    check_credentials()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    request_file = output.with_suffix(".request.json")
    result_file = output.with_suffix(".result.json")

    if output.exists():
        raise FileExistsError(
            f"Output already exists: {output}. "
            "Choose a different --output filename."
        )

    if args.resume:
        print(
            f"Retrieving existing request: {args.resume}",
            flush=True,
        )
        result = higgsfield_client.result(
            request_id=args.resume
        )

    else:
        # Prevent accidentally submitting twice with the same output name.
        if request_file.exists():
            previous = json.loads(
                request_file.read_text(encoding="utf-8")
            )
            previous_id = previous.get("request_id", "unknown")

            raise RuntimeError(
                f"A saved request already exists: {previous_id}. "
                "Use --resume REQUEST_ID to retrieve it. "
                "For an intentional new generation, choose a different "
                "--output filename."
            )

        with tempfile.TemporaryDirectory() as temporary_folder:
            source = prepare_video(args.video, args.duration, temporary_folder)
            video_url = upload_reference(source, "video")
        character_url = upload_reference(args.character, "character")
        car_url = upload_reference(args.car, "car")

        arguments = {
            "prompt": PROMPT,
            "video_url": video_url,
            "image_urls": [character_url, car_url],
            "resolution": "480p",
            "generate_audio": args.generate_audio,
        }

        def on_enqueue(request_id):
            save_json(
                request_file,
                {
                    "request_id": request_id,
                    "model": MODEL,
                    "resolution": "480p",
                },
            )

            print(f"Request ID: {request_id}", flush=True)
            print(
                "Request ID saved. If interrupted, resume this request "
                "rather than submitting another.",
                flush=True,
            )

        def on_queue_update(status):
            print(
                f"Status: {type(status).__name__}",
                flush=True,
            )

        print(
            "Submitting generation with resolution=480p...",
            flush=True,
        )

        result = higgsfield_client.subscribe(
            MODEL,
            arguments=arguments,
            on_enqueue=on_enqueue,
            on_queue_update=on_queue_update,
        )

    # Save the response before validating it.
    save_json(result_file, result)

    if not isinstance(result, dict):
        raise RuntimeError(
            f"Unexpected response type: {type(result).__name__}. "
            f"Inspect {result_file.name}."
        )

    status = str(result.get("status", "")).lower()

    if status in {"failed", "error", "cancelled", "canceled"}:
        error = result.get("error") or result.get("message")
        request_id = result.get("request_id") or args.resume

        raise RuntimeError(
            f"Higgsfield request {status}. "
            f"Request ID: {request_id or 'not provided'}. "
            f"Details: {error or 'No error details returned'}. "
            f"Full response saved to {result_file.name}."
        )

    video = result.get("video")
    video_url = video.get("url") if isinstance(video, dict) else None

    if not video_url:
        raise RuntimeError(
            "The response does not contain video.url. "
            f"Returned status: {status or 'not provided'}. "
            f"Inspect {result_file.name}. "
            "Do not submit another generation without checking "
            "the saved response."
        )

    print("Downloading generated video...", flush=True)
    download_video(video_url, output)
    print(f"Saved: {output}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\nInterrupted locally. A submitted request may still "
            "be running. Use its saved request ID to resume.",
            file=sys.stderr,
        )
        sys.exit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
