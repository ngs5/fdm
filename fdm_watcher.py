#    Standalone module classes

import os, queue, re
from shutil import rmtree

import pandas

import matlab

from watchdog.observers import Observer

from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import (QMainWindow, QWidget, QTextEdit, 
                             QGridLayout, QAction)
import pyqtgraph as pg
import pyqtgraph.exporters

import fdm_settings as s
from fdm_base import FD
from fdm_batch_helper import Batch 
from fdm_UI_helper import (ParamDialog, dialog_notify_error, dialog_ask_question,
                           dialog_ask_folder, dialog_ask_file)
from fdm_file_event import CreateFileEventHandler

class FDMWatcher(QMainWindow):
    '''Standalone module aligning .dcm files in real time and displaying frame displacement.'''
    def __init__(self, spm):
        super().__init__()
        
        self.populated = False
        self.justRanBatch = False
        self.watching = False
        self.waitingBatch = False
        
        self.watch_directory = s.DEFAULT_WATCH_DIRECTORY_PATH

        self.ext = ".dcm" # only works with .dcm atm

        #BK1
        # filter .dcm to process based on regex
        self.regex_input_filenames = s.DEFAULT_INPUT_FILTER
#        self.input_regex_named_fields = self.getRegexNamedFields(self.regex_input_filenames)
        self.input_bounded_fields = {}
        # set permissive constraints
#        for i in self.input_regex_named_fields:
#            self.constrainsDict[i] = (0,10**7)
#        self.constrainsDict['run'] = (2, 2)
              
        self._spm = spm # matlab spm shared engine interface
        self._fd = FD() # FD computation and graphing
        self._batch = Batch(spm) # edit and run batches
        
        # plots -> initialised in _init_UI()
        self._plot_translat = None
        self._plot_rotat = None
        self._plot_fd = None
        
        self.outputSamples = {} # outputSamples is a list to maintain compatibility with OpenNFT data structures
        self.T1 = None
        self.smooth_fwhm = [6,6,6]
        
        self.dcm_queue = queue.Queue() # Will be passed by reference to  CreateFileEventHandler
        self.nii_queue = queue.Queue()
        self.log_filenames = []

        self._init_UI()

        self.fs_observer_watch = None
        self.fs_observer_nii = None
        
        self._set_watch_directory()
        self.update_parameters_dialog()
        self._populate_queue()

        # setup call timer
        self._main_loop_call_timer = QtCore.QTimer()
        self._main_loop_call_timer.timeout.connect(self._main_loop) # call main loop
        self._main_loop_call_timer.start()
        
#        self.showdialog()
#        self.start()
        
#    def workingFolder(self):
#        return self.workingFolder
    
    def _set_watch_directory(self, ask_watch_directory = True):

        if self.justRanBatch: 
            dialog_notify_error(message_title = "ERROR", message = "Resuming watch after spm batch execution is not yet supported. FDM is highly likely to crash.",  detailed = None, title="FDM error")
 
        if ask_watch_directory:
            self.watch_directory = dialog_ask_folder("watch folder")
            if self.watch_directory is None:
                return
        else:
            self.watch_directory = s.DEFAULT_WATCH_DIRECTORY_PATH
        
        self.destination_folder = self.watch_directory # UNUSED : by default we create .nii in same folder
        self.folder_path.setText(self.watch_directory)
        self._spm.watch_directory = self.watch_directory
        
        tmp =self._reset_data()
        self.watching = False
        if self.fs_observer_watch:
            self.fs_observer_watch.stop()
        
        if self.fs_observer_nii:
            self.fs_observer_nii.stop()
            
        self._setup_filesystem_watching()
        self.watching = tmp
