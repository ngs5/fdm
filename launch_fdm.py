# launch_FDM

import sys
from PyQt5.QtWidgets import QApplication

from fdm_install_helper import no_confirm_installer
from fdm_matlab_interface import SPM
from fdm_watcher import FDMWatcher

# TODO :
# ->->-> export plots to csv -> & plot from csv. Evt : export SVG directement..
# ->-> Reprendre analyse
# -> Ajouter des valeurs par défaut à la version OpenNFT du plugin (pour éviter un crash)
# Mieux tester l'input de l'utilisateur (batchs et GUI)
# Ajouter d'autre formats que .dcm
# More Batch formats
# Use OpenNFT functs
#
#
#


if __name__ == "__main__":
#    try:
#        app = QApplication(sys.argv)
#        no_confirm_installer()
#        with SPM() as spm:
#            with FDMWatcher(spm) as watch:
#                #watch._main_loop_call_timer.start(1000)
#                app.exec_()
#    except KeyboardInterrupt:
#        print('Interrupted')
#        sys.exit(0)
#    except:
#        sys.exit(sys.exc_info())
    
    # noexcept
    app = QApplication(sys.argv)
    no_confirm_installer()
    with SPM() as spm:
        with FDMWatcher(spm) as watch:
            #watch._main_loop_call_timer.start(1000)
            app.exec_()
