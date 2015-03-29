#!/usr/bin/python
__author__ = "Kwang Un Jin"

import datetime
import time
import Queue
import subprocess
import os
from os.path import join, getsize
import picamera
import shutil
import RPi.GPIO as GPIO
import threading
from ConfigParser import SafeConfigParser


def mail(to, subject, text, attach):
    pass


def cleanDisk(maxFreeMega, maxTotalMega, directory):
    pass

class Ping(threading.Thread):
    pass

def main():
    parser = SafeConfigParser()
    candidates = ['homepi.conf', '/etc/homepi.conf']

    GPIO_PIR = 7  # GPIO for PIR sensor
    duration = 60  # sec, duration of each split file
    numofclips = 10  # number of split files

    mail_from_hour = 9  # send mail from hour
    mail_until_hour = 19  # until hour

    minFreeSpace = 1000  # minimum disk free space
    maxTotalSpace = 100000  # maximum recording disk space

    recording_dir = '/media/homepi'  # where recording files are saved
    #gmail_user = "biglaputan@gmail.com"  # gmail account ID and recipient
    #gmail_pwd = "go99dhkd"  # gmail password
    gmail_user = "operator1732@gmail.com"
    gmail_pwd = "Rnrnfld86"

    hosts = ['192.168.22.7', '192.168.22.6', '192.168.22.5', '192.168.22.10']


    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIR, GPIO.IN)
    queue = Queue.Queue()
    ping_thread = Ping(queue, hosts, duration * numofclips)
    ping_thread.start()

    devicedetected = False

    try:
        current_state = 0
        previous_state = 0

        # wait until sensor stays stable
        while GPIO.input(GPIO_PIR) == 1:
            current_state = 0

        print "Ready to detect"


        while True:
            current_state = GPIO.input(GPIO_PIR)

            if current_state == 1 and previous_state == 0:
            # if True:  # for debugging
                print "\nIntruder detected!"

                previous_state = 1
                hour = datetime.datetime.now().hour

                # delete the oldest folder if disk space is low (not perfect)
                threading.Thread(target=cleanDisk, args=[minFreeSpace, maxTotalSpace, recording_dir]).start()

                # recording folder name. For example '2014-02-25_22-01-23'
                t = time.strftime("%Y-%m-%d_") + time.strftime("%H-%M-%S")
                dest_dir = os.path.join(recording_dir, t)
                print "Recording directory is {0}".format(dest_dir)

                os.mkdir(dest_dir)

                with picamera.PiCamera() as camera:
                    time.sleep(2)
                    camera.resolution = (1024, 768)
                    startPic = os.path.join(dest_dir, 'begin.jpg')
                    endPic = os.path.join(dest_dir, 'end.jpg')

                    # take the first shot
                    print "Taking the first shot"
                    camera.capture(startPic)
                    camera.resolution = (640, 480)

                    queue.put({'file': startPic, 'user': gmail_user, 'pw': gmail_pwd, 'text': t})


                    for filename in [os.path.join(dest_dir, ('%d.h264' % i)) for i in range(1, numofclips + 1)]:
                        print "Recording : [{0}]".format(filename)
                        camera.start_recording(filename)
                        camera.wait_recording(duration)
                        camera.stop_recording()
                        threading.Thread(target=convert, args=[filename]).start()

                    camera.resolution = (1024, 768)
                    print "Taking the last shot"
                    camera.capture(endPic)

            elif current_state == 0 and previous_state == 1:
                previous_state = 0

    except KeyboardInterrupt:
        ping_thread.isRunning = False
        print "Interrupted... exit"

    finally:
        GPIO.cleanup()

def convert(h264file):
    d = os.path.dirname(h264file)
    (root, ext) = os.path.splitext(h264file)
    mp4file = root + '.mp4'
    subprocess.call(['MP4Box', '-noprog', '-quiet', '-tmp', d, '-add', h264file, mp4file])
    subprocess.call(['rm', '-f', h264file])


def cleanDisk(maxFreeMega, maxTotalMega, directory):
    # get disk free space
    s = os.statvfs(directory)
    freeMega = (s.f_bavail * s.f_frsize) / 1024 / 1024
    print  'Disk free space : {0} MB'.format(freeMega)

    # get the size of all the directories for recording
    total = 0
    for root, dirs, files in os.walk(directory):
        total = total + sum(getsize(join(root, name)) for name in files)

    totalMega = total / 1024 / 1024

    print  'Total video size : {0}MB'.format(totalMega)

    if freeMega < maxFreeMega or totalMega > maxTotalMega:
        # find the oldest directory
        dirs = sorted(os.listdir(directory),
                      key=lambda d: os.path.getctime(os.path.join(directory, d)))

        # do not delete directory if the only directory exists
        if len(dirs) > 1:
            delete_dir = os.path.join(directory, dirs[0])
            shutil.rmtree(delete_dir)
            print 'Deleted the directory {0}'.format(delete_dir)


# send gmail
# thanks to http://kutuma.blogspot.kr/2007/08/sending-emails-via-gmail-with-python.html
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email import Encoders
import smtplib


def mail(to, password, subject, text, attach):
    msg = MIMEMultipart()

    msg['From'] = to
    msg['To'] = to
    msg['Subject'] = subject

    msg.attach(MIMEText(text))

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(open(attach, 'rb').read())
    Encoders.encode_base64(part)
    part.add_header('Content-Disposition',
                    'attachment; filename="%s"' % os.path.basename(attach))
    msg.attach(part)

    mailServer = smtplib.SMTP("smtp.gmail.com", 587)
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(to, password)
    mailServer.sendmail(to, to, msg.as_string())
    # Should be mailServer.quit(), but that crashes...
    mailServer.close()


class Ping(threading.Thread):
    def __init__(self, queue, hosts, delay):
        threading.Thread.__init__(self)
        self.queue = queue
        self.hosts = hosts
        self.isRunning = True
        self.delay = delay

    def myping(self, host):
        isAlive = os.system("ping -c 1 " + host + '>/dev/null')
        if isAlive == 0:
            return True
        else:
            return False

    def run(self):
        while self.isRunning:
            # blocks here
            m = self.queue.get()
            print 'File input {0}'.format(m['file'])

            isConnected = False

            for host in self.hosts:
                if self.myping(host):
                    print host + ' detected'
                    isConnected = True
                    break

            if isConnected == False:
                print 'send mail to {0}'.format(m['user'])
                download_thread = threading.Thread(target=mail,
                                                   args=[m['user'], m['pw'], "", m['text'], m['file']]).start()
            else:
                print 'no need to send mail'


            self.queue.task_done()

            if self.isRunning == False:
                print 'stop signaled'
                return


if __name__ == '__main__':
    main()