#        self.watching = False
        

    def _reset_data(self):
        self._fd.xmax = s.PLOT_INITIAL_XMAX
        # set initial movement to 0
        self.outputSamples['motCorrParam'] = list(matlab.double([[1e-05,1e-05,1e-05,1e-05,1e-05,1e-05]]))
        # reset queue
        with self.dcm_queue.mutex:
             self.dcm_queue.queue.clear()
        with self.nii_queue.mutex:
             self.nii_queue.queue.clear()      
             
        self.status("Queue cleared")
        
        # clear .nii folder and recreate
        print(self.watch_directory)
        if os.path.isdir(s.NII_DIRECTORY_PATH) and dialog_ask_question(message_title = "Clear its content?", message = "Detected previous fdm temporary data in {}.".format(s.NII_DIRECTORY_PATH)):
            rmtree(s.NII_DIRECTORY_PATH, True)
            os.mkdir(s.NII_DIRECTORY_PATH) 
            self.status("fdm temporary data cleared")
            self.drawMcPlots()
            return True
        elif not os.path.isdir(s.NII_DIRECTORY_PATH):
            os.mkdir(s.NII_DIRECTORY_PATH)
        else:
            self.status("fdm processing subfolder left untouched. Loading past FD data if applicable")
            
           
            # print(history_csv)
            # history_csv = os.path.join(s.NII_DIRECTORY_PATH, s.FDM_OUTPUT)
#            if os.path.isfile(history_csv):
#                df = pd.read_csv(history_csv) 
#                self.outputSamples['motCorrParam'] = df.iloc[:,1:7].as_matrix()
#                print(self.outputSamples['motCorrParam'])
#                self.log_filenames = list(df.iloc[:,7].as_matrix())
#                print(df)
#                self._fd.xmax = len(self.log_filenames)
            
            self.drawMcPlots()
            return False
        
    def startToggle(self, pause=False):
        if self.watching or pause is True:
            self.statusBar().showMessage('Paused. PRESS Ctrl+S TO RESUME PROCESSING')
            self.watching = False   
            return
        else:
            if self.justRanBatch: 
                dialog_notify_error(message_title = "ERROR", message = "Resuming watch after spm batch execution is not yet supported. FDM is highly likely to crash.",  detailed = None, title="FDM error")
            self.statusBar().showMessage('Starting')
            self.watching = True
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.fs_observer_watch is not None:
            self.fs_observer_watch.stop()
        if self.fs_observer_nii is not None:
            self.fs_observer_nii.stop()

        self._main_loop_call_timer.stop()  
        
        # TODO : ask question here
        if dialog_ask_question(message_title = "Save FD plot to svg ?", message = "Will be saved to {}".format(os.path.join(s.STAT_DIRECTORY_PATH, self._spm.reference_nii[:-4])+s.PLOT_EXPORT_FORMAT)):
            self._write_data()
        
        print("Exiting")

    def _init_UI(self):               
        '''init UI of main window'''

        self.setGeometry(300, 300, 350, 500)
        self.setWindowTitle('Real-Time Framewise Displacement')
        self.status('Paused. PRESS Ctrl+S TO RESUME PROCESSING')

        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.mainLayout = QtGui.QVBoxLayout(self.main_widget)

        self.folder_path = QTextEdit()
        self.mainLayout.addWidget(self.folder_path)
        self.folder_path.setFixedHeight(50)
        self.folder_path.setReadOnly(True)
        bkgcolor = self.palette().color(QtGui.QPalette.Background)
#        print(bkgcolor)
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Base, bkgcolor)
        self.folder_path.setPalette(palette);

        self.grid = QGridLayout()
        self.mainLayout.addLayout(self.grid)

        self._plot_translat = self._fd.create_mc_plot(self.main_widget, self.grid)
        self._plot_rotat = self._fd.create_mc_plot(self.main_widget, self.grid)
        self._plot_fd = self._fd.create_mc_plot(self.main_widget, self.grid)
        self.drawMcPlots()
        
        self.menu()
        self.main_widget.show()
#
        self.show()
        
    def status(self, message, local_verbose = True):
