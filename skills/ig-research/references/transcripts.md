# Transcripts of the picked Reels

Only for the Reels the person picked to study (at most 10), never the whole search. Transcripts go next to the CSV, in `research-<idea>-<date>-transcripts/` (called `<transcripts>` below).

## Setup, once

Transcription runs on this computer with NVIDIA's Parakeet TDT 0.6B v3 model through FluidAudio, so nothing is uploaded and it costs nothing. It needs macOS on Apple Silicon:

1. ffmpeg: `brew install ffmpeg`.
2. FluidAudio's command-line tool, built from source (Xcode command-line tools needed):

       git clone https://github.com/FluidInference/FluidAudio.git ~/.local/share/fluidaudio
       cd ~/.local/share/fluidaudio && swift build -c release

   The first transcription downloads the model.
3. Put `~/.local/share/fluidaudio/.build/release` on the PATH, or set `IG_RESEARCH_PARAKEET_CLI` to the `fluidaudiocli` file there.

If this isn't set up and the person doesn't want to set it up, say transcripts aren't available here; the rest of the skill doesn't need them.

## Run

This downloads one file, so the person's request has to cover it. Asking for the transcripts does. If they didn't ask, say what will be saved (one archive of the picked Reels' audio, about 7 KB per second of video, deleted after) and wait for their yes.

In the signed-in tab (any instagram.com page; step 4's tab will do), check `typeof window.__igaudio` first: `"object"` means it is already loaded from an earlier run with no navigation since, so send only the `start` line below. Otherwise read `<skill>/scripts/instagram-audio.js` and send its **entire text** as one JavaScript call, ending with

    __igaudio.start({codes: ["<code>", ...]})

then call `await __igaudio.wait(25000)` until `done`. It looks each Reel up, paced, fetches the audio-only track the page itself streams, and has the browser save them all as one archive, `ig-research-audio-<id>.tar`, in Downloads. Then:

    python3 -I -B <skill>/scripts/transcribe.py \
      --archive ~/Downloads/<archive name from the result> --out <transcripts>

It moves the archive out of Downloads, transcribes each Reel (about a second per minute of audio), writes `<code>.md`, and deletes the archive and all audio. If Instagram pushes back, stop.

## Into the report

Run the report again with the same arguments plus `--transcripts <transcripts>`. It renames each transcript from its bare code to `<creator> - <platform> - <opening line> (<code>).md` and gives it a heading with the post date and views. The code stays in brackets because that's how the report matches a transcript to its row, so re-running is safe. Each candidate's transcript then sits under its stats in `research-<idea>-<date>-candidates.md`, next to the CSV, and in the printed output. Show that section. Machine transcripts mishear names: if a tool name looks wrong (for example "cloud code" for Claude Code), say so rather than silently fixing it.
