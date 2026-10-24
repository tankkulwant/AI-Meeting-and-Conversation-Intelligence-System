from abc import ABC, abstractmethod
from typing import List, Optional
from core.models import MeetingAnalysis, FullTranscript, ChatQueryResponse


class LLMProvider(ABC):
    """
    Abstract Base Class for LLM providers (Gemini, Groq, Ollama, etc.).
    Ensures easy swapping and extension of different AI backends.
    """

    @abstractmethod
    def analyze_meeting(self, transcript: FullTranscript) -> MeetingAnalysis:
        """
        Processes a full meeting transcript and returns structured meeting intelligence.
        """
        pass

    @abstractmethod
    def answer_query(self, transcript: FullTranscript, query: str, history: Optional[List[dict]] = None) -> ChatQueryResponse:
        """
        Answers a specific user question about the meeting, citing relevant timestamps.
        """
        pass
