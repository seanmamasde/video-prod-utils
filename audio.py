import argparse
from pathlib import Path

from utils import cli, new_output, run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--denoise", type=float, default=0, metavar="DB", help="0=off; try 12 dB")
    parser.add_argument("--noise-floor", type=float, default=-50, metavar="DB", help="afftdn floor, -80 to -20")
    parser.add_argument("--audio-track", type=int, default=0, help="audio stream index, starting at 0")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args(argv)
    if not (0 <= args.denoise <= 97 and -80 <= args.noise_floor <= -20) or args.audio_track < 0:
        parser.error("Use --denoise 0..97, --noise-floor -80..-20, and a nonnegative audio track.")

    # fill timestamp gaps + denoise
    filters = ["aresample=async=1:first_pts=0"]
    if args.denoise:
        filters.append(f"afftdn=nr={args.denoise}:nf={args.noise_floor}:tn=1")
    with new_output(args.output, (".wav",)) as work:
        command = [args.ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin", "-n",
                   "-i", args.input.resolve(), "-map", f"0:a:{args.audio_track}", "-vn"]
        if args.seconds is not None:
            command += ["-t", args.seconds]
        # export 48 kHz/24-bit PCM
        run(command + ["-af", ",".join(filters), "-ar", "48000", "-c:a", "pcm_s24le", "-rf64", "auto", work])


if __name__ == "__main__":
    cli(main)
