import fdm_settings as s
from fdm_base import FD

from PyQt5.QtWidgets import QWidget, QGridLayout

class fd_OpenNFT:
    '''Module recovering MC data from OpenNFT and using FD to compute and display framewise displacement.'''
    def __init__(self, openNFT = None):
        self.openNFT = openNFT
        self.fdmod = FD(self)
        self.md = "l"
        self.win = None
    
        # create Plot
    def createMcPlot(self):
        '''Create new MC plot'''
        return self.fdmod.createMcPlotSA(self.openNFT, self.openNFT.layoutPlot1, self.openNFT)

        # initialise & draw plots 
    def drawMcPlots(self, init):
        '''Initialise and draw all MC plots accessible to fd_OpenNFT'''
        if init :
            # read params
            try:
                self.fdmod.radius = float(self.openNFT.settings.value('fdRadius', '50'))
                self.fdmod.threshold = self.openNFT.settings.value('fdThreshold', '0.2')
            except:
                self.fdmod.radius = s.DEFAULT_FD_RADIUS
                self.fdmod.threshold = s.DEFAULT_FD_THRESHOLDS
            self.fdmod.xmax = max(self.openNFT.musterInfo['tmpCond1'][-1][1],
            self.openNFT.musterInfo['tmpCond2'][-1][1])
            
        if self.win != None:
            self.win.drawAllPlots(self.openNFT.outputSamples)
                
        return self.fdmod.drawMcPlotsSA(init, self.openNFT.outputSamples,  self.openNFT.mcPlot.getPlotItem(), self.md)
    
    def createwindow(self):
        '''Create/show external MC window AddonONFTWindow'''
        if self.win is None:
             self.win = AddonONFTWindow(None, self)
        else:
            self.win.show()

class AddonONFTWindow(QWidget):
    '''Creates a new window displaying all available MC plot. Windows allows selection of plot to embedd in OpenNFT'''
    def __init__(self, win_parent=None, module=False):
        QWidget.__init__(self, win_parent)
                
        if not module:
            self.module = fd_OpenNFT()
        else:
            self.module = module
        
        self.wgets = []
        self.plts = ['tr','rot','l','fd']
        self.init = True
        
        self.initUI()
        
    def initUI(self):               
        '''Generate expanded view UI'''
        self.grid = QGridLayout()
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.grid)
        
        for i, n in enumerate(self.plts):
            p = self.module.fdmod.createMcPlotSA(self, None, None, "MC_"+n)
            p.installEventFilter(self)
            legend = p.addLegend((10, 10))
            legend.anchor((1,0), (1,0))
            self.grid.addWidget(p, i,0)
            self.wgets.append(p)
            
        self.setGeometry(300, 300, 550, 700)
        self.setWindowTitle('MC addon main window')
        self.show()
    
    def drawAllPlots(self, outputSamples):
        '''Draw all the MC plots contained in the window'''
        # check online
        if self.isVisible():
            for i, n in enumerate(self.plts):
                self.module.fdmod.drawMcPlotsSA(self.init, outputSamples, self.wgets[i], n)
            self.init = False
        
    def eventFilter(self, obj, event):
        '''Replace MC plot in OpenNFT when double clicking on a plot of the expanded view'''        
        if event.type() == 2 or event.type() == 4:
            # Replace plot views
            plotWidget = obj.getViewWidget()
            
            p = plotWidget.getPlotItem() 
            for i, n in enumerate(self.plts):
                if p.vb.name == "MC_" + n:
                    self.module.md = n
                    self.module.drawMcPlots(True)
            
            # hide when plot is double clicked
            if event.type() == 4:
                self.hide()
        return False

    def closeEvent(self, event):
        self.module.win = None
        event.accept()