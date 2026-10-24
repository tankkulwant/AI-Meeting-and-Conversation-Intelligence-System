import os
from typing import Optional, Tuple
import av

# PyAV 14+/19+ compatibility fix for faster-whisper
_orig_av_open = av.open

def _safe_av_open(*args, **kwargs):
    kwargs.pop("metadata_errors", None)
    return _orig_av_open(*args, **kwargs)

av.open = _safe_av_open

from faster_whisper import WhisperModel
from config import (
    DEFAULT_WHISPER_MODEL,
    DEFAULT_DEVICE,
    DEFAULT_COMPUTE_TYPE,
    MODELS_DIR
)
from core.models import FullTranscript, TranscriptSegment, WordTimestamp
from core.cleaner import clean_segments



# Global model cache to avoid reloading the model on every request
_LOADED_MODEL: Optional[WhisperModel] = None
_LOADED_MODEL_PARAMS: Tuple[str, str, str] = ("", "", "")


def get_whisper_model(
    model_size: str = DEFAULT_WHISPER_MODEL,
    device: str = DEFAULT_DEVICE,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
) -> WhisperModel:
    """
    Retrieves or caches a faster-whisper WhisperModel instance.
    """
    global _LOADED_MODEL, _LOADED_MODEL_PARAMS
    params = (model_size, device, compute_type)

    if _LOADED_MODEL is not None and _LOADED_MODEL_PARAMS == params:
        return _LOADED_MODEL

    os.makedirs(MODELS_DIR, exist_ok=True)
    _LOADED_MODEL = WhisperModel(
        model_size_or_path=model_size,
        device=device,
        compute_type=compute_type,
        download_root=str(MODELS_DIR),
    )
    _LOADED_MODEL_PARAMS = params
    return _LOADED_MODEL


def transcribe_audio(
    audio_path: str,
    model_size: str = DEFAULT_WHISPER_MODEL,
    language: Optional[str] = None,
    device: str = DEFAULT_DEVICE,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
    initial_prompt: Optional[str] = None,
) -> FullTranscript:
    """
    Transcribes audio using faster-whisper with word-level and segment-level timestamps.

    Args:
        audio_path: Path to mono 16 kHz WAV audio file.
        model_size: Whisper model size (tiny, base, small, medium, large-v3).
        language: ISO-639-1 code (e.g. 'en', 'hi') or None for auto-detection.
        device: 'cuda' or 'cpu'.
        compute_type: 'int8', 'float16', or 'float32'.
        initial_prompt: Optional context prompt to guide transcription vocabulary.

    Returns:
        FullTranscript object with language, duration, and cleaned segments.
    """
    model = get_whisper_model(model_size=model_size, device=device, compute_type=compute_type)

    transcribe_kwargs = {
        "word_timestamps": True,
        "beam_size": 5,
        "vad_filter": True,  # Silero VAD filtering
        "vad_parameters": {"min_silence_duration_ms": 500},
    }

    if language:
        transcribe_kwargs["language"] = language
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt

    raw_segments, info = model.transcribe(audio_path, **transcribe_kwargs)

    parsed_segments = []
    plain_text_parts = []
    seg_idx = 1

    for seg in raw_segments:
        words = []
        if seg.words:
            for w in seg.words:
                words.append(
                    WordTimestamp(
                        word=w.word,
                        start=round(w.start, 2),
                        end=round(w.end, 2),
                        probability=round(w.probability, 2) if hasattr(w, "probability") else 1.0,
                    )
                )

        parsed_segments.append(
            TranscriptSegment(
                id=seg_idx,
                start=round(seg.start, 2),
                end=round(seg.end, 2),
                text=seg.text.strip(),
                words=words,
            )
        )
        plain_text_parts.append(seg.text.strip())
        seg_idx += 1

    # Filter out silence hallucinations & loops
    cleaned_segments = clean_segments(parsed_segments)

    # Reconstruct plain text from cleaned segments
    cleaned_plain_text = " ".join(s.text for s in cleaned_segments)

    return FullTranscript(
        language=info.language,
        duration=round(info.duration, 2),
        segments=cleaned_segments,
        plain_text=cleaned_plain_text,
    )


def transcribe_audio_generator(
    audio_path: str,
    model_size: str = DEFAULT_WHISPER_MODEL,
    language: Optional[str] = None,
    device: str = DEFAULT_DEVICE,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
    initial_prompt: Optional[str] = None,
):
    """
    Generator yielding real-time progress events as audio is transcribed,
    finishing with the complete FullTranscript object.
    """
    model = get_whisper_model(model_size=model_size, device=device, compute_type=compute_type)

    transcribe_kwargs = {
        "word_timestamps": True,
        "beam_size": 5,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 500},
    }

    if language:
        transcribe_kwargs["language"] = language
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt

    raw_segments, info = model.transcribe(audio_path, **transcribe_kwargs)
    total_duration = max(1.0, float(info.duration))

    parsed_segments = []
    seg_idx = 1

    for seg in raw_segments:
        words = []
        if seg.words:
            for w in seg.words:
                words.append(
                    WordTimestamp(
                        word=w.word,
                        start=round(w.start, 2),
                        end=round(w.end, 2),
                        probability=round(getattr(w, "probability", 1.0), 2),
                    )
                )

        parsed_segments.append(
            TranscriptSegment(
                id=seg_idx,
                start=round(seg.start, 2),
                end=round(seg.end, 2),
                text=seg.text.strip(),
                words=words,
            )
        )
        seg_idx += 1

        percent = min(99, int((seg.end / total_duration) * 100))
        yield {
            "type": "progress",
            "percent": percent,
            "current_time": round(seg.end, 1),
            "total_duration": round(total_duration, 1),
            "text": seg.text.strip()
        }

    cleaned_segments = clean_segments(parsed_segments)
    cleaned_plain_text = " ".join(s.text for s in cleaned_segments)

    final_transcript = FullTranscript(
        language=info.language,
        duration=round(info.duration, 2),
        segments=cleaned_segments,
        plain_text=cleaned_plain_text,
    )

    yield {
        "type": "complete",
        "percent": 100,
        "transcript": final_transcript.model_dump()
    }

