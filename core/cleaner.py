import re
from typing import List
from core.models import TranscriptSegment


# Common Whisper silence hallucinations / repetition loops
KNOWN_HALLUCINATIONS = {
    "thank you.", "thank you very much.", "thanks for watching.",
    "subtitles by", "translated by", "subscribe", "please subscribe",
    "bye.", "you", "...", "---"
}


def is_hallucination(text: str) -> bool:
    """
    Checks if a segment or word is a Whisper hallucination.
    """
    if not text:
        return True
    clean = text.strip()
    if not clean:
        return True

    # 1. Check known hallucination phrases
    if clean.lower().rstrip(".!,?") in KNOWN_HALLUCINATIONS:
        return True

    # 2. Pure punctuation or symbols
    if re.fullmatch(r"[.\-,!?…:;\"'\s\(\)\[\]\-]+", clean):
        return True

    # 3. Single unique character repeated across words (e.g. "a a a a a", "m m m")
    chars_only = clean.replace(" ", "").lower()
    if len(set(chars_only)) == 1 and len(chars_only) <= 15:
        return True

    return False


def clean_segments(segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
    """
    Cleans a list of TranscriptSegment instances, removing hallucinated or empty segments.
    """
    cleaned: List[TranscriptSegment] = []
    seg_id = 1
    for seg in segments:
        if is_hallucination(seg.text):
            continue

        valid_words = [w for w in seg.words if not is_hallucination(w.word)] if seg.words else []
        seg.words = valid_words
        seg.id = seg_id
        cleaned.append(seg)
        seg_id += 1

    return cleaned
