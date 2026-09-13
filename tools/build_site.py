#!/usr/bin/env python3
"""Full rebuild wrapper: parse timetables, calibrate GeoTD, add speed model, split AEL/TCL, and generate track-following geometry."""
import os, sys, subprocess, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
DEFAULT_ZIP='/mnt/data/Timetables, Traffic Notices, Track Diagrams-20260908T153610Z-1-001.zip'
DEFAULT_OUT=os.path.abspath(os.path.join(HERE,'..'))
ZIP=os.path.abspath(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_ZIP
OUT=os.path.abspath(sys.argv[2]) if len(sys.argv)>2 else DEFAULT_OUT
subprocess.run([sys.executable,os.path.join(HERE,'build_base.py'),ZIP,OUT],check=True)
subprocess.run([sys.executable,os.path.join(HERE,'upgrade_calibration_speed.py'),ZIP,OUT],check=True)
shutil.copy2(os.path.join(HERE,'app_enhanced.js'),os.path.join(OUT,'app.js'))
shutil.copy2(os.path.join(HERE,'styles_enhanced.css'),os.path.join(OUT,'styles.css'))
subprocess.run([sys.executable,os.path.join(HERE,'upgrade_track_following_services.py'),OUT,ZIP],check=True)
print('Track-following AEL/TCL-separated calibrated site written to',OUT)
