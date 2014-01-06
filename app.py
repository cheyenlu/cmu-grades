from crontab import CronTab
from grades import *
from twilio.rest import TwilioRestClient
from config import *
import smtplib
import sys
import os
import json
import site
import smtplib
from email.mime.text import MIMEText

DEBUG = False

# writes job to the cron
def install_text():
    install('text')

def install_email():
    install('email')

def install(service):
    cron = CronTab()
    command = 'export PYTHONPATH=%s; python %s run_%s' % (site.getsitepackages()[0], os.path.realpath(__file__), service)
    comment = 'cmu-grades-%s' % service
    job = cron.new(command=command, comment=comment)
    job.minute.every(5)
    cron.write()
    print 'Installed cmu-grades %s service!' % service


# removes job from the cron
def uninstall_text():
    uninstall('text')

def uninstall_email():
    uninstall('email')

def uninstall(service):
    cron = CronTab()
    comment = 'cmu-grades-%s' % service
    job = cron.find_comment(comment)
    cron.remove(job[0])
    cron.write()
    print 'Uninstalled cmu-grades %s service!' % service


def send_text(message):
    client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)
    client.sms.messages.create(to=PHONE_NUMBER, from_=TWILIO_NUMBER, body=message.strip())

def send_email(message):
    s = smtplib.SMTP('smtp.gmail.com:587')
    s.starttls()
    s.login(EMAIL, EMAIL_PASSWORD)

    email  = 'Hey %s,\n\n' % NAME
    email += 'This is your grade update from CMU Grades:\n\n'
    email += message

    mime = MIMEText(email)
    mime['Subject'] = 'CMU Grades Update!'
    mime['To'] = EMAIL

    s.sendmail(EMAIL, EMAIL, mime.as_string())
    s.quit()

def diff(old, new):
    new_scores = {}
    for course, grades in new.iteritems():
        if not course in old: break
        old_grades = old[course]
        if isinstance(grades, basestring) and grades != old_grades:
            new_scores[course] = grades
        else:
            new_grades = [(hw, grades[hw]) for hw in grades if hw not in old_grades]
            if len(new_grades) > 0:
                new_scores[course] = new_grades

    return new_scores

def run_text():
    run(send_text)

def run_email():
    run(send_email)

def run(method):
    # fetches grades from blackboard
    try:
        courses = get_blackboard_grades()
        finals = get_final_grades()
        autolab = get_autolab_grades()
    except Exception:
        if DEBUG:
            print 'Retrieving grades failed...'
        return

    # gets saved grades
    data = {}
    path = os.path.dirname(os.path.realpath(__file__)) + '/grades.json'
    exists = os.path.exists(path)
    if exists:
        f = open(path, 'r+')
        try:
            old_data = json.loads(f.read())
        except:
            # delete malformed json
            f.close()
            os.remove(path)
            return

        f.seek(0)
        f.truncate()

        old_courses = old_data['courses']
        old_finals = old_data['finals']
        old_autolab = old_data['autolab']

        # send a text if blackboard scores have changed
        bb_diff = diff(old_courses, courses)
        if len(bb_diff) > 0:
            message = 'New Blackboard grades!\n'
            for course, grades in bb_diff.iteritems():
                mapper = lambda hw: hw[0] + ' [' + str(round(100.0 * hw[1][0] / hw[1][1])) + ']'
                message += '%s: %s\n' % (course, ', '.join(map(mapper, grades)))
            method(message)

        # same for finals from academic audit
        final_diff = diff(old_finals, finals)
        if len(final_diff) > 0:
            message = 'New final grades!\n'
            for course, grade in final_diff.iteritems():
                message += '%s: %s\n' % (course, grade)
            method(message)

        # same for autolab grades
        autolab_diff = diff(old_autolab, autolab)
        if len(autolab_diff) > 0:
            message = 'New Autolab grades!\n'
            for course, grades in autolab_diff.iteritems():
                mapper = lambda hw: hw[0] + ' [' + str(round(100.0 * hw[1][0] / hw[1][1])) + ']'
                message += '%s: %s\n' % (course, ', '.join(map(mapper, grades)))
            method(message)
    else:
        f = open('grades.json', 'w')

    # write out the new scores
    f.write(json.dumps({'courses': courses, 'finals': finals, 'autolab': autolab}))
    f.close()


COMMANDS = {
    'install_text': install_text,
    'uninstall_text': uninstall_text,
    'run_text': run_text,
    'install_email': install_email,
    'uninstall_email': uninstall_email,
    'run_email': run_email
}

def main():
    if len(sys.argv) <= 1 or sys.argv[1] not in COMMANDS:
        print 'USAGE: %s <%s>' % (sys.argv[0], "|".join(COMMANDS))
        exit()

    COMMANDS[sys.argv[1]]()

if __name__ == '__main__':
    main()
