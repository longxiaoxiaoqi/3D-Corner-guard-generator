"""Run the bundled EXE with no Python/Tcl environment variables or PATH."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

exe=Path(sys.argv[1]).resolve()
environment={key:value for key,value in os.environ.items()
             if not key.upper().startswith('PYTHON') and key.upper() not in ('TCL_LIBRARY','TK_LIBRARY','VIRTUAL_ENV')}
environment['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
with tempfile.TemporaryDirectory(prefix='cover-frozen-') as folder:
    for kind in ['pcb','cuboid','ucover','closedcover','circle','rectangle','square']:
        destination=Path(folder)/('中文输出_'+kind)
        result=subprocess.run([str(exe),'--type',kind,'--out',str(destination)],env=environment,timeout=90)
        assert result.returncode==0,(kind,result.returncode)
        report=json.loads((destination/'parameters.json').read_text(encoding='utf-8'))
        assert report['type']==kind
        assert list(destination.glob('*.stl')) and (destination/'preview.html').exists()
        print('PASS standalone EXE',kind)
