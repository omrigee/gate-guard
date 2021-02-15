import sys
import datetime
import webbrowser as web
import time
import pyautogui as pg

now = datetime.datetime.now()
now_plus_2 = now + datetime.timedelta(minutes = 2)

web.open('https://web.whatsapp.com/send?phone='+sys.argv[1]+'&text='+'Car number: '+sys.argv[2] + ' entered', new = 0)
time.sleep(2)
width, height = pg.size()
pg.click(width / 2, height / 2)
time.sleep(10 - 2)
pg.press('enter')