#        self.statusBar().showMessage("In folder {}\n{}".format(self.watch_directory, message))
        if s.ECHO_STATUS_BAR_IN_TERMINAL:
            print("\n---{}".format(message))
        self.statusBar().showMessage("{}".format(message))

    def menu(self):
        exitAction = QAction('Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(self.close)

        startAction = QAction('Start/Stop processing', self)
        startAction.setShortcut('Ctrl+S')
        startAction.setStatusTip('Start/Stop processing files')
        startAction.triggered.connect(self.startToggle)
        
        selectSourceFolder = QAction('Watch Folder', self)
        selectSourceFolder.setShortcut('Ctrl+W')
        selectSourceFolder.setStatusTip('Select folder to watch for new .dcm')
        selectSourceFolder.triggered.connect(lambda: self._set_watch_directory(True))
    
        setParameters = QAction('Set Parameters', self)
        setParameters.setShortcut('Ctrl+P')
        setParameters.setStatusTip('Choose parameters for FD computation manually')
        setParameters.triggered.connect(self.update_parameters_dialog)
        
        readParameters = QAction('Read Parameters', self)
        readParameters.setShortcut('Ctrl+R')
        readParameters.setStatusTip('Read parameters from .ini config file (see example in fdm folder)')
        readParameters.triggered.connect(self.create_form_group_box)

        regressSPMBatch = QAction('Regress FD', self)
        regressSPMBatch.setShortcut('Ctrl+F')
        regressSPMBatch.setStatusTip('Regress FD to activation map using SPM batch')
        regressSPMBatch.triggered.connect(self.preprocess_fdm)

        customSPMBatch = QAction('Run custom SPM batch', self)
        customSPMBatch.setShortcut('Ctrl+C')
        customSPMBatch.setStatusTip('Apply custom SPM batch to data')
        customSPMBatch.triggered.connect(self.run_custom_batch)

        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)  # required for OSX
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(startAction)
        fileMenu.addAction(selectSourceFolder)
        fileMenu.addAction(exitAction)

        paramMenu = menubar.addMenu('&Parameters')
        paramMenu.addAction(setParameters)
        paramMenu.addAction(readParameters)

        paramMenu = menubar.addMenu('&Processing')
        paramMenu.addAction(regressSPMBatch)
        paramMenu.addAction(customSPMBatch)
        
    def preprocess_fdm_dcm(self): 
        self.status('---- Editing batch...')
        self.watching = False; 
        self._batch.editPreprocDCMBatch(self.watch_directory)
        # TODO -> more stuff

    def run_custom_batch(self): 
        self.watching = False; 
        try:
            if self.watch_directory is None:
                raise UserWarning
            target = dialog_ask_file("custom batch", "*.m")
            print(target)
            if target is not '':
                self.status('---- Editing {}...'.format(target))
                ret = self._batch.batch_edit(target, self.watch_directory, self._fd.all_fd(), self.T1, self.smooth_fwhm,forcedName = "custom_edit.m")
                self.out, self.err, self.future = self._batch.run_custom_batch(self.watch_directory)
                self._future_management('---- Running {}...'.format(target))
                if not ret:
                    raise FileNotFoundError
            else:
                return
        except UserWarning:
            dialog_notify_error(message_title = "ERROR in running custom spm batch", message = "Please select a watch folder.",  detailed = None, title="FDM error")
        except FileNotFoundError:
            dialog_notify_error(message_title = "ERROR in running custom spm batch", message = "Some files requested by the batch were not found (see custom_batch_edit.m in fdm folder). Is the fdm_proc directory empty ?",  detailed = None, title="FDM error")
        except:
            dialog_notify_error(message_title = "ERROR in running custom spm batch", message = "Unknown error. It is often a good idea to open the SPM GUI in matlab when launching a custom batch (e.g. to interact with potential SPM dialogs). Please also check and run the edited batch (custom_batch_edit.m) manually to probe for errors.",  detailed = None, title="FDM error")
            raise   
        
    
    def preprocess_fdm(self):
        self.watching = False; 
        if len(self.outputSamples['motCorrParam']) < 1:
            dialog_notify_error(message_title = "ERROR in regressing the realigned .nii", message = "No FD values in memory. lease load them from file of recompute.",  detailed = None, title="FDM error")
            return
        
        try:
            # check watch folder is set
            if self.watch_directory is None:
                raise UserWarning
            
            # check for T1 image
            if self.T1 is "" or self.T1 is None or self.T1 is "FILE NOT FOUND":
                if dialog_ask_question(message_title = "File required", message = "Please specify a valid T1 image for coregistration",detailed = None):
                    self.T1 = dialog_ask_file("T1", "*.nii")

                    self.status("Set T1 to {}".format(self.T1))
            
                    if self.T1 is "" or self.T1 is None:
                        return
                else:
                    return    
            
            # preprocessing
            self.status('Editing preprocessing batch')
            ret = self._batch.batch_edit(os.path.join(s.MATLAB_FUNCTIONS_PATH, 'preprocess_nii.m'), self.watch_directory, self._fd.all_fd(), self.T1, self.smooth_fwhm)
            if not ret:
                raise FileNotFoundError
            self.out, self.err, self.future = self._batch.run_preprocessing()
            self._future_management('Running preprocessing batch... (this may take a while)', self.regress_fdm)
            
        except UserWarning:
            dialog_notify_error(message_title = "ERROR in preprocessing the realigned .nii", message = "Please select a watch folder.",  detailed = None, title="FDM error")
        except FileNotFoundError:
            dialog_notify_error(message_title = "ERROR in preprocessing the realigned .nii", message = "No files to process found. Please make sure the fdm_proc directory is not empty",  detailed = None, title="FDM error")
        except:
            dialog_notify_error(message_title = "ERROR in preprocessing the realigned .nii", message = "Unknown error. Have you modified the regression batch ?",  detailed = None, title="FDM error")
            raise
            
    def regress_fdm(self):
        try:
            # computing regression
            self.status('Editing regression batch')
            ret = self._batch.batch_edit(os.path.join(s.MATLAB_FUNCTIONS_PATH, 'regress_fdm.m'), self.watch_directory, self._fd.all_fd(), self.T1, self.smooth_fwhm)
            if not ret:
                raise FileNotFoundError
            self.status('Running regression batch... (this may take a while)')
            self.out, self.err, self.future =  self._batch.run_regression(self.watch_directory)
            self._future_management('Running regression batch... (this may take a while)')

            
        except UserWarning:
            dialog_notify_error(message_title = "ERROR in preprocessing the realigned .nii", message = "Please select a watch folder.",  detailed = None, title="FDM error")
        except FileNotFoundError:
            dialog_notify_error(message_title = "ERROR in preprocessing the realigned .nii", message = "No files to process found. Please make sure the fdm_proc directory is not empty",  detailed = None, title="FDM error")
        except:
            dialog_notify_error(message_title = "ERROR in preprocessing the realigned .nii", message = "Unknown error. Have you modified the regression batch ?",  detailed = None, title="FDM error")
            raise

    def _future_management(self, status = '', nextFunction = None,):
        self._main_loop_call_timer.stop()
        self.status(status)
        self.setDisabled(True)
        self.setEnabled(False)
