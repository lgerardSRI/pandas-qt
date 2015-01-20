# -*- coding: utf-8 -*-
import os

from encodings.aliases import aliases as _encodings

import pandas
import sip
sip.setapi('QString', 2)
sip.setapi('QVariant', 2)

from chardet.universaldetector import UniversalDetector
from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtCore import Qt


from pandasqt.DataFrameModel import DataFrameModel
from pandasqt.ColumnDtypeModel import DtypeComboDelegate
from pandasqt.ui import icons_rc

class DelimiterValidator(QtGui.QRegExpValidator):
    """A Custom RegEx Validator.

    The validator checks, if the input has a length of 1.
    The input may contain any non-whitespace-character
    as denoted by the RegEx term `\S`.

    """

    def __init__(self, parent=None):
        """Constructs the object with the given parent.

        Args:
            parent (QObject, optional): Causes the objected to be owned
                by `parent` instead of Qt. Defaults to `None`.

        """
        super(DelimiterValidator, self).__init__(parent)
        re = QtCore.QRegExp('\S{1}')
        self.setRegExp(re)


class DelimiterSelectionWidget(QtGui.QGroupBox):
    """A custom widget with different text delimiter signs.

    A user can choose between 3 predefined and one user defined
    text delimiter characters. Default delimiters include `semicolon`,
    `colon` and `tabulator`. The user defined delimiter may only have
    a length of 1 and may not include any whitespace character.

    Attributes:
        delimiter (QtCore.pyqtSignal): This signal is emitted, whenever a
            delimiter character is selected by the user.
        semicolonRadioButton (QtGui.QRadioButton): A radio button to
            select the `semicolon` character as delimiter.
        commaRadioButton (QtGui.QRadioButton): A radio button to select
            the `comma` character as delimiter.
        tabRadioButton (QtGui.QRadioButton): A radio button to select
            the `tabulator` character as delimiter.
        otherRadioButton (QtGui.QRadioButton): A radio button to select
            the given input text as delimiter.
        otherSeparatorLineEdit (QtGui.QLineEdit): An input line to let the
            user enter one character only, which may be used as delimiter.

    """

    delimiter = QtCore.pyqtSignal('QString')

    def __init__(self, parent=None):
        """Constructs the object with the given parent.

        Args:
            parent (QObject, optional): Causes the objected to be owned
                by `parent` instead of Qt. Defaults to `None`.

        """
        super(DelimiterSelectionWidget, self).__init__(parent)
        self.semicolonRadioButton = None
        self.commaRadioButton = None
        self.tabRadioButton = None
        self.otherRadioButton = None
        self.otherSeparatorLineEdit = None
        self._initUI()


    def _initUI(self):
        """Creates the inital layout with all subwidgets.

        The layout is a `QHBoxLayout`. Each time a radio button is
        selected or unselected, a slot
        `DelimiterSelectionWidget._delimiter` is called.
        Furthermore the `QLineEdit` widget has a custom regex validator
        `DelimiterValidator` enabled.

        """
        #layout = QtGui.QHBoxLayout(self)

        self.semicolonRadioButton = QtGui.QRadioButton(u'Semicolon')
        self.commaRadioButton = QtGui.QRadioButton(u'Comma')
        self.tabRadioButton = QtGui.QRadioButton(u'Tab')
        self.otherRadioButton = QtGui.QRadioButton(u'Other')
        self.semicolonRadioButton.setChecked(True)

        self.otherSeparatorLineEdit = QtGui.QLineEdit(self)
        self.otherSeparatorLineEdit.setEnabled(False)

        self.semicolonRadioButton.toggled.connect(self._delimiter)
        self.commaRadioButton.toggled.connect(self._delimiter)
        self.tabRadioButton.toggled.connect(self._delimiter)

        self.otherRadioButton.toggled.connect(self._enableLine)
        self.otherSeparatorLineEdit.textChanged.connect(lambda: self._delimiter(True))
        self.otherSeparatorLineEdit.setValidator(DelimiterValidator(self))

        currentLayout = self.layout()
        # unset and delete the current layout in order to set a new one
        if currentLayout is not None:
            del currentLayout

        layout = QtGui.QHBoxLayout()
        layout.addWidget(self.semicolonRadioButton)
        layout.addWidget(self.commaRadioButton)
        layout.addWidget(self.tabRadioButton)
        layout.addWidget(self.otherRadioButton)
        layout.addWidget(self.otherSeparatorLineEdit)
        self.setLayout(layout)

    @QtCore.pyqtSlot('QBool')
    def _enableLine(self, toggled):
        self.otherSeparatorLineEdit.setEnabled(toggled)

    def currentSelected(self):
        """Returns the currently selected delimiter character.

        Returns:
            str: One of `,`, `;`, `\t`, `*other*`.

        """
        if self.commaRadioButton.isChecked():
            return ','
        elif self.semicolonRadioButton.isChecked():
            return ';'
        elif self.tabRadioButton.isChecked():
            return '\t'
        elif self.otherRadioButton.isChecked():
            return self.otherSeparatorLineEdit.text()
        return


    @QtCore.pyqtSlot('QBool')
    def _delimiter(self, checked):
        if checked:
            if self.commaRadioButton.isChecked():
                self.delimiter.emit(',')
            elif self.semicolonRadioButton.isChecked():
                self.delimiter.emit(';')
            elif self.tabRadioButton.isChecked():
                self.delimiter.emit('\t')
            elif self.otherRadioButton.isChecked():
                ret = self.otherSeparatorLineEdit.text()
                if len(ret) > 0:
                    self.delimiter.emit(ret)

    def reset(self):
        """Resets this widget to its initial state.

        """
        self.semicolonRadioButton.setChecked(True)
        self.otherSeparatorLineEdit.setText('')


