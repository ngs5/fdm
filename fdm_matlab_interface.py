# Connect to matlab engine and run SPM

import sys, os
import fdm_settings as s
import matlab.engine as me

class SPM():
    def __init__(self):
        # connect to running matlab engine
        if not s.MATLAB_SHARED_ENGINE_NAME in me.find_matlab():
            print("Launch MATLAB and execute \"matlab.engine.shareEngine('{}')\" ".format(s.MATLAB_SHARED_ENGINE_NAME))
            sys.exit("{} MATLAB engine not found.".format(s.MATLAB_SHARED_ENGINE_NAME))
        else:
            print("{} MATLAB engine found".format(s.MATLAB_SHARED_ENGINE_NAME))
        
        self._initialize()
        
        # reference .nii for alignement
        self.reference_nii = None
   
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.eng.quit()
        print("Disconnected from MATLAB")
        
    def _initialize(self, start=True):
        '''Connect to matlab session and add FDM scripts to path'''
        self.eng = me.connect_matlab(s.MATLAB_SHARED_ENGINE_NAME)
        
        #print("Launching MATLAB...")
        #self.eng = matlab.engine.start_matlab("-regserver -desktop")

        self.eng.cd(s.MATLAB_FUNCTIONS_PATH)
        self.eng.addpath(s.MATLAB_FUNCTIONS_PATH)
#        self.eng.addMatlabDirs(nargout=0)
        self.eng.clear('all', nargout=0)
        self.eng.spm('defaults','fmri')

    def convert(self, wfolder, file):
        '''Convert .dcm into .nii (required for alignement)'''
        cvt_time = self.eng.fdm_convert_dcm_to_nii(wfolder,file, s.NII_DIRECTORY_PATH)
        return("converted {} in {}s".format(file, cvt_time))
        
    def align(self, wfolder, second_file):
        '''Call SPM to align 2 .nii frames'''
        if self.reference_nii is None:
            self.reference_nii = second_file
            print( "stored reference file: {}".format(self.reference_nii))
            return False
#        print("{}, {}".format(self.reference_nii,second_file))
        aln_time = self.eng.fdm_align2_nii(wfolder,self.reference_nii,second_file)
        print("aligned {} with {} in {}s".format(self.reference_nii,second_file, aln_time))
        return True
    
    def read(self, wfolder, file):
        '''Read MC transform parameters from SPM summary .txt file'''
        # read second line of file
        filename = "rp_"+file[0:-4]+".txt"
        path = os.path.join(wfolder, filename)
        with open(path, 'r') as f:
            read_data = f.readline()
            read_data = f.readline()
            return read_data.split()