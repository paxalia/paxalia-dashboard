# paxalia/report_delivery.py

"""
send_report_email() sends a ScheduledReport's traffic snapshot as an
HTML email, with a PDF attached IF weasyprint is installed — same
optional-dependency pattern as django-otp elsewhere in this package.
weasyprint isn't in install_requires; without it, the email still
sends, just without the attachment. Rendering the PDF from the exact
same HTML used for the email body avoids maintaining two separate
report layouts.
"""
import logging

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger('paxalia.reporting')


def _render_pdf(html_body):
    try:
        import weasyprint
    except ImportError:
        return None
    try:
        return weasyprint.HTML(string=html_body).write_pdf()
    except Exception:
        logger.exception('Failed to render PDF for scheduled report — sending email without attachment')
        return None


def send_report_email(report, snapshot):
    """report: ScheduledReport, snapshot: dict from
    paxalia.reporting.compute_overview_snapshot(). Returns True/False
    for whether the send succeeded — never raises, since a report
    failure shouldn't crash the whole scheduled run for other reports."""
    html_body = render_to_string('paxalia/email/report_digest.html', {
        'report': report, 'snapshot': snapshot,
    })
    text_body = (
        f"Traffic report for {report.name}: {snapshot['start_date']} to {snapshot['end_date']}\n"
        f"Total views: {snapshot['total_views']}\n"
        f"Unique visitors: {snapshot['unique_visitors']}\n"
    )

    try:
        msg = EmailMultiAlternatives(
            subject=f"[{report.name}] Traffic report — {snapshot['start_date']} to {snapshot['end_date']}",
            body=text_body,
            to=report.recipient_list(),
        )
        msg.attach_alternative(html_body, "text/html")

        pdf_bytes = _render_pdf(html_body)
        if pdf_bytes:
            msg.attach(f"{report.name}-report.pdf", pdf_bytes, "application/pdf")

        msg.send(fail_silently=False)
        return True
    except Exception:
        logger.exception('Failed to send scheduled report email for report_id=%s', report.id)
        return False