#        abdialog = BoxDialog(message_title = "Running preprocessing SPM batch...", message = "This may take a while. Aborting prematurely may cause unexpected errors.", buttons = QMessageBox.Abort, title="FDM batch status")
        self.future_timer = QtCore.QTimer()
        self.future_timer.timeout.connect(lambda : self._future_managementHelper (nextFunction)) # call main loop
        self.future_timer.setInterval(500)
        self.future_timer.start()   
        
    def _future_managementHelper(self, nextFunction = None):
        print(self.out.getvalue())
        print(self.err.getvalue())
        tf = self.future.done()
#        print(tf)
        if tf:
#            print(self.future.result())
            self.setDisabled(False)
            self.setEnabled(True)
            self.future_timer.stop() 
            self.waitingBatch = False
            self._main_loop_call_timer.start()
            if nextFunction:
                nextFunction()
        
    def create_form_group_box(self):
        dialog = ParamDialog()
        if dialog.exec_():
            print("read")

    def update_parameters_dialog(self):
        #BK3
        dialog = ParamDialog(self._fd.threshold, self._fd.radius, self.smooth_fwhm, self.T1, self.regex_input_filenames, self.input_bounded_fields)
        ret = dialog.exec_()
        if ret:
            # TODO implement more elegant exception handling
            try:
                thresholds = dialog.thresholds.text()
                thresholds = [float(i) for i in thresholds.split(',')]
                self._fd.threshold = thresholds
            except:
                print("ERROR in update_parameters_dialog : reading thresholds")
                dialog_notify_error(message_title = "ERROR in update_parameters_dialog", message = "Could not read user-defined thresholds. Please input floats separated by commas.", detailed = None, title="FDM error")
            try:
                self._fd.radius = float(dialog.radius.value())
            except:
                print("ERROR in update_parameters_dialog : reading radius")
                dialog_notify_error(message_title = "ERROR in update_parameters_dialog", message = "Could not read user-defined radius. Please input a single float", detailed = None, title="FDM error")
            try:
                smooth_fwhm = dialog.smooth_fwhm.text()
                smooth_fwhm = [float(i) for i in smooth_fwhm.split(',')]
                self._fd.smooth_fwhm = smooth_fwhm
            except:
                print("ERROR in update_parameters_dialog : reading smooth FWHM")
                dialog_notify_error(message_title = "ERROR in update_parameters_dialog", message = "Could not read user-defined smooth FWHM. Please input floats separated by commas.", detailed = None, title="FDM error")
            try:
                self.T1 = dialog.T1.text()
            except:
                print("ERROR in update_parameters_dialog : reading T1")
                dialog_notify_error(message_title = "ERROR in update_parameters_dialog", message = "Could not read user-defined radius. Please input a single float", detailed = None, title="FDM error")
            try:
                self.input_bounded_fields = dialog.getBoundedFields()
                #self.fs_observer.bounds = self.input_bounded_fields
            except:
                print("ERROR in update_parameters_dialog : reading bounded fields of regexp")
            try:
                self.regex_input_filenames = dialog.filename_filter_regex.text()
                #self.fs_observer.regex = self.regex_input_filenames
            except:
                print("ERROR in update_parameters_dialog : reading regexp")
                    
            self.drawMcPlots()
        # didn't manage to update widgets dynamically without a disproportionate amount of effort
        # simply reload the window to update spin after regexp change
        if ret == 3:
            self.update_parameters_dialog()
            
    def drawMcPlots(self):
        '''draw all plots'''
