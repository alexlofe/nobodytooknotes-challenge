# The Nobody Took Notes Challenge

Welcome. In this challenge you will add local AI to a real desktop app.

**Nobody Took Notes** is a meeting notetaker for macOS. It records a call,
writes down what everyone says, and then writes a summary. Everything runs on
your own computer. No cloud, no account, no data leaves your Mac.

The app in this repository is almost complete. The user interface, the audio
recording, the database and the web server all work. **The AI parts are
missing.** Your job is to add them using the [NobodyWho](https://nobodywho.ooo)
library.

When you finish, the app will:

1. Listen to a meeting and transcribe it live (speech to text).
2. Write a structured summary with a local language model (LLM).

## What you will learn

- How to run a speech-to-text model (Whisper) on your own machine.
- How to run a small language model (Qwen3) on your own machine.
- How to force a language model to answer in a fixed JSON format.
- How to connect AI code to an existing application.

## How the challenge is organised

The work is split into steps. Each step has:

- **Goal:** what you must achieve.
- **Where:** which file and function to edit.
- **Checkpoint:** a command you run to check that the step works.

Do the steps in order. Each step builds on the one before.

Only **three files** need changes. Everything else is already done.

| File                   | What you add there                        | Step |
| ---------------------- | ----------------------------------------- | ---- |
| `nobody/stt.py`        | Speech to text (file and live audio)      | 2, 3 |
| `nobody/summarise.py`  | Summary generation with a language model  | 4    |
| `nobody/setup.py`      | Downloading the models on first run       | 5    |

Each place that needs your code is marked with a `TODO` comment and raises
`NotImplementedError` with the step number. If you see that error, you have
found a part that is still missing.

## Before you start

You need:

- A Mac with **macOS 14.2 or newer**. (The app uses a macOS feature to record
  system audio.)
- **Python 3.11 or newer.** Check with `python3 --version`.
- **Homebrew** and **ffmpeg**. Install ffmpeg with `brew install ffmpeg`.
- About **1 GB of free disk space** for the two AI models.
- An internet connection for the first run. After the models are downloaded,
  the app works offline.

---

## Step 0: Set up and run the app

**Goal:** run the app and see the user interface, even though the AI parts do
not work yet.

Open a terminal in this folder and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[macos,server]"
```

Now start the app:

```bash
python -m nobody serve
```

A small icon appears in the menu bar at the top of your screen. Your browser
opens the app at `http://127.0.0.1:8765`.

Try it:

1. Click the menu bar icon and choose **Start Recording**. macOS will ask for
   microphone and screen recording permissions. Allow both.
2. Talk for a few seconds.
3. Choose **Stop Recording**.

**Checkpoint:** the recording works and a new meeting appears in the web
interface, but the transcript is empty. In the terminal you will see a
`NotImplementedError` that mentions step 3. That is expected. You will fix it.

Press `Ctrl+C` in the terminal to stop the app.

---

## Step 1: Meet NobodyWho

**Goal:** understand the library before writing app code.

NobodyWho is a Python library that runs AI models locally. It was installed in
step 0 as a dependency. Check that it is there:

```bash
python -c "import nobodywho; print('ok')"
```

Now open the documentation and keep it open while you work:

- Main docs: https://docs.nobodywho.ooo/docs/
- A short index of all pages: https://docs.nobodywho.ooo/llms.txt

Read the pages about **speech to text** and **chat** for Python. You do not
need to understand everything. Look for:

- The class that does speech to text, and what arguments it takes.
- The class that does chat with a language model.
- What `.ask()` returns, and how to get the complete text from it.
- How to make the model answer with a JSON schema. (Search for "structured
  output" or "json schema".)

Try a small experiment in Python. Create a file `experiment.py`:

```python
from nobodywho import Chat

chat = Chat("huggingface:NobodyWho/Qwen_Qwen3-0.6B-GGUF/Qwen_Qwen3-0.6B-Q4_K_M.gguf")
answer = chat.ask("Say hello in three languages.").completed()
print(answer)
```

Run it with `python experiment.py`. The first run downloads the model
(about 600 MB), so it takes a while. The second run is fast.

**Checkpoint:** you see a greeting printed in the terminal.

You can delete `experiment.py` when you are done, or keep it for more tests.

---

## Step 2: Transcribe an audio file

**Goal:** turn a WAV file into text.

**Where:** `nobody/stt.py`, the functions `create_stt`, `transcribe_file`
and `transcribe_file_streaming`.

First, you need a test recording. The app can make one for you:

```bash
python -m nobody record --duration 10 --output test_audio
```

Speak clearly for ten seconds. This creates `test_audio/me.wav` (your voice)
and `test_audio/them.wav` (system audio, probably empty for this test).

Now open `nobody/stt.py` and read the comments. The three functions are
small. Together they are about ten lines of real code.

Some help:

- `create_stt` must return the NobodyWho speech-to-text object. Pass it the
  model name and the language.
- The speech-to-text object has a method that transcribes a file. That method
  does **not** return a string. It returns a **stream** of text pieces.
- To wait for the whole text as one string, call `.completed()` on the stream.
- To get pieces one by one, use the stream in a `for` loop.

**Checkpoint:**

```bash
python -m nobody transcribe test_audio/me.wav
```

You should see your words appear in the terminal, piece by piece. The first
run downloads the Whisper model (about 40 MB).

<details>
<summary>Extra help if you are stuck</summary>

The class is called `SpeechToText`. Its constructor is
`SpeechToText(source=..., language=...)`. The file method is
`transcribe_file(path)`. Both `transcribe_file` and `transcribe_pcm` return a
`TokenStream`, which has `.completed()` and also works in a `for` loop.
</details>

---

## Step 3: Live transcription

**Goal:** transcribe audio while the meeting is happening.

**Where:** `nobody/stt.py`, the function `transcribe_pcm`.

During a meeting, the app does not have a file. It has raw audio samples in
memory. Look at `nobody/pipeline.py` around the function `_worker_loop` to
see how the app calls your code. You do not need to change `pipeline.py`.

The pipeline gives your function three things:

- `stt`: the object you created in `create_stt`.
- `samples`: a Python list of integers. Each integer is one audio sample.
- `sample_rate`: the number of samples per second. It is always 48000 here.

Your function must return the recognised text as a string.

Some help:

- The speech-to-text object has a **second** transcribe method made for raw
  samples. It takes the samples and the sample rate.
- Like in step 2, it returns a stream. Wait for the complete text.

**Checkpoint 1 (terminal):**

```bash
python -m nobody live --duration 20
```

Speak for twenty seconds. Lines of text should appear while you talk. At the
end you see a session ID. Show the saved transcript with:

```bash
python -m nobody show <first letters of the session id>
```

**Checkpoint 2 (web interface):** run `python -m nobody serve`, start a
recording from the menu bar, and watch the transcript appear live in the
browser.

Tip: to test the "other side" of a call, play a video or a podcast on your Mac
while recording. Those words should appear as **Guests**.

---

## Step 4: Write the summary

**Goal:** turn a transcript into a structured summary: title, short summary,
key points, decisions, action items and open questions.

**Where:** `nobody/summarise.py`, the methods `_get_chat` and
`_ask_for_summary` in the `Summariser` class, and the import at the top.

Open the file and read it from top to bottom. Most of it is already done:

- `SUMMARY_SCHEMA` describes the JSON the model must produce.
- `SYSTEM_PROMPT` tells the model what its job is.
- `MeetingSummary` is a normal Python class that holds a finished summary.
- `chunk_transcript` splits long transcripts into parts that fit in the model.
- `summarise`, `_summarise_single`, `_summarise_chunked` and
  `_combine_summaries` are written. They all call `_ask_for_summary`.

You only write the two methods that talk to the model.

### 4a: `_get_chat`

Create a NobodyWho `Chat` object and store it in `self._chat`. The chat needs:

- the model name, which is in `self.model`;
- the system prompt, `SYSTEM_PROMPT`;
- the context size, `self.n_ctx`;
- a **sampler** that forces the model to follow `SUMMARY_SCHEMA`.

The sampler is the important part. Without it, the model may answer with
normal text, and the app cannot read it. NobodyWho has a preset that builds a
sampler from a JSON schema. Find it in the docs under structured output.

### 4b: `_ask_for_summary`

This method receives a prompt and must return a `MeetingSummary`. Four steps:

1. Get the chat with `self._get_chat()`.
2. Reset the chat history, so old transcripts do not mix with the new one.
3. Send the prompt and wait for the full answer as a string.
4. The answer is JSON text. Parse it with `json.loads`, then return
   `MeetingSummary.from_dict(data)`.

**Checkpoint 1 (quick test without audio):** create a file `test_summary.py`:

```python
from nobody.summarise import Summariser

transcript = """[Host] Thanks for joining. Today we decide the launch date.
[Guests] We think the first of March is realistic if design is done.
[Host] OK. Let's agree on the first of March. Maria, can you finish the design by the fifteenth?
[Guests] Yes, Maria will send the final design by the fifteenth of February.
[Host] One open question: do we need a Spanish version at launch?
[Guests] We are not sure. We should ask the sales team.
"""

summary = Summariser().summarise(transcript)
print(summary.to_markdown())
```

Run `python test_summary.py`. You should see a Markdown summary with a title,
a decision about the launch date, an action item for Maria, and an open
question about the Spanish version. The exact words will be different each
time. That is normal for a language model.

**Checkpoint 2 (real meeting):** use a session from step 3.

```bash
python -m nobody summarize <session id prefix> --markdown
```

**Checkpoint 3 (web interface):** run `python -m nobody serve`, record a short
meeting, and stop it. The app generates a summary automatically and shows it
in the browser. You can also press the summarise button on an old meeting.

<details>
<summary>Extra help if you are stuck</summary>

The sampler is `SamplerPresets.constrain_with_json_schema(SUMMARY_SCHEMA)`.
Pass it to `Chat(...)` with the `sampler=` keyword argument. The chat has
`.reset_history()`, and `.ask(prompt)` returns a stream with `.completed()`.
</details>

---

## Step 5: First-run setup

**Goal:** make the `setup` command download both models, with a progress bar.

**Where:** `nobody/setup.py`, the function `download_models_with_progress`.

When a new user installs the app, they run `python -m nobody setup` once. It
checks ffmpeg, checks permissions, and downloads the models. The checks are
already written. Only the two downloads are missing.

### 5a: the chat model

NobodyWho has a function that downloads a GGUF model file and calls a progress
callback while it works. Call it with `DEFAULT_CHAT_MODEL` and pass
`chat_progress` as the callback. The code around it already handles errors
and status messages.

### 5b: the Whisper model

Whisper models are not GGUF files, so the function from 5a does not apply.
Instead, simply creating the speech-to-text engine downloads and caches the
model. You already wrote that function in step 2. Call it and ignore the
result.

**Checkpoint:**

```bash
python -m nobody setup
```

You should see both models reported as **ready**. If you delete the model
cache first, you will also see the progress bar. The cache folder is
`~/Library/Caches/nobodywho` on macOS.

<details>
<summary>Extra help if you are stuck</summary>

The download function is `download_model(model_path, on_download_progress=...)`.
For Whisper, call `create_stt(DEFAULT_MODEL)` from `nobody.stt`.
</details>

---

## Step 6: Final check

Run the full flow one more time from a clean start:

```bash
python -m nobody setup
python -m nobody serve
```

1. Start a recording from the menu bar (or press `Cmd+Shift+R`).
2. Play a short video and talk over it.
3. Stop the recording.
4. In the browser: read the live transcript, wait for the summary, edit the
   title, and export the summary as Markdown.

If all of that works, **you have finished the challenge.** Well done.

---

## Going further (optional)

If you want to continue, here are some ideas. Pick any that interest you.

- **A better summary model.** Try a bigger model, for example a 1.7B or 4B
  Qwen3 model from HuggingFace. Compare quality and speed.
- **Other languages.** The app uses `language="en"`. Let the user pick a
  language, or pass `None` to let Whisper detect it.
- **A better speech model.** Try `hf://onnx-community/whisper-base` or
  `whisper-small`. Is the transcript more accurate? How much slower is it?
- **Streaming summaries.** Show the summary in the browser while the model is
  still writing it, instead of waiting for the end.
- **Speaker names.** Ask the user for the names of the people in the call and
  use them instead of "Host" and "Guests".
- **Build the app.** Run `python build.py` to make a standalone macOS app, and
  `python build_dmg.py` to make an installer.

## Common problems

**`NotImplementedError: CHALLENGE step N`**
That part of the code is still empty. Open the file named in the error.

**The first run is very slow.**
Models are downloaded on the first use. The chat model is about 600 MB.
Wait for it to finish. Later runs are fast.

**`json.decoder.JSONDecodeError` in step 4.**
The model did not answer with valid JSON. Check that you passed the JSON
schema sampler to the `Chat`. Without it, the model writes normal text.

**The summary is empty or strange.**
Small models make mistakes. Try a longer transcript, or a bigger model.

**No audio is captured.**
Check System Settings, Privacy & Security. The terminal app (or the built app)
needs Microphone and Screen Recording permission.

**`ffmpeg not found`.**
Run `brew install ffmpeg`.

## Small glossary

- **LLM** (large language model): an AI model that reads and writes text.
- **Whisper**: a family of speech-to-text models made by OpenAI.
- **GGUF**: a file format for language models that run on normal computers.
- **ONNX**: a file format for machine learning models. The Whisper model here
  uses it.
- **Token**: a small piece of text, usually part of a word. Models read and
  write one token at a time.
- **Context window** (`n_ctx`): the maximum number of tokens a model can
  work with at once.
- **Stream**: an answer that arrives piece by piece instead of all at once.
- **Sampler**: the rule the model uses to choose the next token. A JSON
  schema sampler only allows tokens that keep the answer valid JSON.
- **JSON schema**: a description of the exact shape a JSON document must have.
- **PCM**: raw audio, stored as a list of numbers. One number per sample.
- **Sample rate**: how many audio samples there are per second.
