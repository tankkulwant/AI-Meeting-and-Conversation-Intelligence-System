from typing import List, Optional
from pydantic import BaseModel, Field


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    probability: Optional[float] = 1.0


class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: Optional[List[WordTimestamp]] = []


class FullTranscript(BaseModel):
    language: str
    duration: float
    segments: List[TranscriptSegment]
    plain_text: str


class ActionItem(BaseModel):
    id: int = Field(default=1, description="Sequential action item number")
    task: str = Field(description="Clear, actionable task description")
    assignee: str = Field(default="Unassigned", description="Person or team responsible")
    deadline: str = Field(default="Not specified", description="Target completion date or timeline")
    priority: str = Field(default="Medium", description="High / Medium / Low")
    status: str = Field(default="Open", description="Open / In Progress / Completed")


class KeyDecision(BaseModel):
    id: int = Field(default=1)
    decision: str = Field(description="Decision reached during the conversation")
    rationale: Optional[str] = Field(default="", description="Context or reasoning for the decision")


class TopicDiscussion(BaseModel):
    topic: str = Field(description="Topic or agenda theme")
    summary: str = Field(description="Summary of discussions around this topic")
    key_points: List[str] = Field(default_factory=list, description="Bullet points of key arguments or facts")


class MeetingAnalysis(BaseModel):
    meeting_title: str = Field(description="Concise, descriptive title for the meeting")
    executive_summary: str = Field(description="Executive summary (TL;DR) of the meeting")
    overall_sentiment: str = Field(default="Neutral", description="Positive / Constructive / Neutral / Critical / Mixed")
    key_topics: List[TopicDiscussion] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    key_decisions: List[KeyDecision] = Field(default_factory=list)
    key_takeaways: List[str] = Field(default_factory=list)


class ChatQueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class ChatQueryResponse(BaseModel):
    answer: str
    relevant_timestamps: List[str] = []
