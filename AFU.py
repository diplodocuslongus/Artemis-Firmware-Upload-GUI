"""
This is a simple firmware upload GUI designed for the Artemis platform.
Very handy for updating devices in the field without the need for compiling
and uploading through Arduino.

Based on gist by Stefan Lehmann: https://gist.github.com/stlehmann/bea49796ad47b1e7f658ddde9620dff1

MIT license

TODO:

Push user to upgrade bootloader as needed

"""
from typing import Iterator, Tuple
from serial.tools.list_ports import comports
from PyQt5.QtCore import QSettings, QProcess
from PyQt5.QtWidgets import QWidget, QLabel, QComboBox, QGridLayout, \
    QPushButton, QApplication, QLineEdit, QFileDialog
from PyQt5.QtGui import QCloseEvent

# import artemis_svl

# Setting constants
SETTING_PORT_NAME = 'port_name'
SETTING_FILE_LOCATION = 'message'
SETTING_BAUD_RATE = '921600'

progressCount = 1

guiVersion = 'v1.0'


def gen_serial_ports() -> Iterator[Tuple[str, str]]:
    """Return all available serial ports."""
    ports = comports()
    return ((p.description, p.device) for p in ports)

# noinspection PyArgumentList


class RemoteWidget(QWidget):
    """Main Widget."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)

        # File location line edit
        self.msg_label = QLabel(self.tr('Firmware File:'))
        self.fileLocation_lineedit = QLineEdit()
        self.msg_label.setBuddy(self.msg_label)
        self.fileLocation_lineedit.setEnabled(False)
        self.fileLocation_lineedit.returnPressed.connect(
            self.on_browse_btn_pressed)

        # Browse for new file button
        self.browse_btn = QPushButton(self.tr('Browse'))
        self.browse_btn.setEnabled(True)
        self.browse_btn.pressed.connect(self.on_browse_btn_pressed)

        # Port Combobox
        self.port_label = QLabel(self.tr('COM Port:'))
        self.port_combobox = QComboBox()
        self.port_label.setBuddy(self.port_combobox)
        self.update_com_ports()

        # Refresh Button
        self.refresh_btn = QPushButton(self.tr('Refresh'))
        self.refresh_btn.pressed.connect(self.on_refresh_btn_pressed)

        # Baudrate Combobox
        self.baud_label = QLabel(self.tr('Baud:'))
        self.baud_combobox = QComboBox()
        self.baud_label.setBuddy(self.baud_combobox)
        self.update_baud_rates()

        # Upload Button
        self.upload_btn = QPushButton(self.tr('Upload'))
        self.upload_btn.pressed.connect(self.on_upload_btn_pressed)

        # Status bar
        self.status_label = QLabel(self.tr('Status:'))
        self.status = QLabel(self.tr(' '))

        # Arrange Layout
        layout = QGridLayout()
        layout.addWidget(self.msg_label, 0, 0)
        layout.addWidget(self.fileLocation_lineedit, 0, 1)
        layout.addWidget(self.browse_btn, 0, 2)

        layout.addWidget(self.port_label, 1, 0)
        layout.addWidget(self.port_combobox, 1, 1)
        layout.addWidget(self.refresh_btn, 1, 2)

        layout.addWidget(self.baud_label, 2, 0)
        layout.addWidget(self.baud_combobox, 2, 1)
        layout.addWidget(self.upload_btn, 3, 2)

        layout.addWidget(self.status_label, 3, 0)
        layout.addWidget(self.status, 3, 1)
        self.setLayout(layout)

        self._load_settings()

    def _load_settings(self) -> None:
        """Load settings on startup."""
        settings = QSettings()

        # port name
        port_name = settings.value(SETTING_PORT_NAME)
        if port_name is not None:
            index = self.port_combobox.findData(port_name)
            if index > -1:
                self.port_combobox.setCurrentIndex(index)

        # last message
        msg = settings.value(SETTING_FILE_LOCATION)
        if msg is not None:
            self.fileLocation_lineedit.setText(msg)

        baud = settings.value(SETTING_BAUD_RATE)
        if baud is not None:
            index = self.baud_combobox.findData(baud)
            if index > -1:
                self.baud_combobox.setCurrentIndex(index)

    def _save_settings(self) -> None:
        """Save settings on shutdown."""
        settings = QSettings()
        settings.setValue(SETTING_PORT_NAME, self.port)
        settings.setValue(SETTING_FILE_LOCATION,
                          self.fileLocation_lineedit.text())
        settings.setValue(SETTING_BAUD_RATE, self.baudRate)

    def show_error_message(self, msg: str) -> None:
        """Show a Message Box with the error message."""
        QMessageBox.critical(self, QApplication.applicationName(), str(msg))

    def update_com_ports(self) -> None:
        """Update COM Port list in GUI."""
        self.port_combobox.clear()
        for name, device in gen_serial_ports():
            self.port_combobox.addItem(name, device)

    def update_baud_rates(self) -> None:
        """Update COM Port list in GUI."""
        self.baud_combobox.addItem("921600", 921600)
        self.baud_combobox.addItem("460800", 460800)
        self.baud_combobox.addItem("115200", 115200)
        # self.baud_combobox.addItem("9600", 9600) #Used to test comm failure

    @property
    def port(self) -> str:
        """Return the current serial port."""
        return self.port_combobox.currentData()

    @property
    def baudRate(self) -> str:
        """Return the current baud rate."""
        return self.baud_combobox.currentData()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle Close event of the Widget."""
        self._save_settings()

        event.accept()

    def on_refresh_btn_pressed(self) -> None:
        self.update_com_ports()

    def on_upload_btn_pressed(self) -> None:
        """Check if port is available"""
        portAvailable = False
        ports = comports()
        for p in ports:
            if (p.device == self.port):
                portAvailable = True
        if (portAvailable == False):
            self.status.setText("Port No Longer Available")
            return

        """Check if file exists"""
        fileExists = False
        try:
            f = open(self.fileLocation_lineedit.text())
            fileExists = True
        except IOError:
            fileExists = False
        finally:
            if (fileExists == False):
                self.status.setText("File Not Found")
                return
            f.close()

        global progressCount
        progressCount = 0

        self.status.setText("Uploading ")

        self.process = QProcess()
        self.process.readyReadStandardError.connect(
            self.onReadyReadStandardError)
        self.process.readyReadStandardOutput.connect(
            self.onReadyReadStandardOutput)

        self.process.start("artemis_svl.exe " + str(self.port) +
                           " -f\"" + self.fileLocation_lineedit.text() + "\"" + " -b" + str(self.baudRate))

    def onReadyReadStandardError(self):
        error = self.process.readAllStandardError().data().decode()
        # print(error)
        self.status.setText(error)

    def onReadyReadStandardOutput(self):
        """Parse the output from the process. Update our status as we go."""
        result = self.process.readAllStandardOutput().data().decode()
        # print(result)
        if ("complete" in result):
            self.status.setText("Complete")
        elif ("failed" in result):
            self.status.setText("Upload Failed")
        elif ("open" in result):
            self.status.setText("Port In Use / Please Close")
        else:  # The '#' is displayed 50 times until completion
            global progressCount
            progressCount = progressCount + result.count("#")
            # print(progressCount)
            for i in range(int(progressCount / 3)):
                current = self.status.text() + "."
                self.status.setText(current)

    def on_browse_btn_pressed(self) -> None:
        """Open dialog to select bin file."""
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(
            None,
            "Select Firmware to Upload",
            "",
            "Firmware Files (*.bin);;All Files (*)",
            options=options)
        if fileName:
            self.fileLocation_lineedit.setText(fileName)


if __name__ == '__main__':
    import sys
    app = QApplication([])
    app.setOrganizationName('SparkFun')
    app.setApplicationName('Artemis Firmware Uploader')
    w = RemoteWidget()
    w.show()
    sys.exit(app.exec_())
