import os
import json
import re
from typing import List, Optional
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, DEFAULT_GEMINI_MODEL
from core.models import FullTranscript, MeetingAnalysis, ChatQueryResponse
from core.intelligence.base import LLMProvider
from core.intelligence.prompts import SYSTEM_MEETING_ANALYZER_PROMPT, SYSTEM_QA_PROMPT


class GeminiProvider(LLMProvider):
    """
    Google Gemini implementation using official google.genai SDK for meeting intelligence and Q&A.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = DEFAULT_GEMINI_MODEL):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY
        self.model_name = model_name
        self.client: Optional[genai.Client] = None

        if self.api_key and self.api_key != "your_gemini_api_key_here":
            self.client = genai.Client(api_key=self.api_key)

    def _ensure_client(self) -> genai.Client:
        key = self.api_key or os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY
        if not key or key == "your_gemini_api_key_here":
            raise ValueError("Google Gemini API Key is missing. Please set GEMINI_API_KEY in .env or via Settings.")

        if self.client is None or self.api_key != key:
            self.api_key = key
            self.client = genai.Client(api_key=key)

        return self.client

    def _build_transcript_text(self, transcript: FullTranscript) -> str:
        """Formats the transcript with timestamps for context."""
        lines = []
        for s in transcript.segments:
            start_m, start_s = divmod(int(s.start), 60)
            end_m, end_s = divmod(int(s.end), 60)
            lines.append(f"[{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}] {s.text}")
        return "\n".join(lines)

    def analyze_meeting(self, transcript: FullTranscript) -> MeetingAnalysis:
        client = self._ensure_client()
        transcript_formatted = self._build_transcript_text(transcript)

        user_prompt = f"""Language: {transcript.language.upper()}
Duration: {transcript.duration} seconds

Full Timestamped Meeting Transcript:
{transcript_formatted}

Analyze the meeting above according to the system instructions and output strictly the JSON object.
"""

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_MEETING_ANALYZER_PROMPT,
            response_mime_type="application/json"
        )

        response = client.models.generate_content(
            model=self.model_name,
            contents=user_prompt,
            config=config
        )

        raw_text = response.text.strip() if response.text else ""

        # Clean JSON fences if any were included
        clean_json_str = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
        clean_json_str = re.sub(r"^```\s*", "", clean_json_str)
        clean_json_str = re.sub(r"\s*```$", "", clean_json_str)

        try:
            data = json.loads(clean_json_str)
            return MeetingAnalysis(**data)
        except Exception:
            return MeetingAnalysis(
                meeting_title="Meeting Intelligence Report",
                executive_summary=raw_text[:500] if raw_text else "Summary unavailable.",
                overall_sentiment="Neutral",
                key_topics=[],
                action_items=[],
                key_decisions=[],
                key_takeaways=[]
            )

    def answer_query(self, transcript: FullTranscript, query: str, history: Optional[List[dict]] = None) -> ChatQueryResponse:
        client = self._ensure_client()
        transcript_formatted = self._build_transcript_text(transcript)

        user_prompt = f"""Timestamped Meeting Transcript:
{transcript_formatted}

Question:
{query}
"""

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_QA_PROMPT
        )

        response = client.models.generate_content(
            model=self.model_name,
            contents=user_prompt,
            config=config
        )

        answer_text = response.text.strip() if response.text else "No response generated."

        # Extract timestamps in bracket notation like [01:23 - 01:45] or [01:23]
        timestamp_matches = re.findall(r"\[\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?\]", answer_text)

        return ChatQueryResponse(
            answer=answer_text,
            relevant_timestamps=list(set(timestamp_matches))
        )
