import argparse
import math
import os
from pathlib import Path

from opencc import OpenCC

from utils import cli, new_output, read_srt, run, write_srt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path("models/ggml-large-v3-turbo-q5_0.bin"))
    parser.add_argument("--whisper", default=os.environ.get("WHISPER_CLI", "whisper-cli"))
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--prompt-file", type=Path, help="Short UTF-8 terminology hint, at most 200 characters.")
    parser.add_argument("--device", type=int, default=0, help="Whisper GPU index; backend depends on build.")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--beam-size", type=int, default=5, help="Try 1 for speed, 5 for accuracy.")
    parser.add_argument("--max-len", type=int, default=0, help="Whisper segment limit; 0=native segments.")
    parser.add_argument("--audio-track", type=int, default=0)
    parser.add_argument("--seconds", type=float, help="Only the first N seconds, for a trial.")
    parser.add_argument("--traditional", choices=("s2t", "s2tw", "s2twp"), default="s2twp")
    args = parser.parse_args(argv)
    if min(args.threads, args.beam_size) <= 0 or min(args.device, args.max_len, args.audio_track) < 0:
        parser.error("Threads/beam size must be positive; device/max-len/audio-track must be nonnegative.")
    if args.seconds is not None and (not math.isfinite(args.seconds) or args.seconds <= 0):
        parser.error("--seconds must be positive and finite.")
    if not args.model.is_file():
        parser.error(f"Model not found: {args.model}. See README.md for the download.")
    prompt = args.prompt_file.read_text(encoding="utf-8-sig").strip() if args.prompt_file else ""
    if len(prompt) > 200:
        parser.error("Whisper hint is too long: use at most 200 characters, not the full history.")

    with new_output(args.output, (".srt",)) as work:
        # temp mono 16 kHz PCM to keep initial silence and timeline gap
        wav = work.parent / "audio.wav"
        command = [args.ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin", "-n",
                   "-i", args.input.resolve(), "-map", f"0:a:{args.audio_track}", "-vn"]
        if args.seconds is not None:
            command += ["-t", args.seconds]
        run(command + ["-af", "aresample=async=1:first_pts=0", "-ar", "16000", "-ac", "1",
                       "-c:a", "pcm_s16le", wav])

        # transcribe mandarin, preserving english
        command = [args.whisper, "-m", args.model.resolve(), "-f", wav, "-l", "zh",
                   "-osrt", "-of", work.with_suffix(""), "-t", args.threads,
                   "-bs", args.beam_size, "-bo", args.beam_size, "-ml", args.max_len, "-dev", args.device]
        if args.cpu:
            command += ["--no-gpu"]
        if prompt:
            command += ["--prompt", prompt]
        print("Check the backend/device messages below: use_gpu=1 alone does not prove GPU use.", flush=True)
        run(command)
        if not work.is_file():
            raise ValueError("Whisper produced no SRT. Check its model/backend messages above.")

        # convert text only
        cues = read_srt(work)
        converter = OpenCC(args.traditional)
        for cue in cues:
            cue["text"] = converter.convert(cue["text"])
        write_srt(work, cues)
        if not cues:
            print("Warning: no speech recognized; the SRT is empty.")


if __name__ == "__main__":
    cli(main)
