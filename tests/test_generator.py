import importlib.util
import sys
from pathlib import Path
import numpy as np
import manifold3d as m
import trimesh

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'program/corner_guard.py'
spec=importlib.util.spec_from_file_location('corner_guard',source)
g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)

cases=[g.Parameters(),g.Parameters(overlap=2,slot=3.8,top=8,bottom=2,arm=22),
       g.Parameters(overlap=.3,slot=.5,top=.3,bottom=.7,arm=2,wall=.4),
       g.Parameters(overlap=3,slot=6,top=10,bottom=8,arm=40,wall=4)]
for index,p in enumerate(cases):
    directory=ROOT/'test-output'/f'case{index}'
    report=g.generate(p,directory)
    mesh=trimesh.load_mesh(directory/'corner_single.stl')
    solid=m.Manifold(m.Mesh(np.asarray(mesh.vertices,dtype=np.float32),np.asarray(mesh.faces,dtype=np.uint32)))
    full=(p.arm+p.wall)**2-(p.arm-p.overlap)**2-1.5*p.chamfer**2
    walls=(p.arm+p.wall)**2-p.arm**2-1.5*p.chamfer**2
    # Independent cross-section checks: full contact footprint above/below,
    # only the two outside walls in the middle of the PCB slot.
    for z,expected in [(p.bottom/2,full),(p.bottom+p.slot/2,walls),
                       (p.bottom+p.slot+p.top/2,full)]:
        actual=solid.slice(z).area()
        assert abs(actual-expected)<.002,(index,z,actual,expected)
    print('PASS geometry',index,report['outer_dimensions_mm'])
del solid

for bad in [dict(overlap=0),dict(slot=-1),dict(top=float('nan')),
            dict(bottom=float('inf')),dict(arm=2.2),dict(wall=.01)]:
    try:g.Parameters(**bad).validate()
    except ValueError:pass
    else:raise AssertionError(('Invalid input accepted',bad))
print('PASS six invalid inputs rejected')

for index,p in enumerate([g.CuboidParameters(),g.CuboidParameters(x=12,y=25,z=38,wall=2),g.CuboidParameters(x=.5,y=.8,z=1.2,wall=.2)]):
    directory=ROOT/'test-output'/f'cuboid{index}'
    report=g.generate(p,directory)
    mesh=trimesh.load_mesh(directory/'corner_single.stl')
    expected=(p.x+p.wall)*(p.y+p.wall)*(p.z+p.wall)-p.x*p.y*p.z
    assert abs(mesh.volume-expected)<.01
    solid=m.Manifold(m.Mesh(np.asarray(mesh.vertices,dtype=np.float32),np.asarray(mesh.faces,dtype=np.uint32)))
    assert abs(solid.slice(p.wall/2).area()-(p.x+p.wall)*(p.y+p.wall))<.001
    assert abs(solid.slice(p.wall+p.z/2).area()-((p.x+p.wall)*(p.y+p.wall)-p.x*p.y))<.001
    # Empty cavity and all three positive directions remain open.
    for offset,extents in [((p.wall+.01,p.wall+.01,p.wall+.01),(p.x+1,p.y-.02,p.z-.02)),
                           ((p.wall+.01,p.wall+.01,p.wall+.01),(p.x-.02,p.y+1,p.z-.02)),
                           ((p.wall+.01,p.wall+.01,p.wall+.01),(p.x-.02,p.y-.02,p.z+1))]:
        probe=m.Manifold.cube(extents).translate(offset)
        assert (solid^probe).volume()<.0001
    reflected=trimesh.load_mesh(directory/'corner_mirrored.stl')
    assert reflected.is_watertight and abs(reflected.volume-mesh.volume)<.01
    pack=trimesh.load_mesh(directory/'corner_eight.stl')
    assert len(pack.split())==8
    assert abs(pack.volume-8*expected)<.05
    print('PASS three-face geometry and eight-pack',index)
del solid,probe

import subprocess
bad=subprocess.run([sys.executable,str(source),'--type','cuboid','--slot','4','--out',str(ROOT/'test-output/invalid')],capture_output=True)
assert bad.returncode!=0
assert not (ROOT/'test-output/invalid').exists()
print('PASS incompatible CLI parameters rejected')

for index,p in enumerate([g.UCoverParameters(),g.UCoverParameters(width=35,length=80,height=12,base=2,wall=4),g.UCoverParameters(width=.6,length=2,height=.8,base=.2,wall=.3)]):
    directory=ROOT/'test-output'/f'ucover{index}'
    report=g.generate(p,directory)
    mesh=trimesh.load_mesh(directory/'cover_single.stl')
    expected=p.length*(p.width+2*p.wall)*p.base+2*p.length*p.wall*p.height
    assert abs(mesh.volume-expected)<.01
    assert np.allclose(mesh.extents,p.extents,atol=.001)
    solid=m.Manifold(m.Mesh(np.asarray(mesh.vertices,dtype=np.float32),np.asarray(mesh.faces,dtype=np.uint32)))
    assert abs(solid.slice(p.base/2).area()-p.length*(p.width+2*p.wall))<.001
    assert abs(solid.slice(p.base+p.height/2).area()-2*p.length*p.wall)<.001
    # Probe spans BOTH end openings and the full space between opposing walls.
    probe=m.Manifold.cube((p.length+2,p.width-.02,p.height+1)).translate((-1,p.wall+.01,p.base+.01))
    assert (solid^probe).volume()<.0001
    assert report['type']=='ucover' and report['components']==[1]
    assert not (directory/'corner_four.stl').exists()
    print('PASS U cover dimensions, thickness and both openings',index)
