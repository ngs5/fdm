# UI helpers

import re
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import (QMessageBox, QDialog, QLineEdit, 
                             QDoubleSpinBox, QDialogButtonBox, QFileDialog,
                             QVBoxLayout, QFormLayout, QLabel, QGroupBox,
                             QWidget, QSpinBox)
                            

class BoxDialog(QMessageBox):
    '''Multipurpose message box'''
    def __init__(self, message_title = "Test", message = "This is a text",  buttons = None, detailed = None, title="FDM alert", icon = QMessageBox.Information):
        super(BoxDialog, self).__init__()
        
        self.setIcon(icon)
    
        self.setText(message)
        self.setInformativeText(message_title)
        self.setWindowTitle(title)
        if detailed is not None:
            self.setDetailedText(detailed)
        if buttons is None:
            self.setStandardButtons(QtWidgets.Ok)
#           self.buttonClicked.connect(msgbtn)
        else:
            self.setStandardButtons(buttons)
            
class ParamDialog(QDialog):
    '''Creates a form requesting FD computation parameters to user.'''
    NumGridRows = 2
    NumButtons = 3
 
    def __init__(self, threshs = [0.2], radius = 50, smooth_fwhm = [6, 6, 6], T1 = "", regex = "([0-9]+)_(?P<run>[0-9]+)_(?P<frame>[0-9]+).dcm", bounds = {}):
        super(ParamDialog, self).__init__()
        
        # FD paramters
        self.thresholds = QLineEdit()
        self.thresholds.setText(str(threshs)[1:-1])
        self.radius = QDoubleSpinBox()
        self.radius.setValue(radius)

        # tags and FD regressing
        self.smooth_fwhm = QLineEdit()
        self.smooth_fwhm.setText(str(smooth_fwhm)[1:-1])
        self.uploadButton = QtGui.QPushButton('Select', self)
        self.uploadButton.clicked.connect(self.setT1)
        self.T1 = QLineEdit()
        self.T1.setText(T1)
        self.T1.setReadOnly(True)
        self.T1layout = QtGui.QHBoxLayout()
        self.T1layout.addWidget(self.T1)
        self.T1layout.addWidget(self.uploadButton)

        #BK2
        # file selection
        self.filename_filter_regex = QLineEdit()
        self.filename_filter_regex.setText(regex)
        self.parseButton = QtGui.QPushButton('Parse', self)
        # send signal to regenerate window
        self.parseButton.clicked.connect(lambda : self.done(3))
        self.fields = None
        
        self.filter_layout = QtGui.QHBoxLayout()
        self.filter_layout.addWidget(self.filename_filter_regex)
        self.filter_layout.addWidget(self.parseButton)
        self.bounds = bounds
        self.filter_bounds_widget = None
        self.buildFieldBoundsWidgets()
        
        self.createFormGroupBox()
        
        # buttons
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
 
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.fileGroup)
        mainLayout.addWidget(self.FDGroup)
        mainLayout.addWidget(self.tagGroup)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)
 
        self.setWindowTitle("Parameters")
        self.show()
 
    def createFormGroupBox(self):
        self.fileGroup = QGroupBox("File selection")
        layout0 = QFormLayout()
        layout0.addRow(QLabel("Regexp"), self.filter_layout)
        layout0.addRow(self.filter_bounds_widget)        
        self.fileGroup.setLayout(layout0)

        self.FDGroup = QGroupBox("FD computation")
        layout1 = QFormLayout()
        layout1.addRow(QLabel("Thresholds [mm] (comma separated):"), self.thresholds)
        layout1.addRow(QLabel("Radius [mm]:"), self.radius)
        self.FDGroup.setLayout(layout1)

        self.tagGroup = QGroupBox("FD regression & tags")
        layout2 = QFormLayout()
        layout2.addRow(QLabel("Smooth FWHM (comma separated):"), self.smooth_fwhm)
        layout2.addRow(QLabel("T1 image:"), self.T1layout)
        self.tagGroup.setLayout(layout2)

    def buildFieldBoundsWidgets(self, recall=False):
        self.filter_bounds_widget = QWidget()
        self.spinBoxes = []
        self.fields = self.getRegexNamedFields(self.filename_filter_regex.text())
        
        filter_bounds_layout = QtGui.QVBoxLayout(self.filter_bounds_widget)
        for k in self.fields:
            self.spinBoxes.append((QSpinBox(), QSpinBox()))
            for i in [0,1]:
                self.spinBoxes[-1][i].setRange(0,100000)
                if k in self.bounds.keys():
                    self.spinBoxes[-1][i].setValue(self.bounds[k][i])
                else:
                    self.spinBoxes[-1][i].setValue(i*10000)
            form = QtGui.QHBoxLayout()
            form.addWidget(QLabel(k))
            form.addStretch()
            form.addWidget(QLabel('min'))
            form.addWidget(self.spinBoxes[-1][0])
            form.addWidget(QLabel('max'))
            form.addWidget(self.spinBoxes[-1][1])
            filter_bounds_layout.addLayout(form)

    def getBoundedFields(self):
        if self.fields is None:
            return {}
        ret = {}
        for i,k in enumerate(self.fields):
            ret[k] = (self.spinBoxes[i][0].value(), self.spinBoxes[i][1].value())
        return ret
    
    def getRegexNamedFields(self, target):
        '''Get all named fields from regex'''
        fields = []
        tmp = target.split('?') # for repeated capture
        for t in tmp:
            m = re.search('P<([a-zA-Z0-9]+)>\[0-9\]*', t)
            if m:
                fields.append(m.group(1))
        return fields
    
    def setT1(self):
        T1 = dialog_ask_file("T1 image", "*.nii")
        if T1 is not "":
            self.T1.setText(T1)   

#    def dialogAskFile(self, file_description, filter):    
#        options = QFileDialog.Options()
#        options |= QFileDialog.DontUseNativeDialog
#        fileName  = QFileDialog.getOpenFileName(self,"Please select {}".format(file_description), "", filter = filter, options=options)
#        if fileName:
#            return fileName[0]
        
def dialog_notify_error(*args, **kwargs):
    print(kwargs['message_title'] + ", " + kwargs['message'])
    errdialog = BoxDialog(*args, **kwargs, icon = QMessageBox.Warning, buttons = QMessageBox.Ok)
    errdialog.exec_()

def dialog_ask_question(*args, **kwargs):
    qdialog = BoxDialog(*args, buttons =  QMessageBox.Ok | QMessageBox.Cancel, title = "FDM dialog", **kwargs)
    return qdialog.exec_() == 1024

#    def dialogAbort(self, *args, **kwargs):
#        abdialog = BoxDialog(*args, **kwargs, buttons = QMessageBox.Abort)
#        print(abdialog.exec_())   
#            
def dialog_ask_folder(folder_description):
    print("enter")
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    folderName  = QFileDialog.getExistingDirectory(None, "Please select {}".format(folder_description), "", options=options)
    print("exit")
    if folderName:
        return folderName
    
    QFileDialog.getExistingDirectory()

def dialog_ask_file(file_description, filter):    
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    fileName  = QFileDialog.getOpenFileName(None,"Please select {}".format(file_description), "", filter = filter, options=options)
    if fileName:
        return fileName[0]