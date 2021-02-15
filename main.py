import sys
import time

from PyQt5.uic import loadUi
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5 import QtWidgets as qtw
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QWidget, QMessageBox
import MySQLdb
import sys
import os

import cv2 as cv
from collections import deque
from openalpr import *


phone_to_report = 'X'
DB_USERNAME = 'X'
DB_PASSWORD = 'X'


class AddCarDialog(QDialog):
    def __init__(self):
        super(AddCarDialog, self).__init__()
        loadUi('./ui/add_car_dialog.ui', self)

class ChangeHoursDialog(QDialog):
    def __init__(self):
        super(ChangeHoursDialog,self).__init__()
        loadUi('./ui/changehours_dialog.ui',self)

class ActivityHoursDatabaseWindow(QDialog):
    def __init__(self):
        super(ActivityHoursDatabaseWindow, self).__init__()
        loadUi("./ui/hours_database.ui", self)
        self.mydb = MySQLdb.connect(host="localhost", user=DB_USERNAME, passwd=DB_PASSWORD)
        self.cursor = self.mydb.cursor()

        self.days_dictionary = {1 : 'Sunday',2 : 'Monday',3 : 'Tuesday',4 : 'Wednesday', 5 : 'Thursday', 6 : 'Friday' , 7 : 'Saturday'}
        self.tableWidget.setColumnWidth(0, 220)  # set column 0 width to 200
        self.tableWidget.setColumnWidth(1, 220)
        self.tableWidget.setColumnWidth(2, 220)
        self.activityhours_load_data()

        self.changeHoursBtn.clicked.connect(self.executeChangeHoursDialog)

    def activityhours_load_data(self):
        sqlquery = "SELECT * FROM GateGuard.ActivityHours"
        self.cursor.execute(sqlquery)
        self.tableWidget.setRowCount(7)
        tablerow = 0
        for row in self.cursor.fetchall():
            self.tableWidget.setItem(tablerow, 0, qtw.QTableWidgetItem(str(self.days_dictionary.get(row[0]))))  # insert name
            self.tableWidget.setItem(tablerow, 1, qtw.QTableWidgetItem(str(row[1])))  # insert car id
            self.tableWidget.setItem(tablerow, 2, qtw.QTableWidgetItem(str(row[2])))  # insert phone no.
            tablerow += 1

    def executeChangeHoursDialog(self):
        change_hours_dialog = ChangeHoursDialog()
        change_hours_dialog.exec_()

class CarDatabaseWindow(QDialog):
    def __init__(self):
        super(CarDatabaseWindow, self).__init__()
        loadUi("./ui/cars_database.ui", self)
        self.mydb = MySQLdb.connect(host="localhost", user=DB_USERNAME, passwd=DB_PASSWORD)
        self.cursor = self.mydb.cursor()
        self.tableWidget.setColumnWidth(0, 200)  # set column 0 width to 200
        self.tableWidget.setColumnWidth(1, 200)
        self.tableWidget.setColumnWidth(2, 200)
        self.cars_load_data()
        self.addCarBtn.clicked.connect(self.executeAddCarDialog)

    def cars_load_data(self):
        sqlquery = "SELECT * FROM GateGuard.Cars"
        self.cursor.execute(sqlquery)
        self.tableWidget.setRowCount(50) #TODO: rowcount will be number of entries + 50
        tablerow = 0
        for row in self.cursor.fetchall():
            self.tableWidget.setItem(tablerow, 0, qtw.QTableWidgetItem(str(row[0])))  # insert name
            self.tableWidget.setItem(tablerow, 1, qtw.QTableWidgetItem(str(row[1])))  # insert car id
            self.tableWidget.setItem(tablerow, 2, qtw.QTableWidgetItem(str(row[2])))  # insert phone no.
            tablerow += 1

    def executeAddCarDialog(self):
        add_car_page = AddCarDialog()
        add_car_page.exec_()
        owner_name = add_car_page.ownerName_lineedit.text()
        car_id = add_car_page.CarID_lineedit.text()
        phone_number = add_car_page.PhoneNumber_lineedit.text()

        # Check if car is already in database
        #print(phone_number)
        self.cursor.execute("SELECT * FROM GateGuard.Cars WHERE car_ID = {}".format(car_id))
        if self.cursor.rowcount == 0:
            self.cursor.execute(
                "INSERT INTO GateGuard.Cars (car_id,owner_name,phone_number) VALUES ('{}','{}','{}');".format(
                    str(car_id), str(owner_name), str(phone_number)))
            self.mydb.commit()
        else:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setText("Car number: {} is already registered in the cars database".format(car_id))
            msg.exec_()

        self.cars_load_data()





