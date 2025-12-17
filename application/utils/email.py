import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_email(to_email, subject, content):
    message = Mail(
        from_email='noreply@smarteats.com',  # must be a verified sender in SendGrid
        to_emails=to_email,
        subject=subject,
        plain_text_content=content
    )
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print("Email sent:", response.status_code)
    except Exception as e:
        print("Error sending email:", e)
