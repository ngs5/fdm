# SPM batch edition 

import os, time, io, re, fileinput
from shutil import rmtree, copyfile

import fdm_settings as s

class Batch:
    '''Edits and runs specially tagged SPM batches'''
    def __init__(self, spm):
        self.spm = spm
        self.running = False
        pass
    
    def _retrieve_file_names(self, target_folder, ext_filter = False, prefix_filter = False):
        #self.status('Populating Queue') 
        files = []
        for filename in sorted(os.listdir(target_folder)):
            if (not ext_filter or filename[-4:] == ext_filter) and (not prefix_filter or filename[0:len(prefix_filter)] == prefix_filter):
                files.append(os.path.join(target_folder, filename))
                #self.status('Adding {} to .dcm queue'.format(filename))
    
        if not files:
            #self.status('Folder empty')
            return
    
        return sorted(files)
    
    def _flank(self, words, suffix=",1'", prefix="'", nl = '\n', interc = None): #todo : extend to words
        if words is None:
            return "'NO SUCH FILE FOUND'"
        elif isinstance(words, str):
            return prefix + words + suffix
        elif len(words) > 1:
            if interc is None:
                interc = suffix+nl+prefix
            return prefix + interc.join([str(word) for word in words])+suffix
        
    def run_custom_batch(self, watch_folder):
        out = io.StringIO()
        err = io.StringIO()
        self.start = time.time()
        print("running custom")
        self.running = True
        return (out, err, self.spm.eng.custom_edit(async=True, stdout=out,stderr=err))     
    
    def run_preprocessing(self):
        out = io.StringIO()
        err = io.StringIO()
        self.start = time.time()
        print("runpre")
        self.running = True
        return (out, err, self.spm.eng.preprocess_nii_edit('Finished preprocessing',async=True, stdout=out,stderr=err))

        
    def run_regression(self, wfolder):
        out = io.StringIO()
        err = io.StringIO()
        stat_folder = os.path.join(wfolder,s.STAT_DIRECTORY_PATH)
        rmtree(stat_folder, ignore_errors=True)
        self.start = time.time()
        print("runreg")
        return (out, err, self.spm.eng.regress_fdm_edit('Finished computing regression',async=True, stdout=out,stderr=err))
    
    def batch_edit(self, target_file, wfolder, fd, T1, smooth_fwhm, forcedName = None):
#        edited_target_file = os.path.join(os.path.join(wfolder, NII_DIRECTORY_PATH), os.path.basename(target_file)[0:-2] + '_edit.m')
        tmpdir = os.path.join(s.MATLAB_FUNCTIONS_PATH, 'tmp')
#        tmpdir = MATLAB_FUNCTIONS_PATH
        if not os.path.exists(tmpdir):
            os.mkdir(tmpdir)
        if forcedName is None:
            edited_target_file = os.path.join(tmpdir, os.path.basename(target_file)[0:-2] + '_edit.m')
        else:
            edited_target_file = os.path.join(tmpdir, forcedName)
#        edited_target_file = os.path.join(MATLAB_FUNCTIONS_PATH, os.path.basename(target_file)[0:-2] + '_edit.m')
        copyfile(target_file, edited_target_file)
        proc_folder = s.NII_DIRECTORY_PATH
        
        print("Looking for .dcm in " + wfolder, end='...')
        dcm_files = self.retrieveFileNames(wfolder, ext_filter = '.dcm')
        print("{} files found.".format("No" if dcm_files is None else len(dcm_files)))
        print("Looking for realigned .nii in " + proc_folder, end='...')
        f_nii_files = self.retrieveFileNames(proc_folder, ext_filter = '.nii', prefix_filter = 'f')
        print("{} files found.".format("No" if f_nii_files is None else len(f_nii_files)))
        print("Looking for realigned, (coregistrated,) resliced, and smoothened .nii in " + proc_folder, end='...')
        srf_nii_files = self.retrieveFileNames(proc_folder, ext_filter = '.nii', prefix_filter = 'srf')
        print("{} files found.".format("No" if srf_nii_files is None else len(srf_nii_files)))

#        T1 = '/home/ari/Documents/2017-2018_EPFL/MIP/rmiponline/motion_tool_SPM_batches_demo/templates/s002967-0005-00001-000208-01.nii'

        replace_dict = {'###DCM_FILES###': self._flank(dcm_files, "'"),
                        '###FNII_FILES###': self._flank(f_nii_files, "'"),
                        '###SRFNII_FILES###': self._flank(srf_nii_files, "'"),
                        '###CONVERT_OUTDIR###':  self._flank(proc_folder,"'"),
                        '###OUT_STATS###': self._flank(s.STAT_DIRECTORY_PATH,"'"),
                        '###T1###':  self._flank(T1),
                        '###SMOOTH_FWHM###':  self._flank(smooth_fwhm, "]", "[", interc = " "),
                        '###FD###': self._flank(fd, "","")}
        
        self.spm.eng.addpath(tmpdir)
        return self._file_edit(edited_target_file, replace_dict)
                        
    def _file_edit(self, target_file, replace_dict, append_dict = {}, preserveIndent = True):
        ret = True
        
        file = ""
        r = re.compile("([ \t]*)(.+)")
        
        with fileinput.FileInput(target_file, inplace=True, backup='.bak') as file:
        #with fileinput.FileInput(OPENNFT_PATH) as file:
            for line in file:
                if preserveIndent:
                    indent_line = r.match(line)
                else:
                    indent_line = ""
                if indent_line is not None:
                    nli = "\n" + indent_line.group(1)
                    
                    for k in replace_dict.keys():
                        if k in line:                            
                            subst = replace_dict[k].replace("\n", nli)
                            line = line.replace(k, subst) 
                            
                            if "NO SUCH FILE FOUND" in replace_dict[k]:
                                ret = False
#                    elif indent_line.group(2) in append_dict:
#                        line = line[0:-1] + nli + append_dict[indent_line.group(2)].replace("\n", nli) + "\n"
                print(line, end='')
        print(ret)
        return ret