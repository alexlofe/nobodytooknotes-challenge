"""Speech-to-text transcription.

CHALLENGE: this file is part of the open challenge. See CHALLENGE.md, steps 2 and 3.

All speech-to-text code for the app lives in this file. The rest of the app
(the CLI, the live pipeline and the web server) already calls these functions.
Your job is to make them work using the NobodyWho library.

Useful documentation:
    https://docs.nobodywho.ooo/docs/
    https://docs.nobodywho.ooo/llms.txt
"""

# TODO (step 2): import SpeechToText from the nobodywho package.


# The Whisper model used by default. "hf://" means "download from HuggingFace".
# Keep this constant: other files import it.
DEFAULT_MODEL = "hf://onnx-community/whisper-tiny"


def create_stt(model: str = DEFAULT_MODEL, language: str = "en"):
    """Create and return a speech-to-text engine.

    The returned object is reused many times, so creating it is the slow part
    (the model is loaded into memory here) and transcribing is the fast part.

    Hint: NobodyWho has a class for this. It takes the model source and the
    language code as arguments.
    """
    raise NotImplementedError("CHALLENGE step 2: implement create_stt() in nobody/stt.py")


def transcribe_file(path: str, model: str = DEFAULT_MODEL, language: str = "en") -> str:
    """Transcribe an audio file (WAV or MP3) and return the full text as one string.

    Hint: the engine from create_stt() has a method that takes a file path.
    That method returns a stream of text pieces, not a string. The stream has
    a method that waits for everything and returns the complete text.
    """
    raise NotImplementedError("CHALLENGE step 2: implement transcribe_file() in nobody/stt.py")


def transcribe_file_streaming(path: str, model: str = DEFAULT_MODEL, language: str = "en"):
    """Transcribe an audio file, yielding small pieces of text as they are produced.

    This is a generator. The CLI command `python -m nobody transcribe` loops
    over it and prints each piece as soon as it arrives.

    Hint: the stream returned by the engine can be used directly in a `for` loop.
    """
    raise NotImplementedError("CHALLENGE step 2: implement transcribe_file_streaming() in nobody/stt.py")


def transcribe_pcm(stt, samples: list[int], sample_rate: int) -> str:
    """Transcribe raw audio samples that are already in memory.

    This is used by the live pipeline (nobody/pipeline.py) while a meeting
    is being recorded. The pipeline gives you:

        stt         the engine returned by create_stt()
        samples     a list of 16-bit signed integers (one per audio sample)
        sample_rate how many samples per second (48000 in this app)

    Return the recognised text as one string.

    Hint: the engine has a second transcribe method made for raw samples.
    Like the file method, it returns a stream that you must wait on.
    """
    raise NotImplementedError("CHALLENGE step 3: implement transcribe_pcm() in nobody/stt.py")
