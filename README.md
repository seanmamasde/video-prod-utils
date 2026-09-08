# Video Production Utilities

small, standalone Windows video/subtitle commands.

|     Script      | Job                                       |
| :-------------: | ----------------------------------------- |
|   `audio.py`    | extract `WAV` from video and reduce noise |
| `transcribe.py` | transcribe media to `zh:tw` `SRT` file    |
|   `embed.py`    | add subs to video                         |


For options, use `--help`, for example `uv run python transcribe.py --help`.

## File Safety

- Every utility requires an explicit `-o` output with a fresh filename.
- Existing files are never overwritten. Output folders such as `out/` are created automatically.
- All text inputs support UTF-8 and UTF-8 with BOM. Convert legacy encodings to
  UTF-8 in your editor first. Generated text is UTF-8.
- Keep original recordings and manual subtitles. Review generated text against
  the audio before publishing; valid JSON/SRT does not prove correct wording.

## Windows Setup

64-bit Windows + PowerShell (7 recommended), and [Scoop](https://scoop.sh/).

```powershell
git clone https://github.com/seanmamasde/video-prod-utils
cd path/to/video-prod-utils
```

Install missing tools in scoop:

```powershell
scoop bucket add extras
scoop install ffmpeg uv whisper-cpp
uv sync --python 3.11
whisper-cli --version
```

`transcribe.py` uses `whisper-cli` on PATH unless `WHISPER_CLI` or `--whisper`
specifies another executable. For GPU acceleration, follow [GPU Build](#gpu-build);
`--device 0` doesn't add GPU support to a CPU-only executable.

### Whisper Model

Download the default multilingual Whisper model for once.

```powershell
New-Item -ItemType Directory -Force -Path '.\models' | Out-Null
$model = '.\models\ggml-large-v3-turbo-q5_0.bin'
if (Test-Path -LiteralPath $model) { throw 'Model exists; skip download and verify below.' }
curl.exe --fail --location --output "$model.part" 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin'
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
if ((Get-Item -LiteralPath "$model.part").Length -ne 574041195 -or
    (Get-FileHash -Algorithm SHA256 -LiteralPath "$model.part").Hash -ne
    '394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2') { throw 'Model size or hash mismatch.' }
Move-Item -LiteralPath "$model.part" -Destination $model
```

## Workflow

Replace `data/recording.mp4` with your recording and `data/history/` with a folder
of previous manually corrected SRTs. Correction is optional; use fresh output names for reruns.

### 0. Denoise Audio (optional; doesn't remove echo)

```powershell
uv run python audio.py '.\data\edited.mp4' -o '.\out\edit-audio-denoised.wav' --denoise 12 --noise-floor -50
```

### 1. Edit Externally

Edit in your video editor w/ the denoised audio, export as `data/edited.mp4`.

### 2. Transcribe

Transcribe the edited timeline using your selected Whisper executable:

```powershell
uv run python transcribe.py '.\data\edited.mp4' -o '.\out\raw.srt'
```

Whisper receives temporary 16 kHz mono audio with timeline gaps preserved. Mandarin
(`zh`) transcription does not request English translation. `--cpu` to not use gpu.

Optionally prepare a short (~200 toks) `out/whisper-hint.txt` and append
`--prompt-file '.\out\whisper-hint.txt'`. OpenCC defaults to `--traditional s2twp`.

### 3. Correct SRT

provide your previous correct srts to either claude or chat jippty (upload them as project files or sum idk, preferrably of the the same video topic/situation as the current one), and upload the current srt, tell it to fix wordings or special terms/phrases. 

### 4. Embed Subtitles

```powershell
# defaults to soft mode; mp4 or mkv
uv run python embed.py '.\data\edited.mp4' --srt '.\out\corrected.srt' -o '.\out\subtitled.mkv'
uv run python embed.py '.\data\edited.mp4' --srt '.\out\corrected.srt' -o '.\out\subtitled.mp4'

# hard mode, CPU encoding
uv run python embed.py '.\data\edited.mp4' --srt '.\out\corrected.srt' -o '.\out\burned.mp4' --mode hard

# hard mode, NVIDIA GPU encoding; use h264_qsv instead for Intel Quick Sync
uv run python embed.py '.\data\edited.mp4' --srt '.\out\corrected.srt' -o '.\out\burned-gpu.mp4' --mode hard --encoder h264_nvenc
```

<details>
<summary>optional gpu build (much faster tho)</summary>

Follow the [upstream build instructions](https://github.com/ggml-org/whisper.cpp/blob/v1.9.2/README.md).
Install Git, CMake 3.24+, Ninja, Visual Studio C++ tools and Windows SDK. Run from
the repo root in x64 developer PowerShell with compiler/CMake/Ninja on PATH.

```powershell
New-Item -ItemType Directory -Force -Path '.\tools' | Out-Null
git clone --depth 1 --branch v1.9.2 https://github.com/ggml-org/whisper.cpp.git '.\tools\whisper-upstream-v1.9.2'
```

For NVIDIA, install a compatible driver and CUDA Toolkit: **CUDA 12.8+ for Blackwell**.
Select an MSVC toolset supported by your CUDA version and put `nvcc` on PATH.
This build targets the GPU on the build computer with `native`:

```powershell
cmake -S '.\tools\whisper-upstream-v1.9.2' -B '.\tools\whisper-build-cuda' -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=native
cmake --build '.\tools\whisper-build-cuda' --config Release --target whisper-cli --parallel 8
$env:WHISPER_CLI = (Resolve-Path '.\tools\whisper-build-cuda\bin\whisper-cli.exe').Path
```

For Intel/AMD GPU deployment, install the [Vulkan SDK](https://vulkan.lunarg.com/)
and a GPU driver with Vulkan support. The [official v1.9.2 release](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.9.2) does **not** provide a Windows Vulkan bundle; a helper must build upstream:

```powershell
cmake -S '.\tools\whisper-upstream-v1.9.2' -B '.\tools\whisper-build-vulkan' -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=ON
cmake --build '.\tools\whisper-build-vulkan' --config Release --target whisper-cli --parallel 8
$env:WHISPER_CLI = (Resolve-Path '.\tools\whisper-build-vulkan\bin\whisper-cli.exe').Path
```

Deploy the **full matching runtime bundle**, not just the executable: Whisper/GGML/
backend DLLs, required CUDA runtimes, and x64 MSVC redistributable as applicable.
Install a compatible NVIDIA driver for CUDA or the target's Vulkan driver/runtime.
Do not mix backend bundles or assume a native CUDA build supports other GPU models.
Set `WHISPER_CLI` again in each new PowerShell session, or pass the executable path
with `--whisper`. Verify that transcription logs identify the GPU backend and model
allocation; `use_gpu=1` alone does not prove GPU use.
</details>
