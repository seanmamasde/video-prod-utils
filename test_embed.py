"""Small FFmpeg check: uv run python test_embed.py (no GPU required)."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from embed import main
from utils import run


def check():
    with tempfile.TemporaryDirectory(prefix="embed [test], '\u5b57\u5e55-", dir=Path(__file__).parent) as directory:
        root = Path(directory)
        source, srt = root / "input.mp4", root / "captions ' [1],.srt"
        run(["ffmpeg", "-hide_banner", "-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i",
             "color=c=black:s=320x180:r=10:d=2", "-f", "lavfi", "-i", "sine=duration=2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", source])
        srt.write_text("\ufeff1\n00:00:00,100 --> 00:00:00,800\n\u7e41\u9ad4 Whisper\n", encoding="utf-8")
        before = srt.read_bytes()
        # Exercise a relative executable path even when the subprocess working directory changes.
        ffmpeg = shutil.which("ffmpeg")
        if os.path.splitdrive(ffmpeg)[0].lower() == os.path.splitdrive(os.getcwd())[0].lower():
            ffmpeg = os.path.relpath(ffmpeg)
        for suffix, subtitle_codec in ((".mp4", "mov_text"), (".mkv", "subrip")):
            for mode in ("soft", "hard"):
                output = root / (mode + suffix)
                args = [str(source), "--srt", str(srt), "-o", str(output), "--ffmpeg", ffmpeg]
                # No --mode for MP4/soft: verify the original command still works unchanged.
                main(args + (["--mode", mode] if mode == "hard" or suffix == ".mkv" else []))
                info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                                                           "-show_format", "-of", "json", str(output)]))
                assert [s["codec_name"] for s in info["streams"]] == (
                    ["h264", "aac", subtitle_codec] if mode == "soft" else ["h264", "aac"])
                assert float(info["format"]["duration"]) >= 2
                pixels = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", "0.4", "-i", str(output),
                                                  "-map", "0:v:0", "-frames:v", "1", "-pix_fmt", "gray",
                                                  "-f", "rawvideo", "-"])
                assert max(pixels) < 10 if mode == "soft" else max(pixels) > 200
                try:
                    main(args + ["--mode", mode])
                except FileExistsError:
                    pass
                else:
                    raise AssertionError("Existing output was not protected")
        # A failed encoder/tool invocation must not leave an apparently finished file.
        failed = root / "failed.mp4"
        try:
            main([str(source), "--srt", str(srt), "-o", str(failed), "--mode", "hard",
                  "--ffmpeg", str(root / "missing-ffmpeg.exe")])
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("Missing FFmpeg was not rejected")
        assert not failed.exists() and srt.read_bytes() == before
        assert not list(root.glob("video-*")), "Temporary output was not cleaned up"
    print("PASS: default/explicit soft and hard, MP4/MKV, rendered text, Unicode/quoted paths, "
          "relative executable, full duration, and file safety.")


if __name__ == "__main__":
    check()
