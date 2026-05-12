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

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(40, y, "AI Voice Interview Report")
        y -= 28

        pdf.setFont("Helvetica", 11)
        pdf.drawString(40, y, f"Candidate: {report['candidate_name']}")
        y -= 18
        pdf.drawString(40, y, f"Mode: {report['mode']}")
        y -= 18
        pdf.drawString(40, y, f"Total Score: {report.get('total_score', 0)} / 50")
        y -= 26

        scores = report.get("scores", {})
        if scores:
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(40, y, "Score Summary")
            y -= 18
            pdf.setFont("Helvetica", 10)
            for line in [
                f"Communication: {scores.get('communication', '-')}/10",
                f"Confidence: {scores.get('confidence', '-')}/10",
                f"Technical: {scores.get('technical', '-')}/10",
                f"Performance: {report.get('performance_label', '-')}",
            ]:
                if y < 70:
                    pdf.showPage()
                    y = height - 50
                    pdf.setFont("Helvetica", 10)
                pdf.drawString(40, y, line)
                y -= 16
            y -= 8

        alerts = report.get("alerts", [])
        if alerts:
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(40, y, "Behavior Alerts")
            y -= 18
            pdf.setFont("Helvetica", 10)
            for alert in alerts[:8]:
                if y < 70:
                    pdf.showPage()
                    y = height - 50
                    pdf.setFont("Helvetica", 10)
                pdf.drawString(40, y, f"- {alert}"[:110])
                y -= 16
            y -= 8

        final_feedback = report.get("final_feedback")
        if final_feedback:
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(40, y, "Final Feedback")
            y -= 18
            pdf.setFont("Helvetica", 10)
            if y < 70:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 10)
            pdf.drawString(40, y, str(final_feedback)[:110])
            y -= 22

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, "Question Breakdown")
        y -= 18

        pdf.setFont("Helvetica", 10)
        for index, item in enumerate(report["items"], start=1):
            for line in [
                f"{index}. {item['question']}",
                f"Score: {item.get('score', 0)}/{item.get('max_score', 10)}",
                f"Feedback: {item['feedback']}",
                f"Suggestion: {item['improvement_suggestion']}",
            ]:
                if y < 70:
                    pdf.showPage()
                    y = height - 50
                    pdf.setFont("Helvetica", 10)
                pdf.drawString(40, y, line[:110])
                y -= 16
            y -= 10

        pdf.save()
        return buffer.getvalue()


report_generator = ReportGenerator()
