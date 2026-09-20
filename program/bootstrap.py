"""Source launcher. Frozen EXE includes dependencies and never invokes pip."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import venv


def main():
    source = Path(__file__).resolve().parent
    requirements = source/'requirements.txt'
    # Some Windows Python installs cannot discover Tcl under a Unicode profile path.
    # Scope these paths to this launcher and its children, never system settings.
    for variable, folder in [('TCL_LIBRARY', 'tcl8.6'), ('TK_LIBRARY', 'tk8.6')]:
        library = Path(sys.base_prefix)/'tcl'/folder
        if library.is_dir(): os.environ[variable] = str(library)
    environment = Path(os.environ.get('LOCALAPPDATA', Path.home()))/'CoverGenerator'/'runtime'
    python = environment/'Scripts'/'python.exe'
    marker = environment/'requirements.sha256'
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    if not python.exists():
        print('首次启动：正在创建独立 Python 环境…', flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    probe = subprocess.run([str(python), '-c', 'import numpy, manifold3d, trimesh, networkx, tkinter'], capture_output=True)
    if probe.returncode or not marker.exists() or marker.read_text()!=digest:
        print('正在安装运行依赖，首次需要联网；失败后可重新启动重试…', flush=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(requirements)], check=True)
        subprocess.run([str(python), '-c', 'import numpy, manifold3d, trimesh, networkx, tkinter'], check=True)
        marker.write_text(digest)
    if '--install-only' not in sys.argv:
        return subprocess.call([str(python), str(source/'corner_guard.py'), '--gui'])
    print('运行环境已准备好。')
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'初始化失败：{exc}\n请检查网络或 Python 安装后重试，也可以直接使用发布的独立 EXE。', file=sys.stderr)
        sys.exit(1)