class CSVImportDialog(QtGui.QDialog):
    """A dialog to import any csv file into a pandas data frame.

    This modal dialog enables the user to enter any path to a csv
    file and parse this file with or without a header and with special
    delimiter characters.

    On a successful load, the data can be previewed and the column data
    types may be edited by the user.

    After all configuration is done, the dataframe and the underlying model
    may be used by the main application.

    Attributes:
        load (QtCore.pyqtSignal): This signal is emitted, whenever the
            dialog is successfully closed, e.g. when the ok button is
            pressed.
    """

    load = QtCore.pyqtSignal('QAbstractItemModel')

    def __init__(self, parent=None):
        """Constructs the object with the given parent.

        Args:
            parent (QObject, optional): Causes the objected to be owned
                by `parent` instead of Qt. Defaults to `None`.

        """
        super(CSVImportDialog, self).__init__(parent)
        self._modal = True
        self._windowTitle = u'Import CSV'
        self._encodingKey = None
        self._filename = None
        self._delimiter = None
        self._header = None
        self._initUI()

    def _initUI(self):
        """Initiates the user interface with a grid layout and several widgets.

        """
        self.setModal(self._modal)
        self.setWindowTitle(self._windowTitle)

        layout = QtGui.QGridLayout()

        self._filenameLabel = QtGui.QLabel(u'Choose File', self)
        self._filenameLineEdit = QtGui.QLineEdit(self)
        self._filenameLineEdit.textEdited.connect(self._updateFilename)
        chooseFileButtonIcon = QtGui.QIcon(QtGui.QPixmap(':/icons/document-open.png'))
        self._chooseFileAction = QtGui.QAction(self)
        self._chooseFileAction.setIcon(chooseFileButtonIcon)
        self._chooseFileAction.triggered.connect(self._openFile)

        self._chooseFileButton = QtGui.QToolButton(self)
        self._chooseFileButton.setDefaultAction(self._chooseFileAction)

        layout.addWidget(self._filenameLabel, 0, 0)
        layout.addWidget(self._filenameLineEdit, 0, 1, 1, 2)
        layout.addWidget(self._chooseFileButton, 0, 3)

        self._encodingLabel = QtGui.QLabel(u'File Encoding', self)

        encoding_names = map(lambda x: x.upper(), sorted(list(set(_encodings.viewvalues()))))
        self._encodingComboBox = QtGui.QComboBox(self)
        self._encodingComboBox.addItems(encoding_names)
        self._encodingComboBox.activated.connect(self._updateEncoding)

        layout.addWidget(self._encodingLabel, 1, 0)
        layout.addWidget(self._encodingComboBox, 1, 1, 1, 1)

        self._hasHeaderLabel = QtGui.QLabel(u'Header Available?', self)
        self._headerCheckBox = QtGui.QCheckBox(self)
        self._headerCheckBox.toggled.connect(self._updateHeader)

        layout.addWidget(self._hasHeaderLabel, 2, 0)
        layout.addWidget(self._headerCheckBox, 2, 1)

        self._delimiterLabel = QtGui.QLabel(u'Column Delimiter', self)
        self._delimiterBox = DelimiterSelectionWidget(self)
        self._delimiter = self._delimiterBox.currentSelected()
        self._delimiterBox.delimiter.connect(self._updateDelimiter)

        layout.addWidget(self._delimiterLabel, 3, 0)
        layout.addWidget(self._delimiterBox, 3, 1, 1, 3)

        self._tabWidget = QtGui.QTabWidget(self)
        self._previewTableView = QtGui.QTableView(self)
        self._datatypeTableView = QtGui.QTableView(self)
        self._tabWidget.addTab(self._previewTableView, u'Preview')
        self._tabWidget.addTab(self._datatypeTableView, u'Change Column Types')
        layout.addWidget(self._tabWidget, 4, 0, 3, 4)

        self._datatypeTableView.horizontalHeader().setDefaultSectionSize(200)
        self._datatypeTableView.setItemDelegateForColumn(1, DtypeComboDelegate(self._datatypeTableView))


        self._loadButton = QtGui.QPushButton(u'Load Data', self)
        #self.loadButton.setAutoDefault(False)

        self._cancelButton = QtGui.QPushButton(u'Cancel', self)
        # self.cancelButton.setDefault(False)
        # self.cancelButton.setAutoDefault(True)

        self._buttonBox = QtGui.QDialogButtonBox(self)
        self._buttonBox.addButton(self._loadButton, QtGui.QDialogButtonBox.AcceptRole)
        self._buttonBox.addButton(self._cancelButton, QtGui.QDialogButtonBox.RejectRole)
        self._buttonBox.accepted.connect(self.accepted)
        self._buttonBox.rejected.connect(self.reject)
        layout.addWidget(self._buttonBox, 9, 2, 1, 2)
        self._loadButton.setDefault(False)
        self._filenameLineEdit.setFocus()

        self._statusBar = QtGui.QStatusBar(self)
        self._statusBar.setSizeGripEnabled(False)
        layout.addWidget(self._statusBar, 8, 0, 1, 4)
        self.setLayout(layout)

    @QtCore.pyqtSlot('QString')
    def updateStatusBar(self, message):
        """Updates the status bar widget of this dialog with the given message.

        This method is also a `SLOT()`.
        The message will be shown for only 5 seconds.

        Args:
            message (QString): The new message which will be displayed.

        """
        self._statusBar.showMessage(message, 5000)

    @QtCore.pyqtSlot()
    def _openFile(self):
        """Opens a file dialog and sets a value for the QLineEdit widget.

        This method is also a `SLOT`.

        """
        ret = QtGui.QFileDialog.getOpenFileName(self, self.tr(u'open file'), filter='Comma Separated Values (*.csv)')
        if ret:
            self._filenameLineEdit.setText(ret)
            self._updateFilename()

    @QtCore.pyqtSlot('QBool')
    def _updateHeader(self, toggled):
        """Changes the internal flag, whether the csv file contains a header or not.

        This method is also a `SLOT`.

        In addition, after toggling the corresponding checkbox, the
        `_previewFile` method will be called.

        Args:
            toggled (boolean): A flag indicating the status of the checkbox.
                The flag will be used to update an internal variable.

        """
        self._header = 0 if toggled else None
        self._previewFile()

    @QtCore.pyqtSlot()
    def _updateFilename(self):
        """Calls several methods after the filename changed.

        This method is also a `SLOT`.
        It checks the encoding of the changed filename and generates a
        preview of the data.

        """
        self._filename = self._filenameLineEdit.text()
        self._guessEncoding(self._filename)
        self._previewFile()

    def _guessEncoding(self, path):
        """Opens a file from the given `path` and checks the file encoding.

        The file must exists on the file system and end with the extension
        `.csv`. The file is read line by line until the encoding could be
        guessed.
        On a successfull identification, the widgets of this dialog will be
        updated.

        Args:
            path (string): Path to a csv file on the file system.

        """
        if os.path.exists(path) and path.lower().endswith('csv'):
            encodingDetector = UniversalDetector()
            with open(path, 'r') as fp:
                for line in fp:
                    encodingDetector.feed(line)
                    if encodingDetector.done:
                        break
            encodingDetector.close()
            result = encodingDetector.result['encoding']
            result = result.replace('-','_')

            self._encodingKey = _calculateEncodingKey(result)
            if self._encodingKey:
                index = self._encodingComboBox.findText(result.upper())
                self._encodingComboBox.setCurrentIndex(index)

    @QtCore.pyqtSlot('int')
    def _updateEncoding(self, index):
        """Changes the value of the encoding combo box to the value of given index.

        This method is also a `SLOT`.
        After the encoding is changed, the file will be reloaded and previewed.

        Args:
            index (int): An valid index of the combo box.

        """
        encoding = self._encodingComboBox.itemText(index)
        encoding = encoding.lower()

        self._encodingKey = _calculateEncodingKey(encoding)
        self._previewFile()

    @QtCore.pyqtSlot('QString')
    def _updateDelimiter(self, delimiter):
        """Changes the value of the delimiter for the csv file.

        This method is also a `SLOT`.

        Args:
            delimiter (string): The new delimiter.

        """
        self._delimiter = delimiter
        self._previewFile()

    def _previewFile(self):
        """Updates the preview widgets with new models for both tab panes.

        """
        dataFrame = self._loadCSVDataFrame()
        dataFrameModel = DataFrameModel(dataFrame)
        self._previewTableView.setModel(dataFrameModel)
        columnModel = dataFrameModel.columnDtypeModel()
        columnModel.changeFailed.connect(self.updateStatusBar)
        self._datatypeTableView.setModel(columnModel)

    def _loadCSVDataFrame(self):
        """Loads the given csv file with pandas and generate a new dataframe.

        The file will be loaded with the configured encoding, delimiter
        and header.
        If any execptions will occur, an empty Dataframe is generated
        and a message will appear in the status bar.

        Returns:
            pandas.DataFrame: A dataframe containing all the available
                information of the csv file.

        """
        if self._filename and os.path.exists(self._filename) and self._filename.endswith('.csv'):
            # default fallback if no encoding was found/selected
            encoding = self._encodingKey or 'uft8'

            try:
                dataFrame = pandas.read_csv(self._filename,
                    sep=self._delimiter, encoding=encoding,
                    header=self._header)
            except Exception, err:
                self.updateStatusBar(str(err))
                return pandas.DataFrame()
            self.updateStatusBar('Preview generated.')
            return dataFrame
        self.updateStatusBar('File does not exists or does not end with .csv')
        return pandas.DataFrame()

    def _resetWidgets(self):
        """Resets all widgets of this dialog to its inital state.

        """
        self._filenameLineEdit.setText('')
        self._encodingComboBox.setCurrentIndex(0)
        self._delimiterBox.reset()
        self._headerCheckBox.setChecked(False)
        self._previewTableView.setModel(None)
        self._datatypeTableView.setModel(None)

    @QtCore.pyqtSlot()
    def accepted(self):
        """Successfully close the widget and return the loaded model.

        This method is also a `SLOT`.
        The dialog will be closed, when the `ok` button is pressed. If
        a `DataFrame` was loaded, it will be emitted by the signal `load`.

        """
        model = self._previewTableView.model()
        if model is not None:
            df = model.dataFrame().copy()
            dfModel = DataFrameModel(df)
            self.load.emit(dfModel)
        self._resetWidgets()
        self.accept()

    @QtCore.pyqtSlot()
    def rejected():
        """Close the widget and reset its inital state.

        This method is also a `SLOT`.
        The dialog will be closed and all changes reverted, when the
        `cancel` button is pressed.

        """
        self._resetWidgets()
        self.reject()

class CSVExportWidget(QtGui.QDialog):
    pass


def _calculateEncodingKey(comparator):
    """Gets the first key of all available encodings where the corresponding
    value matches the comparator.

    Args:
        comparator (string): A view name for an encoding.

    Returns:
        str: A key for a specific encoding used by python.

    """
    encodingName = None
    for k, v in _encodings.viewitems():
        if v == comparator:
            encodingName = k
            break
    return encodingName