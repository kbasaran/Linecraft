from PySide6 import QtWidgets as qtw
from PySide6 import QtCore as qtc

class MainWindow(qtw.QWidget):

    signal_test_data = qtc.Signal(object)

    def __init__(self):
        super().__init__()
        self.populate_widgets()
        self.make_connections()

    def populate_widgets(self):
        layout = qtw.QVBoxLayout(self)
        self.text_window = qtw.QTextEdit()
        add_text_button = qtw.QPushButton("Hop", clicked=self.test_signaller)
        layout.addWidget(self.text_window)
        layout.addWidget(add_text_button)

    def make_connections(self):
        self.signal_test_data.connect(self.add_text)

    @qtc.Slot()
    def add_text(self, load):
        widget = self.text_window
        text = widget.toPlainText()
        new_text = str(type(load)) + " => " + str(load) + "\n" + text
        widget.setText(new_text)

    def test_signaller(self):
        self.signal_test_data.emit(None)
        self.signal_test_data.emit([1,2,3])

def main():
    qApp or qtw.QApplication()
    mw = MainWindow()
    mw.show()
    qApp.exec()

if __name__ == "__main__":
    main()
