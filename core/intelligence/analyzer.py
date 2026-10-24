from typing import Optional, List
from core.models import FullTranscript, MeetingAnalysis, ChatQueryResponse
from core.intelligence.base import LLMProvider
from core.intelligence.gemini_provider import GeminiProvider


class IntelligenceAnalyzer:
    """
    Orchestrator for AI Meeting Analysis. Allows selecting and switching providers.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider: LLMProvider = provider or GeminiProvider()

    def set_provider(self, provider: LLMProvider):
        self.provider = provider

    def analyze(self, transcript: FullTranscript) -> MeetingAnalysis:
        return self.provider.analyze_meeting(transcript)

    def ask(self, transcript: FullTranscript, query: str, history: Optional[List[dict]] = None) -> ChatQueryResponse:
        return self.provider.answer_query(transcript, query, history)
