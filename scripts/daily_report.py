from src.admin.app import create_app
from src.utils.email import send_report_email

app = create_app()
with app.app_context():
    response = app.view_functions['generate_report_csv']()
    csv_data = response.response[0].encode()

send_report_email(
    "admin@kibabii.ac.ke",
    csv_data,
    "daily_access_report.csv"
)
