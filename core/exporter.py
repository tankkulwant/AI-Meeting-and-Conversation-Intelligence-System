import os
from pathlib import Path
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from core.models import FullTranscript, MeetingAnalysis, TranscriptSegment


def format_srt_time(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    ms = min(ms, 999)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def format_vtt_time(seconds: float) -> str:
    """Format seconds into WebVTT timestamp format: HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    ms = min(ms, 999)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def export_to_srt(segments: List[TranscriptSegment], output_path: str) -> str:
    """Exports transcript segments to .srt file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_time(seg.start)} --> {format_srt_time(seg.end)}\n")
            f.write(f"{seg.text}\n\n")
    return output_path


def export_to_vtt(segments: List[TranscriptSegment], output_path: str) -> str:
    """Exports transcript segments to WebVTT (.vtt) file for HTML5 video track."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_vtt_time(seg.start)} --> {format_vtt_time(seg.end)}\n")
            f.write(f"{seg.text}\n\n")
    return output_path


def export_to_markdown(analysis: MeetingAnalysis, transcript: FullTranscript, output_path: str) -> str:
    """Exports meeting intelligence and transcript to a clean Markdown Minutes of Meeting (MoM)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    lines = [
        f"# Minutes of Meeting: {analysis.meeting_title}",
        "",
        f"- **Language:** {transcript.language.upper()} | **Duration:** {transcript.duration} seconds",
        f"- **Overall Sentiment:** {analysis.overall_sentiment}",
        "",
        "## 1. Executive Summary",
        f"{analysis.executive_summary}",
        "",
        "## 2. Key Discussion Topics",
    ]

    for topic in analysis.key_topics:
        lines.append(f"### {topic.topic}")
        lines.append(f"{topic.summary}")
        if topic.key_points:
            for pt in topic.key_points:
                lines.append(f"- {pt}")
        lines.append("")

    lines.append("## 3. Action Items")
    if analysis.action_items:
        lines.append("| # | Action Item | Assignee | Deadline | Priority | Status |")
        lines.append("|---|---|---|---|---|---|")
        for item in analysis.action_items:
            lines.append(f"| {item.id} | {item.task} | {item.assignee} | {item.deadline} | {item.priority} | {item.status} |")
    else:
        lines.append("No explicit action items detected.")
    lines.append("")

    lines.append("## 4. Key Decisions Made")
    if analysis.key_decisions:
        for dec in analysis.key_decisions:
            lines.append(f"- **Decision {dec.id}:** {dec.decision}")
            if dec.rationale:
                lines.append(f"  *Rationale:* {dec.rationale}")
    else:
        lines.append("No explicit decisions recorded.")
    lines.append("")

    lines.append("## 5. Key Takeaways")
    for t in analysis.key_takeaways:
        lines.append(f"- {t}")
    lines.append("")

    lines.append("## 6. Timestamped Transcript")
    for seg in transcript.segments:
        lines.append(f"`[{format_vtt_time(seg.start)} - {format_vtt_time(seg.end)}]` {seg.text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def export_to_pdf(analysis: MeetingAnalysis, output_path: str) -> str:
    """Exports a styled PDF document of the Minutes of Meeting (MoM)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=12
    )
    h2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#2563EB'),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155')
    )

    story = []

    # Title
    story.append(Paragraph(f"Minutes of Meeting: {analysis.meeting_title}", title_style))
    story.append(Paragraph(f"<b>Overall Tone/Sentiment:</b> {analysis.overall_sentiment}", body_style))
    story.append(Spacer(1, 10))

    # Executive Summary
    story.append(Paragraph("1. Executive Summary", h2_style))
    story.append(Paragraph(analysis.executive_summary, body_style))
    story.append(Spacer(1, 10))

    # Key Topics
    story.append(Paragraph("2. Key Topics & Discussion", h2_style))
    for topic in analysis.key_topics:
        story.append(Paragraph(f"<b>{topic.topic}:</b> {topic.summary}", body_style))
        for pt in topic.key_points:
            story.append(Paragraph(f"• {pt}", body_style))
        story.append(Spacer(1, 4))

    # Action Items Table
    story.append(Paragraph("3. Action Items", h2_style))
    if analysis.action_items:
        table_data = [["#", "Action Item", "Assignee", "Deadline", "Priority", "Status"]]
        for item in analysis.action_items:
            table_data.append([
                str(item.id),
                Paragraph(item.task, body_style),
                item.assignee,
                item.deadline,
                item.priority,
                item.status
            ])
        t = Table(table_data, colWidths=[25, 200, 80, 80, 60, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No action items recorded.", body_style))
    story.append(Spacer(1, 10))

    # Key Decisions
    story.append(Paragraph("4. Key Decisions", h2_style))
    if analysis.key_decisions:
        for dec in analysis.key_decisions:
            story.append(Paragraph(f"• <b>{dec.decision}</b> ({dec.rationale})", body_style))
    else:
        story.append(Paragraph("No explicit decisions recorded.", body_style))

    doc.build(story)
    return output_path
