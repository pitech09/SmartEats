from threading import Thread
from flask_mail import Message # type: ignore

from flask import current_app, render_template

from application import mail

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(to, subject, template, **kwargs):
    msg = Message(current_app.config['FLASKY_MAIL_SUBJECT_PREFIX'] + subject,
    sender=current_app.config['FLASKY_MAIL_SENDER'], recipients=[to])
    msg.body = render_template('templates/auth/email/confirm' + '.txt', **kwargs)
    #msg.html = render_template(template + '.html', **kwargs)
    mail.send(msg)
