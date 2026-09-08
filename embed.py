import argparse
from pathlib import Path

from utils import cli, new_output, read_srt, run, write_srt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("soft", "hard"), default="soft")
    parser.add_argument("--encoder", choices=("libx264", "h264_nvenc", "h264_qsv"), default="libx264",
                        help="Hard mode only: CPU (default), NVIDIA, or Intel.")
    parser.add_argument("--quality", type=int, default=19, help="Hard mode only: 1..51; lower is higher quality.")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args(argv)
    cues = read_srt(args.srt)
    if not cues:
        parser.error("Cannot embed an empty SRT.")
    if not 1 <= args.quality <= 51:
        parser.error("--quality must be 1..51.")

    with new_output(args.output, (".mkv", ".mp4")) as work:
        command = [args.ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin", "-n",
                   "-i", args.input.resolve()]
        if args.mode == "soft":
            # copy all video/audio tracks and replace old tracks
            command += ["-i", args.srt.resolve(), "-map", "0:v", "-map", "0:a?", "-map", "1:0",
                        "-c:v", "copy", "-c:s", "mov_text" if work.suffix == ".mp4" else "srt",
                        "-metadata:s:s:0", "language=zho", "-metadata:s:s:0", "title=Traditional Chinese",
                        "-disposition:s:0", "default"]
        else:
            # fixed relative filename
            write_srt(work.parent / "captions.srt", cues)
            quality = {
                "libx264": ["-crf", args.quality],
                "h264_nvenc": ["-preset", "p4", "-rc", "vbr", "-cq", args.quality, "-b:v", "0"],
                "h264_qsv": ["-global_quality", args.quality],
            }[args.encoder]
            command += ["-map", "0:V:0", "-map", "0:a?", "-sn", "-vf",
                        "subtitles=captions.srt:force_style='FontName=Microsoft JhengHei,FontSize=22,Outline=2'",
                        "-c:v", args.encoder, "-pix_fmt", "nv12" if args.encoder == "h264_qsv" else "yuv420p",
                        *quality]
        run(command + ["-c:a", "copy", "-map_metadata", "0", "-map_chapters", "0", work],
            cwd=work.parent if args.mode == "hard" else None)


if __name__ == "__main__":
    cli(main)