#        self.status('Drawing plots')
        self._fd.draw_mc_plots(True, self.outputSamples, self._plot_translat, "tr")
        self._fd.draw_mc_plots(True, self.outputSamples, self._plot_rotat, "rot")
        self._fd.draw_mc_plots(True, self.outputSamples, self._plot_fd, "fd")

    def _setup_filesystem_watching(self):
        path = os.path.join(self.watch_directory, self.ext)
        path = os.path.dirname(path)

        print('Searching for %s in %s' %(self.ext, path))

        # setup handler
        self.event_handler = CreateFileEventHandler(self)

        # setup observer watch folder
        self.fs_observer_watch = Observer()
        self.fs_observer_watch.schedule(
            self.event_handler, self.watch_directory, recursive=False)
        
        self.fs_observer_nii = Observer()
        self.fs_observer_nii.schedule(
            self.event_handler, s.NII_DIRECTORY_PATH, recursive=False)
        
        self.fs_observer_watch.start()
        self.fs_observer_nii.start()
    
    
    # find all files in watch folder
    def _populate_queue(self):
        self.status('Populating Queue')

        files = []
        for filename in sorted(os.listdir(self.watch_directory)):
            if self.is_acceptable_input(filename):
                files.append(os.path.join(self.watch_directory, filename))
                self.status('Adding {} to .dcm queue'.format(filename))
        if not files:
            self.status('Queue empty')
            return
        for f in sorted(files): 
            self.dcm_queue.put(f)   
            
        # check if file is an acceptable input
    def is_acceptable_input(self, tested_filename):
        m = re.search(self.regex_input_filenames, tested_filename)
        if m is None:
            return False
        else:
            for key in self.input_bounded_fields.keys():
                if int(m.group(key)) < self.input_bounded_fields[key][0] or int(m.group(key)) > self.input_bounded_fields[key][1]:
                    return False
        return True

    # check if file is a valid .nii processed by fdm
    def is_nii(self, tested_filename):
        m = re.search(s.DEFAULT_NII_FILTER, tested_filename)
        if m is None:
            return False
        else:
            return True
        
    def _main_loop(self):
