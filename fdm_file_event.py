# Handle creation of new files

import os
from watchdog.events import FileSystemEventHandler
#from fdm_watcher import FDMWatcher

class CreateFileEventHandler(FileSystemEventHandler):
    '''Appends filenames of newly created .dcm and .nii to their respective queues'''
    def __init__(self, fdm_watcher):
        self.fdm_watcher = fdm_watcher
        
        # keep track of last processed files
        self._last_dcm = "" 
        self._last_nii = ""

        # TODO : implement logging
#        if len(log)>0:
#            self._last_dcm = log[-1]
    
    # called when new file is created    
    def on_created(self, event):
        
        valid_input = self.fdm_watcher.is_acceptable_input(os.path.split(event.src_path)[1])
        # double-check that it is a dcm
        if not event.is_directory and valid_input and event.src_path > self._last_dcm:
            self.fdm_watcher.dcm_queue.put(event.src_path)
            self._last_dcm = event.src_path
            return 

        # and niis to nii queue only if they were created by fdm
#        print(os.path.split(event.src_path)[1][0])
#        print("new {}, last {}, n>l {}".format(event.src_path, self._last_nii, event.src_path > self._last_nii))
        #if not event.is_directory and event.src_path.endswith('.nii') and event.src_path > self._last_nii and os.path.split(event.src_path)[1][0] == 'f':
        
        valid_nii = self.fdm_watcher.is_nii(os.path.split(event.src_path)[1])
        if not event.is_directory and valid_nii and event.src_path > self._last_nii:
            self.fdm_watcher.nii_queue.put(event.src_path)
            self._last_nii = event.src_path
            return 
        elif event.src_path < self._last_nii:
            print("DISCARDED")
            pass