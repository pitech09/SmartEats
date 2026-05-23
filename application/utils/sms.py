import re

import requests
from flask import current_app


def normalize_phone_number(value):
    if not value:
        return None

    phone = re.sub(r"[^\d+]", "", str(value).strip())
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    elif phone.startswith("266") and len(phone) == 11:
        phone = "+" + phone
    elif phone.startswith("0") and len(phone) == 9:
        phone = "+266" + phone[1:]
    elif phone.isdigit() and len(phone) == 8:
        phone = "+266" + phone

    return phone if re.fullmatch(r"\+\d{8,15}", phone) else None


def send_sms(to, body):
    to_number = normalize_phone_number(to)
    if not to_number:
        current_app.logger.info("SMS skipped: missing or invalid recipient number.")
        return False

    if not current_app.config.get("SMS_ENABLED", False):
        current_app.logger.info("SMS skipped: SMS_ENABLED is false.")
        return False

    account_sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    auth_token = current_app.config.get("TWILIO_AUTH_TOKEN")
    from_number = current_app.config.get("TWILIO_FROM_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        current_app.logger.warning("SMS skipped: Twilio settings are incomplete.")
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    try:
        response = requests.post(
            url,
            data={"From": from_number, "To": to_number, "Body": body},
            auth=(account_sid, auth_token),
            timeout=8,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        current_app.logger.exception("SMS send failed.")
        return False