class SystemWorker(QThread):
    ImageUpdate = pyqtSignal(QImage)
    update_table_signal = pyqtSignal()

    def validatePlate(self,raw_plate):
        plate_str = str(raw_plate)
        if ((len(plate_str)) >= 7)  & plate_str.isdigit():
           car_checked =  filter(lambda car_checked: car_checked['plate'] == plate_str,  self.last_entered_queue)
           if not car_checked:
               return True
        return False

    def reportInWhatsapp(self,phone_number,car_entered_id):
        os.system("python3.7 whatsapp.py " + phone_number + " " + car_entered_id)

    def run(self):
        #print("entered run")
        self.ThreadActive = True
        self.mydb = MySQLdb.connect(host="localhost", user=DB_USERNAME, passwd=DB_PASSWORD)
        self.cursor = self.mydb.cursor()
        self.last_entered_queue = deque(maxlen=50)

        self.alpr = Alpr("eu", "/etc/openalpr/openalpr.conf", "/usr/share/openalpr/runtime_data/")
        if not self.alpr.is_loaded():
            print('Error loading OpenALPR')
            sys.exit(1)
        self.alpr.set_top_n(20)


        capture = cv.VideoCapture(1)
        if not capture.isOpened():
            capture = cv.VideoCapture(0)
            if not capture.isOpened():
                sys.exit('Failed to open Camera/Video File')

        while True:
            while self.ThreadActive:
                ret,frame = capture.read()
                ret2, enc = cv.imencode("*.bmp", frame)
                if ret:
                    Image = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
                    ConvertToQtFormat = QImage(Image.data, Image.shape[1],Image.shape[0], QImage.Format_RGB888)
                    Pic = ConvertToQtFormat.scaled(640, 480, Qt.KeepAspectRatio)
                    self.ImageUpdate.emit(Pic)

                    results = self.alpr.recognize_array(bytes(bytearray(enc)))
                    for plate in results['results']:
                        item = plate['plate']

                        if self.validatePlate(item): #validating license plate length and not being recognized
                            #Finding car in database:
                            self.cursor.execute("SELECT * FROM GateGuard.Cars WHERE car_id = '{}'".format(item))
                            x = self.cursor.fetchone()
                            if x != None: #Found car in database
                                self.last_entered_queue.appendleft({'plate': x[0], 'authorized': 'Yes', 'car_owner': x[1], 'phone_number': x[2]})
                                self.update_table_signal.emit()
                            else:
                                self.last_entered_queue.appendleft({'plate': item, 'authorized': 'No', 'car_owner': 'Unknown', 'phone_number': 'Unknown'})
                                self.update_table_signal.emit()
                                global phone_to_report
                                print(phone_to_report)
                                self.reportInWhatsapp(phone_to_report,item)

    def cont(self):
        self.ThreadActive = True

    def pause(self):
        self.ThreadActive = False

    def stop(self):
        self.ThreadActive = False
        self.quit()


class SystemSettingsWindow(QDialog):
    def __init__(self):
        super(SystemSettingsWindow,self).__init__()
        loadUi('./ui/settings.ui',self)



