import os
import smtplib
from email.message import EmailMessage

def send_report_email(to_email, file_bytes, filename):
    msg = EmailMessage()
    msg["Subject"] = "Biometric Access Report"
    msg["From"] = os.getenv("SMTP_USER")
    msg["To"] = to_email
    msg.set_content("Attached is the access report.")

    msg.add_attachment(
        file_bytes,
        maintype="application",
        subtype="octet-stream",
        filename=filename
    )

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as smtp:
        smtp.starttls()
        smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
        smtp.send_message(msg)
def build_date_filter(params):
    """Build SQL WHERE clause for date filtering."""
    where_clauses = []
    query_params = {}

    start_date = params.get('start_date')
    end_date = params.get('end_date')

    if start_date:
        where_clauses.append("al.timestamp >= :start_date")
        query_params['start_date'] = start_date

    if end_date:
        where_clauses.append("al.timestamp <= :end_date")
        query_params['end_date'] = end_date

    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    return where_clause, query_params