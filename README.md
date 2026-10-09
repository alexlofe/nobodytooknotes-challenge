# Nobody Took Notes: the challenge edition

This is a teaching version of [Nobody Took Notes](https://github.com/alexlofe/nobodytooknotes),
a free, fully local meeting notetaker for macOS. It records both sides of any
call, transcribes the audio with AI, and writes a summary. No cloud, no
subscriptions, no data leaves your Mac.

**In this version the AI parts have been removed on purpose.** The user
interface, audio capture, database and web server are complete. The speech-to-
text and summary code is left as empty functions with comments. Your task is
to implement them with the [NobodyWho](https://nobodywho.ooo) library.

**Start here: [CHALLENGE.md](CHALLENGE.md).** It explains the steps, where to
write code, and how to test each step.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[macos,server]"
python -m nobody serve
```

The app runs in the menu bar and opens a web interface in your browser.
Recording works right away. Transcription and summaries will work once you
complete the challenge.

## Requirements

- macOS 14.2 or later (needed for system audio capture)
- Python 3.11 or later
- ffmpeg, installed with `brew install ffmpeg`
- About 1 GB of disk space for the AI models

## What is in the repository

```
nobody/
  __main__.py      command line interface (serve, live, record, transcribe, summarize, setup)
  server.py        FastAPI web server and REST API
  ui/index.html    the web interface
  tray.py          menu bar icon and global hotkey
  capture/         microphone and system audio capture (macOS)
  segment.py       cuts live audio into short segments for transcription
  pipeline.py      connects capture, segmentation, transcription and storage
  store.py         SQLite database for sessions, transcripts and summaries
  stt.py           speech to text        <- challenge, steps 2 and 3
  summarise.py     summary generation    <- challenge, step 4
  setup.py         first-run setup       <- challenge, step 5
build.py           builds a standalone macOS app with PyInstaller
build_dmg.py       packages the app as a DMG installer
```

## Command line

```bash
python -m nobody serve                     # run the app with menu bar icon and web UI
python -m nobody record -d 10 -o out       # record 10 seconds of mic and system audio to WAV files
python -m nobody transcribe file.wav       # transcribe an audio file (needs step 2)
python -m nobody live -d 30                # live transcription in the terminal (needs step 3)
python -m nobody show <session id>         # print a saved transcript
python -m nobody summarize <session id>    # summarise a saved transcript (needs step 4)
python -m nobody setup                     # check permissions and download models (needs step 5)
```

## Troubleshooting

**No system audio is captured.**
Open System Settings, then Privacy & Security, then Screen Recording. Enable
your terminal app (or the built app) and restart it.

**The microphone does not work.**
Open System Settings, then Privacy & Security, then Microphone. Enable your
terminal app.

**Audio export does not work.**
Install ffmpeg with `brew install ffmpeg`.

**My voice sounds bad but others sound fine.**
Bluetooth headphones with a built-in microphone use a low-quality audio
profile. Use wired headphones, or use your Mac's built-in microphone.

## Privacy

- All transcription and summarisation runs locally on your Mac.
- No internet connection is needed after the models are downloaded.
- No accounts, no sign-ups, no data collection.

## License

MIT
