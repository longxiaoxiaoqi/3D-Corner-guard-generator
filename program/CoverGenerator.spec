from PyInstaller.utils.hooks import collect_all
packages = ['numpy', 'manifold3d', 'trimesh', 'networkx']
datas, binaries, hiddenimports = [], [], []
for package in packages:
    d, b, h = collect_all(package)
    datas += d; binaries += b; hiddenimports += h
a = Analysis(['corner_guard.py'], pathex=[SPECPATH], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, excludes=['pytest', 'IPython'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='CoverGenerator',
          debug=False, bootloader_ignore_signals=False, strip=False,
          upx=False, console=False)