del solid,probe
for key in ['width','length','height','base','wall']:
    for value in [0,-1,float('nan'),float('inf')]:
        try:g.UCoverParameters(**{key:value}).validate()
        except ValueError:pass
        else:raise AssertionError(('Invalid U cover input',key,value))
bad=subprocess.run([sys.executable,str(source),'--type','ucover','--slot','4','--out',str(ROOT/'test-output/invalid-ucover')],capture_output=True)
assert bad.returncode!=0
print('PASS invalid U cover inputs and irrelevant parameters rejected')

for index,p in enumerate([g.ClosedCoverParameters(),g.ClosedCoverParameters(length=70,width=45,height=20,base=2,wall=4),g.ClosedCoverParameters(length=2,width=.6,height=.8,base=.2,wall=.3)]):
    directory=ROOT/'test-output'/f'closedcover{index}'
    report=g.generate(p,directory)
    mesh=trimesh.load_mesh(directory/'cover_single.stl')
    expected=np.prod(p.extents)-p.length*p.width*p.height
    assert abs(mesh.volume-expected)<.01
    assert np.allclose(mesh.extents,p.extents,atol=.001)
    solid=m.Manifold(m.Mesh(np.asarray(mesh.vertices,dtype=np.float32),np.asarray(mesh.faces,dtype=np.uint32)))
    full=p.extents[0]*p.extents[1]
    assert abs(solid.slice(p.base/2).area()-full)<.001
    assert abs(solid.slice(p.base+p.height/2).area()-(full-p.length*p.width))<.001
    # Only the insertion face is open; verify cavity and all four wall regions.
    probe=m.Manifold.cube((p.length-.02,p.width-.02,p.height+1)).translate((p.wall+.01,p.wall+.01,p.base+.01))
    assert (solid^probe).volume()<.0001
    for offset,extents in [((0,0,p.base),(p.wall,p.extents[1],p.height)),
                           ((p.wall+p.length,0,p.base),(p.wall,p.extents[1],p.height)),
                           ((p.wall,0,p.base),(p.length,p.wall,p.height)),
                           ((p.wall,p.wall+p.width,p.base),(p.length,p.wall,p.height))]:
        probe=m.Manifold.cube(extents).translate(offset)
        assert abs((solid^probe).volume()-np.prod(extents))<.001
    assert report['type']=='closedcover'
    print('PASS four-wall cover, inner dimensions and open insertion face',index)
del solid,probe

# Exercise the actual GUI generate button without displaying a desktop window.
import tkinter as tk
from tkinter import ttk, messagebox
def smoke(root):
    root.withdraw()
    def widgets(parent):
        for child in parent.winfo_children():
            yield child
            yield from widgets(child)
    items=list(widgets(root))
    entries=[x for x in items if isinstance(x,ttk.Entry)]
    assert len(entries)==21
    entries[-1].delete(0,'end');entries[-1].insert(0,str(ROOT/'test-output/gui'))
    button=next(x for x in items if isinstance(x,ttk.Button) and x.cget('text')=='生成模型')
    preview=next(x for x in items if isinstance(x,ttk.Button) and x.cget('text')=='打开 3D 预览')
    messagebox.showerror=lambda title,message:(_ for _ in ()).throw(AssertionError(message))
    button.invoke()
    assert str(preview.cget('state'))=='normal'
    assert list((ROOT/'test-output/gui').glob('*/corner_single.stl'))
    notebook=next(x for x in items if isinstance(x,ttk.Notebook))
    notebook.select(1)
    # Invalid hidden PCB fields must not prevent cuboid generation.
    entries[0].delete(0,'end');entries[0].insert(0,'invalid')
    button.invoke()
    assert list((ROOT/'test-output/gui').glob('*/corner_eight.stl'))
    notebook.select(2)
    button.invoke()
    assert list((ROOT/'test-output/gui').glob('*/cover_single.stl'))
    notebook.select(3)
    button.invoke()
    import json
    reports=[json.loads(f.read_text(encoding='utf-8')) for f in (ROOT/'test-output/gui').glob('*/parameters.json')]
    assert any(r.get('type')=='closedcover' for r in reports)
    root.destroy()
tk.Tk.mainloop=smoke
g.gui()
print('PASS GUI form and generate button')
