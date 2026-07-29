# runtime_hook.py
import os, sys

if hasattr(sys, '_MEIPASS'):
    base = sys._MEIPASS
    pil_sub = os.path.join(base, 'PIL')
    adds = [base]
    if os.path.isdir(pil_sub):
        adds.append(pil_sub)
    os.environ['PATH'] = os.pathsep.join(adds) + os.pathsep + os.environ.get('PATH', '')

os.environ['MPLBACKEND'] = 'TkAgg'