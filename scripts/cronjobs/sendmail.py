# Simple SMTP interface
import smtplib

# Import the email modules we'll need
from email.mime.text import MIMEText

__SENDER__ = 'Projects <sebb@apache.org>'
__RECIPIENTS__ = 'Site Development <sebb@apache.org>'
__REPLY_TO__ = 'sebb@apache.org'

def sendMail(subject, body='', recipients=__RECIPIENTS__, sender=__SENDER__, port=25, replyTo=__REPLY_TO__):
    # Create a text/plain message
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    if isinstance(recipients, str):
        msg['To'] = recipients
    else:
        msg['To'] = ",".join(recipients)
    if replyTo != None:
        msg['Reply-To'] = replyTo
    smtp = smtplib.SMTP('localhost', port)
#     smtp.set_debuglevel(True)
    smtp.sendmail(sender, recipients, msg.as_string())
    smtp.quit()

if __name__ == '__main__':
    import sys
    port = 25
    if len(sys.argv) > 1: # argv[0] is the script name
        port = int(sys.argv[1])
    # for testing locally:
    # sudo postfix start # MacoxX
    # or start a debug server => need to change the SMTP port
    # python -m smtpd -n -c DebuggingServer localhost:1025
    sendMail('Test message, please ignore', "Thanks!", port=port)
    print("Sent")
    sendMail('Another Test message, please ignore', "Thanks again!", recipients=['a.b.c','d.e.f'], port=port)
    print("Sent second")
