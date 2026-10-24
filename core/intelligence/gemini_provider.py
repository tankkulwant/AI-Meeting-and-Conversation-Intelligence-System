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
    Google Gemini implementation using official google.genai SDK with automatic model resolution and fallback.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = DEFAULT_GEMINI_MODEL):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.client: Optional[genai.Client] = None
        self._resolved_model: Optional[str] = None

        if self.api_key and self.api_key != "your_gemini_api_key_here":
            self.client = genai.Client(api_key=self.api_key)

    def _ensure_client(self) -> genai.Client:
        key = self.api_key or os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY
        if not key or key == "your_gemini_api_key_here":
            raise ValueError("Google Gemini API Key is missing. Please set GEMINI_API_KEY in .env or via Settings.")

        if self.client is None or self.api_key != key:
            self.api_key = key
            self.client = genai.Client(api_key=key)
            self._resolved_model = None  # Reset resolution for new client

        return self.client

    def _resolve_model_name(self, client: genai.Client) -> str:
        """
        Dynamically verifies which Gemini model is available for the active API key.
        """
        if self._resolved_model:
            return self._resolved_model

        candidates = [
            self.model_name,
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp"
        ]

        # Query client.models.list() to find active models
        try:
            available_models = []
            for m in client.models.list():
                raw_name = m.name or ""
                clean_name = raw_name.replace("models/", "")
                available_models.append(clean_name)

            # Match against candidates
            for c in candidates:
                if c in available_models:
                    self._resolved_model = c
                    self.model_name = c
                    return c

            # Match any gemini flash or pro model
            for a in available_models:
                if "gemini" in a and ("flash" in a or "pro" in a):
                    self._resolved_model = a
                    self.model_name = a
                    return a

            if available_models:
                self._resolved_model = available_models[0]
                self.model_name = available_models[0]
                return self._resolved_model
        except Exception:
            pass

        # Default to preferred candidate
        self._resolved_model = candidates[0] or "gemini-2.0-flash"
        return self._resolved_model

    def _generate_with_retry(self, client: genai.Client, contents: str, config: types.GenerateContentConfig):
        """
        Calls generate_content with automatic model fallback in case of 404 NOT_FOUND.
        """
        primary_model = self._resolve_model_name(client)
        fallback_chain = [
            primary_model,
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp"
        ]

        last_error = None
        attempted = set()

        for model_candidate in fallback_chain:
            if not model_candidate or model_candidate in attempted:
                continue
            attempted.add(model_candidate)

            try:
                response = client.models.generate_content(
                    model=model_candidate,
                    contents=contents,
                    config=config
                )
                self.model_name = model_candidate
                self._resolved_model = model_candidate
                return response
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # If 404 or unsupported, continue to next model candidate
                if "404" in err_str or "not found" in err_str or "not supported" in err_str:
                    continue
                # For non-404 errors (like quota or auth), raise directly
                raise e

        raise last_error or RuntimeError("Failed to generate content with available Gemini models.")

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

        response = self._generate_with_retry(
            client=client,
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

        response = self._generate_with_retry(
            client=client,
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
