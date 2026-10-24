import os
from pathlib import Path
import ffmpeg


def extract_audio(input_media_path: str, output_audio_path: str) -> str:
    """
    Extracts and normalizes audio from an audio or video file.
    Outputs a mono, 16 kHz WAV file required by Whisper.

    Args:
        input_media_path: Path to the input video (.mp4, .mov, .mkv) or audio (.mp3, .wav, .m4a).
        output_audio_path: Destination path for the extracted 16kHz mono WAV.

    Returns:
        output_audio_path on success.
    """
    input_media_path = str(Path(input_media_path).resolve())
    output_audio_path = str(Path(output_audio_path).resolve())
    os.makedirs(os.path.dirname(output_audio_path), exist_ok=True)

    try:
        (
            ffmpeg
            .input(input_media_path)
            .output(
                output_audio_path,
                ac=1,                   # Mono channel
                ar=16000,               # 16,000 Hz sample rate
                format="wav"
            )
            .overwrite_output()
            .run(quiet=True)
        )
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode("utf-8") if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg audio extraction failed: {error_msg}")

    if not os.path.isfile(output_audio_path) or os.path.getsize(output_audio_path) == 0:
        raise RuntimeError(f"Extracted audio file is missing or empty at {output_audio_path}")

    return output_audio_path