class MainWindow(qtw.QMainWindow):

    phone_to_report_signal = pyqtSignal(str)

    def __init__(self):
            super(MainWindow, self).__init__()
            loadUi("./ui/main.ui", self)
            self.setWindowTitle('GateGuard')

            # Initializing Database and tables if not exist:
            self.mydb = MySQLdb.connect(host="localhost", user=DB_USERNAME, passwd=DB_PASSWORD)
            self.cursor = self.mydb.cursor()
            self.initializeDB()

            #Initialize Buttons:
            self.carDatabaseBtn.clicked.connect(self.openCarsDBwindow)
            self.systemSettingsBtn.clicked.connect(self.executeSystemSettingsWindow)
            self.activityHoursDbBtn.clicked.connect(self.openActivityHoursDBwindow)
            self.refreshLastEnteredBtn.clicked.connect(self.update_LastEnteredTable)

            #Initializing and activating camera thread:
            self.worker = SystemWorker()
            self.worker.start()
            self.worker.ImageUpdate.connect(self.ImageUpdateSlot)
            self.worker.update_table_signal.connect(self.update_LastEnteredTable)





    def initializeDB(self):
        self.cursor.execute("CREATE DATABASE IF NOT EXISTS GateGuard;")
        self.cursor.execute("USE GateGuard;")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS Cars (car_id VARCHAR(8) PRIMARY KEY, " +
                                                            "owner_name VARCHAR(30), " +
                                                            "phone_number VARCHAR(10)) ENGINE=InnoDB;")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS ActivityHours (`day` int(1) PRIMARY KEY, " +
                            "start_at TIME (0) NOT NULL, " +
                            "end_at TIME (6) NOT NULL) ENGINE=InnoDB;")
        self.cursor.execute("INSERT IGNORE INTO `ActivityHours` SET `day` = 7, start_at = 0, end_at = 5;")
        self.cursor.execute("INSERT IGNORE INTO `ActivityHours` SET `day` = 6, start_at = 0, end_at = 5;")
        self.cursor.execute("INSERT IGNORE INTO `ActivityHours` SET `day` = 5, start_at = 0, end_at = 5;")
        self.cursor.execute("INSERT IGNORE INTO `ActivityHours` SET `day` = 4, start_at = 0, end_at = 5;")
        self.cursor.execute("INSERT IGNORE INTO `ActivityHours` SET `day` = 3, start_at = 0, end_at = 5;")
        self.cursor.execute("INSERT IGNORE INTO `ActivityHours` SET `day` = 2, start_at = 0, end_at = 5;")
        self.cursor.execute("INSERT IGNORE INTO `ActivityHours` SET `day` = 1, start_at = 0, end_at = 5;")
        self.mydb.commit()


    def executeSystemSettingsWindow(self):
        sys_settings_page = SystemSettingsWindow()
        sys_settings_page.exec_()
        raw_phone =  sys_settings_page.phone_lineEdit.text()
        final_phone = '+972' + raw_phone[1:]
        global phone_to_report
        phone_to_report = final_phone





    def ImageUpdateSlot(self, Image):
        self.FeedLabel.setPixmap(QPixmap.fromImage(Image))
        self.activateBtn.setCheckable(True)
        self.activateBtn.setStyleSheet("background-color : lightgrey")
        self.activateBtn.clicked.connect(self.activateBtnStatus)


        #Last_Entered_Table:
        self.last_entered_queue = self.worker.last_entered_queue
        self.lastEnteredTable.setColumnWidth(0, 150)
        self.lastEnteredTable.setColumnWidth(2, 170)
        self.lastEnteredTable.setColumnWidth(3, 150)
        self.lastEnteredTable.setRowCount(50)

    def update_LastEnteredTable(self):
        tablerow = 0
        for row in self.last_entered_queue:
            # print(row)
            self.lastEnteredTable.setItem(tablerow, 0, qtw.QTableWidgetItem(str(row['plate'])))  # insert name
            self.lastEnteredTable.setItem(tablerow, 1, qtw.QTableWidgetItem(str(row['car_owner'])))  # insert name
            self.lastEnteredTable.setItem(tablerow, 2, qtw.QTableWidgetItem(str(row['phone_number'])))  # insert name
            tablerow += 1


    #Cars Database Button:
    def openCarsDBwindow(self):
        d = CarDatabaseWindow()
        d.exec_()

    # Cars Database Button:
    def openActivityHoursDBwindow(self):
        d = ActivityHoursDatabaseWindow()
        d.exec_()

    #Activate Button:
    def activateBtnStatus(self):
        # if button is checked - system is off:
        if self.activateBtn.isChecked():
            self.activateBtn.setStyleSheet("background-color : lightgrey")
            self.activateBtn.setText("System Status: OFF\nClick to turn on")
            self.worker.pause()
            self.FeedLabel.hide()

        else:
            # set background color back to light-grey
            self.FeedLabel.show()
            self.activateBtn.setStyleSheet("background-color : lightblue")
            self.activateBtn.setText("System Status: ON\nClick to turn off")
            self.worker.cont()





class Login(QDialog):
    def __init__(self):
        super(Login, self).__init__()
        loadUi('./ui/login_dialog.ui', self)

    def execLogin(self):
        login_page = Login()
        login_page.exec_()
        global DB_USERNAME, DB_PASSWORD
        DB_USERNAME = login_page.username_lineEdit.text()
        DB_PASSWORD = login_page.password_lineEdit.text()




if __name__ == '__main__':
    app = QApplication(sys.argv)
    file = open("./MacOS.qss")
    with file:
        qss = file.read()
        app.setStyleSheet(qss)
    login = Login()
    login.execLogin()
    mainwindow = MainWindow()
    mainwindow.show()
    sys.exit(app.exec_())