#        while i > 0:
#        print("MCMC")
        if not self.nii_queue.empty():
            self._align_one()
            
        if self.watching and not self.waitingBatch:
            if not self.dcm_queue.empty():
                self._convert_one()
            if self.dcm_queue.qsize() > 1 or self.nii_queue.qsize() > 1:
                self._main_loop_call_timer.setInterval(50)
                self.status('Processing next element in queue')
            else:
                self._main_loop_call_timer.setInterval(1000)
                self.status('Watching', False)
        else:
            self._main_loop_call_timer.setInterval(300)
            self.status('Paused. PRESS Ctrl+S TO RESUME PROCESSING', False)

    def _convert_one(self):
#        print("conv")
        item = self.dcm_queue.get()
        f = os.path.split(item)[1]
        self.log_filenames.append(f)
        
        self.status("Converting {}".format(f))
        self._spm.convert(self.watch_directory, f)
#        print(self._spm.convert(f))
        self.dcm_queue.task_done()
    
    def _align_one(self):
#        print("ali")
        item = self.nii_queue.get()
        f = os.path.split(item)[1]

        self.status("Aligning {}".format(f))
        align_time = self._spm.align(s.NII_DIRECTORY_PATH, f)
        if align_time:
            align_data = self._spm.read(s.NII_DIRECTORY_PATH, self._spm.reference_nii)
            self.outputSamples['motCorrParam'].append(align_data)
            self.drawMcPlots()
        self.nii_queue.task_done()
    
    def _write_data(self):
        
        # PyQtGraph's ImageExporter needs to be patched !!!  (cast to int)
        exporter = pg.exporters.ImageExporter(self._plot_fd.getPlotItem())
        
        # set export parameters
        exporter.params.param('width').setValue(s.PLOT_EXPORT_WIDTH, blockSignal=exporter.widthChanged)
        exporter.params.param('height').setValue(s.PLOT_EXPORT_HEIGHT, blockSignal=exporter.heightChanged)

        # save to file
        print("exporting to {}".format(os.path.join(s.STAT_DIRECTORY_PATH, self._spm.reference_nii[:-4])+s.PLOT_EXPORT_FORMAT))
        exporter.export(os.path.join(s.STAT_DIRECTORY_PATH, self._spm.reference_nii[:-4]+s.PLOT_EXPORT_FORMAT))
        #exporter.exportos.path.join(s.STAT_DIRECTORY_PATH, self._spm.reference_nii[:-4]+".png")

        if len(self.log_filenames) > 0:
            try:
                df_MC = pandas.DataFrame(self._fd.data, columns=['trX', 'trY','trZ','pitch','roll','yaw'])
                df_MC['fname'] = self.log_filenames
                df_MC['FD'] = self._fd.all_fd()
                df_MC.to_csv(os.path.join(s.STAT_DIRECTORY_PATH, self._spm.reference_nii[:-4])+".csv")
                print(df_MC)
            except Exception as e: 
                print(e)                
                print("Could not save to file. Possible reason : saving to file when watch folder has been modified is known to be unsupported yet.")
        
#        'filename', 
    