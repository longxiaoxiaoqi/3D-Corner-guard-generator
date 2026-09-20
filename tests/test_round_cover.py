"""Independent analytic cross-sections of the chamfer and both fillets."""
from dataclasses import replace, asdict
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
import manifold3d as m
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'program'))
import corner_guard as g


def area_at(p,z):
    r=p.diameter/2
    outer=r+p.wall
    if p.outer_radius and z<p.outer_radius:
        outer=outer-p.outer_radius+np.sqrt(p.outer_radius**2-(z-p.outer_radius)**2)
    inner=0.
    if z>p.base:
        inner=r
        if p.inner_radius and z<p.base+p.inner_radius:
            inner=r-p.inner_radius+np.sqrt(p.inner_radius**2-(z-p.base-p.inner_radius)**2)
        elif p.opening_chamfer and z>p.base+p.height-p.opening_chamfer:
            inner=r+z-(p.base+p.height-p.opening_chamfer)
    return np.pi*(outer**2-inner**2)


cases=[g.RoundCoverParameters(opening_chamfer=c,outer_radius=ro,inner_radius=ri)
       for c,ro,ri in itertools.product([0.,1.],[0.,2.],[0.,2.])]
cases += [g.RoundCoverParameters(diameter=1,height=.4,base=.2,wall=.2,opening_chamfer=.05,outer_radius=.2,inner_radius=.1),
          g.RoundCoverParameters(opening_chamfer=2.99,outer_radius=3,inner_radius=12),
          g.RoundCoverParameters(diameter=10,height=8,base=1,wall=2,inner_radius=4.99,outer_radius=1,opening_chamfer=1.9),
          g.RoundCoverParameters(diameter=1000,height=1000,base=1000,wall=1000,opening_chamfer=100,outer_radius=1000,inner_radius=400)]
with tempfile.TemporaryDirectory(prefix='round-cover-') as folder:
    folder=Path(folder)
    volumes={}
    for index,p in enumerate(cases):
        path=folder/str(index)
        report=g.generate(p,path)
        mesh=trimesh.load_mesh(path/'cover_single.stl')
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
        assert np.allclose(mesh.extents,p.extents,atol=.001,rtol=0)
        solid=m.Manifold(m.Mesh(np.asarray(mesh.vertices,dtype=np.float32),np.asarray(mesh.faces,dtype=np.uint32)))
        assert solid.status()==m.Error.NoError
        points=[p.base*.5,p.base+p.inner_radius+(p.height-p.inner_radius-p.opening_chamfer)/2,
                p.base+p.height-min(.01,p.height*.01)]
        if p.outer_radius: points += [p.outer_radius*x for x in [.1,.35,.75]]
        if p.inner_radius: points += [p.base+p.inner_radius*x for x in [.1,.35,.75]]
        if p.opening_chamfer: points += [p.base+p.height-p.opening_chamfer*x for x in [.1,.5,.9]]
        for z in points:
            expected=area_at(p,z)
            actual=solid.slice(z).area()
            # Convert .025 mm chord deviation into a perimeter-scaled area bound.
            tolerance=max(.002,2*np.pi*(p.diameter+p.wall)*.055)
            assert abs(actual-expected)<tolerance,(index,z,actual,expected,tolerance)
        # The cavity center is empty right through the opening and beyond it.
        probe=m.Manifold.cylinder(p.height+1,min(.01,p.diameter/2-p.inner_radius)/2,circular_segments=16).translate((0,0,p.base+.001))
        assert (solid^probe).volume()<1e-7
        assert report['opening_diameter_mm']==p.diameter+2*p.opening_chamfer
        assert report['straight_wall_height_mm']>0
        assert '圆形封闭盖板' in (path/'preview.html').read_text(encoding='utf-8')
        assert 'rotate_extrude' in (path/'cover_parametric.scad').read_text(encoding='utf-8')
        if index<8: volumes[(p.opening_chamfer,p.outer_radius,p.inner_radius)]=mesh.volume
        print('PASS circular cover cross-sections',index)
    assert volumes[(1,0,0)]<volumes[(0,0,0)], 'Chamfer must remove material'
    assert volumes[(0,2,0)]<volumes[(0,0,0)], 'Outer fillet must remove material'
    assert volumes[(0,0,2)]>volumes[(0,0,0)], 'Inner fillet must add material'
    invalid=[dict(opening_chamfer=3),dict(outer_radius=3.01),dict(inner_radius=50),
             dict(inner_radius=14,opening_chamfer=1),dict(height=.2,opening_chamfer=.2)]
    for name in asdict(g.RoundCoverParameters()):
        invalid += [{name:value} for value in [-1,float('nan'),float('inf'),1001]]
    for values in invalid:
        try: g.RoundCoverParameters(**values).validate()
        except ValueError: pass
        else: raise AssertionError(('Accepted invalid parameters',values))
    for flags in [['--slot','4'],['--opening_chamfer','3']]:
        result=subprocess.run([sys.executable,str(ROOT/'program/corner_guard.py'),'--type','roundcover',*flags,'--out',str(folder/'invalid')],capture_output=True)
        assert result.returncode!=0 and not (folder/'invalid').exists()
    result=subprocess.run([sys.executable,str(ROOT/'program/corner_guard.py'),'--type','roundcover','--opening_chamfer','1','--outer_radius','2','--inner_radius','2','--out',str(folder/'cli')],capture_output=True)
    assert result.returncode==0,result.stderr
    assert json.loads((folder/'cli/parameters.json').read_text(encoding='utf-8'))['type']=='roundcover'
print('PASS circular cover feature effects, validation and CLI')
