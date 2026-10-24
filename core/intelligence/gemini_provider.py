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
        Returns the resolved model name, defaulting to gemini-3.8-flash.
        """
        if self._resolved_model:
            return self._resolved_model
        self._resolved_model = self.model_name or "gemini-3.8-flash"
        return self._resolved_model

    def _is_network_or_dns_error(self, e: Exception) -> bool:
        """Determines if an exception is caused by transient socket, network, or DNS resolution failures."""
        err_str = str(e).lower()
        dns_indicators = [
            "getaddrinfo failed",
            "11001",
            "nameresolutionerror",
            "connectionerror",
            "connecttimeout",
            "timeout",
            "remotedisconnected",
            "connection refused",
            "network is unreachable",
            "temporary failure in name resolution"
        ]
        return any(ind in err_str for ind in dns_indicators)

    def _generate_with_retry(self, client: genai.Client, contents, config):
        """
        Calls generate_content with automatic network retries and model fallback.
        """
        import time
        primary_model = self._resolve_model_name(client)
        fallback_chain = [
            primary_model,
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.5-flash",
            "gemini-flash-latest",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash"
        ]

        last_error = None
        attempted = set()

        for model_candidate in fallback_chain:
            if not model_candidate or model_candidate in attempted:
                continue
            attempted.add(model_candidate)

            # Retry transient network / DNS socket errors up to 3 times before giving up
            max_network_retries = 3
            for attempt in range(max_network_retries):
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

                    # Handle network/DNS failures with backoff
                    if self._is_network_or_dns_error(e):
                        if attempt < max_network_retries - 1:
                            time.sleep(0.8 * (attempt + 1))
                            continue
                        raise RuntimeError(
                            "Network Connection Error: Unable to resolve Google AI servers (DNS lookup failed). "
                            "Please check your internet connection or DNS settings and try again."
                        ) from e

                    # If 404 or unsupported, continue to next model candidate in fallback chain
                    if "404" in err_str or "not found" in err_str or "not supported" in err_str:
                        break

                    # For non-network, non-404 errors (like quota or auth), raise directly
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
