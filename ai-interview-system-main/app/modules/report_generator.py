from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class ReportGenerator:
    def generate_pdf(self, report: dict) -> bytes:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 50

        def draw_line(text: str, font: str = "Helvetica", size: int = 10, step: int = 16) -> None:
            nonlocal y
            if y < 70:
                pdf.showPage()
                y = height - 50
            pdf.setFont(font, size)
            pdf.drawString(40, y, (text or "")[:110])
            y -= step

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(40, y, "AI Voice Interview Report")
        y -= 28

        pdf.setFont("Helvetica", 11)
        pdf.drawString(40, y, f"Candidate: {report['candidate_name']}")
        y -= 18
        pdf.drawString(40, y, f"Mode: {report['mode']}")
        y -= 18
        pdf.drawString(40, y, f"Overall Score: {report['overall_score']}%")
        y -= 26

        ai_feedback = report.get("ai_feedback_report") or {}
        if ai_feedback:
            draw_line("AI Feedback Report", "Helvetica-Bold", 12, 18)
            communication = ai_feedback.get("communication", {})
            confidence = ai_feedback.get("confidence", {})
            technical = ai_feedback.get("technical_answer_quality", {})
            draw_line(f"Communication: {communication.get('score', '-')}/10 - {communication.get('summary', '')}")
            draw_line(f"Confidence: {confidence.get('score', '-')}/10 - {confidence.get('summary', '')}")
            draw_line(f"Technical Quality: {technical.get('score', '-')}/10 - {technical.get('summary', '')}")
            suggestions = ai_feedback.get("improvement_suggestions") or []
            if suggestions:
                draw_line("Improvement Suggestions:", "Helvetica-Bold", 10)
                for suggestion in suggestions[:5]:
                    draw_line(f"- {suggestion}")
            y -= 8

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, "Question Breakdown")
        y -= 18

        pdf.setFont("Helvetica", 10)
        for index, item in enumerate(report["items"], start=1):
            for line in [
                f"{index}. {item['question']}",
                f"Score: {item['score']}%",
                f"Feedback: {item['feedback']}",
                f"Suggestion: {item['improvement_suggestion']}",
            ]:
                draw_line(line)
            y -= 10

        pdf.save()
        return buffer.getvalue()


report_generator = ReportGenerator()
