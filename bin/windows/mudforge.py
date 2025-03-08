import os
import sys

# for pip install -e
sys.path.insert(0, os.path.abspath(os.getcwd()))
# main library path
sys.path.insert(0, os.path.join(sys.prefix, "Lib", "site-packages"))

from mudforge.launcher import main

main()
