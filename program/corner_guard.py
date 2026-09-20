"""PCB corner guard generator: a local form and command-line interface."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import sys
import webbrowser


@dataclass(frozen=True)
class Parameters:
    overlap: float = 2.2
    slot: float = 4.1
    top: float = 5.0
    bottom: float = 5.0
    arm: float = 15.0
    wall: float = 3.0

    @property
    def height(self):
        return self.bottom + self.slot + self.top

    @property
    def chamfer(self):
        return min(0.8, self.wall / 3, self.arm / 10)

    @property
    def entry(self):
        return min(0.4, self.overlap / 4, self.bottom / 4, self.top / 4)

    def validate(self):
        labels = dict(overlap='内嵌深度', slot='夹槽高度', top='上垫高',
                      bottom='下垫高', arm='护角边长', wall='外侧壁厚')
        for key, value in asdict(self).items():
            if not math.isfinite(value) or not 0.2 <= value <= 1000:
                raise ValueError(f'{labels[key]}必须是 0.2～1000 mm 之间的有限数值。')
        if self.arm <= self.overlap:
            raise ValueError('护角边长必须大于内嵌深度。')


@dataclass(frozen=True)
class CuboidParameters:
    x: float = 20.0
    y: float = 20.0
    z: float = 20.0
    wall: float = 3.0

    def validate(self):
        for key,value in asdict(self).items():
            if not math.isfinite(value) or not 0.2 <= value <= 1000:
                raise ValueError(f'{key} 必须是 0.2～1000 mm 之间的有限数值。')


@dataclass(frozen=True)
class UCoverParameters:
    width: float = 100.0
    length: float = 120.0
    height: float = 15.0
    base: float = 3.0
    wall: float = 3.0

    @property
    def extents(self):
        return [self.length,self.width+2*self.wall,self.height+self.base]

    def validate(self):
        labels=dict(width='内宽',length='长度',height='侧壁内高',base='平板厚度',wall='侧壁厚度')
        for key,value in asdict(self).items():
            if not math.isfinite(value) or not 0.2 <= value <= 1000:
                raise ValueError(f'{labels[key]}必须是 0.2～1000 mm 之间的有限数值。')


@dataclass(frozen=True)
class ClosedCoverParameters(UCoverParameters):
    @property
    def extents(self):
        return [self.length+2*self.wall,self.width+2*self.wall,self.height+self.base]


@dataclass(frozen=True)
class RectPlateParameters:
    length: float = 120.
    width: float = 100.
    thickness: float = 3.
    radius: float = 0.
    bevel: float = 0.
    def validate(self):validate_plate(self)


@dataclass(frozen=True)
class SquarePlateParameters:
    side: float = 100.
    thickness: float = 3.
    radius: float = 0.
    bevel: float = 0.
    def validate(self):validate_plate(self)


@dataclass(frozen=True)
class CirclePlateParameters:
    diameter: float = 100.
    thickness: float = 3.
    bevel: float = 0.
    def validate(self):validate_plate(self)


PLATES=(RectPlateParameters,SquarePlateParameters,CirclePlateParameters)


def plate_size(p):
    if isinstance(p,CirclePlateParameters):return [p.diameter,p.diameter,p.thickness]
    if isinstance(p,SquarePlateParameters):return [p.side,p.side,p.thickness]
    return [p.length,p.width,p.thickness]


def validate_plate(p):
    for key,value in asdict(p).items():
        minimum=0 if key in ('radius','bevel') else .2
        if not math.isfinite(value) or not minimum<=value<=1000:
            raise ValueError(f'{key} 必须为 {minimum}～1000 mm 的有限数值。')
    a,b,t=plate_size(p)
    if getattr(p,'radius',0)>min(a,b)/2:
        raise ValueError('圆角半径 R 不能超过短边的一半。')
    if p.bevel>=min(a,b,t)/2:
        raise ValueError('倒角 C 必须小于厚度及短边（或直径）的一半；0 表示无倒角。')


def build_plate(p):
    p.validate()
    import numpy as np
    import trimesh
    a,b,t=plate_size(p);c=p.bevel
    rings=[(0,c),(c,0),(t-c,0),(t,c)] if c else [(0,0),(t,0)]
    r=getattr(p,'radius',0)
    if 0<r<c:
        rings=[(0,c),(c-r,r),(c,0),(t-c,0),(t-c+r,r),(t,c)]
    verts=[]
    for z,inset in rings:
        if isinstance(p,CirclePlateParameters):
            angles=np.linspace(0,2*np.pi,256,endpoint=False)
            points=[(a/2+(a/2-inset)*np.cos(v),b/2+(b/2-inset)*np.sin(v),z) for v in angles]
        else:
            r=max(0,p.radius-inset)
            centers=[(a-inset-r,b-inset-r),(inset+r,b-inset-r),(inset+r,inset+r),(a-inset-r,inset+r)]
            points=[]
            for i,(x,y) in enumerate(centers):
                for angle in np.linspace(i*np.pi/2,(i+1)*np.pi/2,65):
                    points.append((x+r*np.cos(angle),y+r*np.sin(angle),z))
        verts.extend(points)
    n=len(points);faces=[]
    for j in range(len(rings)-1):
        for i in range(n):
            k=(i+1)%n;lo=j*n;hi=(j+1)*n
            faces.extend([(lo+i,lo+k,hi+k),(lo+i,hi+k,hi+i)])
    bottom=len(verts);verts.append((a/2,b/2,0))
    top=len(verts);verts.append((a/2,b/2,t));start=(len(rings)-1)*n
    for i in range(n):
        k=(i+1)%n;faces.extend([(bottom,k,i),(top,start+i,start+k)])
    mesh=trimesh.Trimesh(vertices=verts,faces=faces,process=True)
    mesh.merge_vertices(digits_vertex=6);mesh.update_faces(mesh.nondegenerate_faces());mesh.remove_unreferenced_vertices()
    check(mesh,1)
    if not np.allclose(mesh.extents,[a,b,t],atol=.001,rtol=0):raise RuntimeError('平板尺寸检查失败。')
    return mesh


def plate_scad(p):
    # Export the validated triangulation as an editable parametric ring loft.
    a,b,t=plate_size(p)
    dimensions=(f'diameter={a:g}; length=diameter; width=diameter;' if isinstance(p,CirclePlateParameters) else
                (f'side={a:g}; length=side; width=side;' if isinstance(p,SquarePlateParameters) else f'length={a:g}; width={b:g};'))
    return f'''// mm. R: plan-view corner radius. C: 45-degree top/bottom edge bevel.
{dimensions} thickness={t:g};
radius={getattr(p,'radius',0):g}; bevel={p.bevel:g};
round_plate={'true' if isinstance(p,CirclePlateParameters) else 'false'};
assert(min(length,width,thickness)>0);
assert(radius>=0 && radius<=min(length,width)/2);
assert(bevel>=0 && bevel<min(length,width,thickness)/2);
function ring(z,d)=round_plate ?
    [for(i=[0:255]) [length/2+(length/2-d)*cos(i*360/256),width/2+(width/2-d)*sin(i*360/256),z]] :
    let(r=max(0,radius-d), centers=[[length-d-r,width-d-r],[d+r,width-d-r],[d+r,d+r],[length-d-r,d+r]])
    [for(j=[0:3]) for(i=[0:64]) [centers[j][0]+r*cos(j*90+i*90/64),centers[j][1]+r*sin(j*90+i*90/64),z]];
rings=bevel==0?[[0,0],[thickness,0]]:
    (!round_plate && radius>0 && radius<bevel)?
    [[0,bevel],[bevel-radius,radius],[bevel,0],[thickness-bevel,0],[thickness-bevel+radius,radius],[thickness,bevel]]:
    [[0,bevel],[bevel,0],[thickness-bevel,0],[thickness,bevel]];
n=round_plate?256:260; nr=len(rings);
v=concat([for(pair=rings) each ring(pair[0],pair[1])],[[length/2,width/2,0],[length/2,width/2,thickness]]);
faces=concat(
 [for(j=[0:nr-2]) for(i=[0:n-1]) each [[j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n],[j*n+i,(j+1)*n+(i+1)%n,(j+1)*n+i]]],
 [for(i=[0:n-1]) each [[nr*n,(i+1)%n,i],[nr*n+1,(nr-1)*n+i,(nr-1)*n+(i+1)%n]]]);
// Weld collapsed corner vertices when R=0 or C>=R, then drop zero-area faces.
vr=[for(p=v) [for(q=p) round(q*1000000)/1000000]];
unique=[for(i=[0:len(vr)-1]) if(search([vr[i]],vr)[0]==i) vr[i]];
mapped=[for(f=faces) [for(i=f) search([vr[i]],unique)[0]]];
// OpenSCAD uses clockwise face winding viewed from outside.
polyhedron(points=unique,faces=[for(f=mapped)
    if(norm(cross(unique[f[1]]-unique[f[0]],unique[f[2]]-unique[f[0]]))>0.000000001)
    [f[2],f[1],f[0]]],convexity=10);
'''


def generate_plate(p,destination):
    import trimesh
    import numpy as np
    mesh=build_plate(p);destination=Path(destination).expanduser().resolve();destination.mkdir(parents=True,exist_ok=True)
    mesh.export(destination/'plate_single.stl');reread=trimesh.load_mesh(destination/'plate_single.stl');check(reread,1)
    if not np.allclose(reread.extents,plate_size(p),atol=.001,rtol=0):raise RuntimeError('平板导出尺寸不符。')
    (destination/'plate_parametric.scad').write_text(plate_scad(p),encoding='utf-8')
    (destination/'preview.html').write_text(preview_html(p,mesh),encoding='utf-8')
    kind={RectPlateParameters:'rectangle',SquarePlateParameters:'square',CirclePlateParameters:'circle'}[type(p)]
    report={'units':'mm','type':kind,'parameters':asdict(p),'outer_dimensions_mm':mesh.extents.tolist(),'single_closed':True,'components':[1],'volume_mm3':float(mesh.volume),'physically_print_tested':False}
    (destination/'parameters.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (destination/'打印说明.txt').write_text(f'''实心平板，单位 mm。类型：{kind}，参数：{asdict(p)}。
尺寸为成品最大外尺寸，不添加装配间隙。R 为俯视四角圆角，C 为上下周边 45 度倒角的水平/竖直退让量。
C 必须小于板厚一半；倒角后中间直壁保持最大外形尺寸。圆形板没有四角圆角参数。
圆形与圆角使用多边形近似，最大支持尺寸下轮廓弦高误差约 0.04 mm。
按毫米、100% 比例导入切片软件，平放打印，检查底部倒角的悬空效果。先打印试配。
已检查数字尺寸和网格，未做实物打印验证。输出 plate_single.stl、plate_parametric.scad 和 preview.html。
''',encoding='utf-8')
    return report


def build_ucover(p):
    p.validate()
    import numpy as np
    import manifold3d as m
    import trimesh
    # X is the open-ended length; opposite walls run along X, at Y=0 and Y=max.
    body=m.Manifold.cube(p.extents)
    if isinstance(p,ClosedCoverParameters):
        body-=m.Manifold.cube((p.length,p.width,p.height+1)).translate((p.wall,p.wall,p.base))
    else:
        body-=m.Manifold.cube((p.length+2,p.width,p.height+1)).translate((-1,p.wall,p.base))
    raw=body.to_mesh()
    mesh=trimesh.Trimesh(vertices=np.asarray(raw.vert_properties)[:,:3],faces=np.asarray(raw.tri_verts),process=True)
    check(mesh,1)
    if not np.allclose(mesh.extents,p.extents,atol=.0002,rtol=0):
        raise RuntimeError('盖板尺寸检查失败。')
    return mesh


def build_cuboid(p):
    p.validate()
    import numpy as np
    import manifold3d as m
    import trimesh
    w=p.wall
    # Three perpendicular plates only: negative-X, negative-Y, negative-Z.
    # The positive ends remain fully open, with no opposing faces or lid.
    body=m.Manifold.cube((p.x+w,p.y+w,p.z+w))
    body-=m.Manifold.cube((p.x+1,p.y+1,p.z+1)).translate((w,w,w))
    raw=body.to_mesh()
    mesh=trimesh.Trimesh(vertices=np.asarray(raw.vert_properties)[:,:3],faces=np.asarray(raw.tri_verts),process=True)
    check(mesh,1)
    if not np.allclose(mesh.extents,[p.x+w,p.y+w,p.z+w],atol=.0001,rtol=0):
        raise RuntimeError('三面护角尺寸检查失败。')
    return mesh


def build(p):
    if isinstance(p,PLATES):return build_plate(p)
    if isinstance(p,UCoverParameters):return build_ucover(p)
    if isinstance(p,CuboidParameters):return build_cuboid(p)
    p.validate()
    import numpy as np
    import manifold3d as m
    import trimesh

    d, l, w, b, g, h, c, e = (p.overlap, p.arm, p.wall, p.bottom,
                              p.slot, p.height, p.chamfer, p.entry)
    profile = [(-w+c,-w),(l-c,-w),(l,-w+c),(l,d),(d,d),(d,l),
               (-w+c,l),(-w,l-c),(-w,-w+c)]
    body = m.CrossSection([profile]).extrude(h)
    body -= m.Manifold.cube((l+1,l+1,g)).translate((0,0,b))
    # Extend cutters beyond the outer surface to avoid coincident-edge artifacts.
    eps = min(0.1, e / 2)
    for poly in [[(d-e,b),(d+eps,b-e-eps),(d+eps,b+eps),(d-e,b+eps)],
                 [(d-e,b+g-eps),(d+eps,b+g-eps),(d+eps,b+g+e+eps),(d-e,b+g)]]:
        cutter = m.CrossSection([poly]).extrude(l+eps).rotate((90,0,0)).translate((0,l+eps,0))
        body = body - cutter - cutter.mirror((1,-1,0))
    raw = body.to_mesh()
    mesh = trimesh.Trimesh(vertices=np.asarray(raw.vert_properties)[:,:3],
                           faces=np.asarray(raw.tri_verts), process=True)
    mesh.merge_vertices(digits_vertex=5)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    mesh.apply_translation((w,w,0))
    check(mesh, 1)
    if not np.allclose(mesh.extents, [l+w,l+w,h], atol=0.0001, rtol=0):
        raise RuntimeError('模型尺寸检查未通过。')
    return mesh


def check(mesh, components):
    if not (mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0):
        raise RuntimeError('模型封闭性检查未通过，未输出打印文件。')
    if len(mesh.split()) != components:
        raise RuntimeError('模型组件数量检查未通过。')


def scad_source(p):
    if isinstance(p,ClosedCoverParameters):
        return '// Four-wall cover. mm. length, width and height are INNER dimensions.\n'+'\n'.join(f'{k}={v:g};' for k,v in asdict(p).items())+'''
assert(min(width,length,height,base,wall)>=0.2);
difference() {
    cube([length+2*wall,width+2*wall,height+base]);
    translate([wall,wall,base]) cube([length,width,height+1]);
}
'''
    if isinstance(p,UCoverParameters):
        return '// U-shaped cover. mm. width is INNER width; height is INNER wall height.\n'+'\n'.join(f'{k}={v:g};' for k,v in asdict(p).items())+'''
assert(min(width,length,height,base,wall)>=0.2);
difference() {
    cube([length,width+2*wall,height+base]);
    translate([-1,wall,base]) cube([length+2,width,height+1]);
}
'''
    if isinstance(p,CuboidParameters):
        return '// Cuboid three-face guard. Units: mm. Lengths exclude wall.\n' + '\n'.join(f'{k}={v:g};' for k,v in asdict(p).items()) + '''
mode="single"; // "single", "mirrored", "eight"
assert(min(x,y,z,wall)>=0.2);
module corner() {
    difference() {
        cube([x+wall,y+wall,z+wall]);
        translate([wall,wall,wall]) cube([x+1,y+1,z+1]);
    }
}
module reflected() { translate([x+wall,0,0]) mirror([1,0,0]) corner(); }
if(mode=="single") corner();
if(mode=="mirrored") reflected();
if(mode=="eight") for(row=[0:1]) for(col=[0:3])
    translate([col*(x+wall+6),row*(y+wall+6),0])
        if(col%2==0) corner(); else reflected();
'''
    header = '// Millimetres. arm = length along each PCB edge, excluding wall.\n'
    header += '\n'.join(f'{k} = {v:g};' for k,v in asdict(p).items())
    return header + '''
mode = "single"; // "single" or "four"
c = min(0.8, wall/3, arm/10);
e = min(0.4, overlap/4, bottom/4, top/4);
eps = min(0.1, e/2);
h = bottom + slot + top;
assert(min(overlap,slot,top,bottom,arm,wall)>=0.2);
assert(arm>overlap);
module relief(poly) {
    translate([0,arm+eps,0]) rotate([90,0,0])
        linear_extrude(height=arm+eps) polygon(poly);
}
module cuts() {
    relief([[overlap-e,bottom],[overlap+eps,bottom-e-eps],
            [overlap+eps,bottom+eps],[overlap-e,bottom+eps]]);
    relief([[overlap-e,bottom+slot-eps],[overlap+eps,bottom+slot-eps],
            [overlap+eps,bottom+slot+e+eps],[overlap-e,bottom+slot]]);
}
module corner() {
    translate([wall,wall,0]) difference() {
        linear_extrude(height=h) polygon([
            [-wall+c,-wall],[arm-c,-wall],[arm,-wall+c],[arm,overlap],
            [overlap,overlap],[overlap,arm],[-wall+c,arm],
            [-wall,arm-c],[-wall,-wall+c]]);
        translate([0,0,bottom]) cube([arm+1,arm+1,slot]);
        cuts(); mirror([1,-1,0]) cuts();
    }
}
if(mode=="single") corner();
if(mode=="four") for(x=[0,arm+wall+6]) for(y=[0,arm+wall+6])
    translate([x,y,0]) corner();
'''


def preview_html(p, mesh):
    data = json.dumps({'v':mesh.vertices.round(5).tolist(),'f':mesh.faces.tolist()}, separators=(',',':'))
    labels=dict(diameter='直径',side='边长',length='长度',width='宽度',thickness='厚度',radius='圆角 R',bevel='倒角 C')
    text = (('实心平板 · '+ ' · '.join(f'{labels[k]} {v:g}' for k,v in asdict(p).items())+' mm')
            if isinstance(p,PLATES) else
            f'四周封闭盖板 · 内长 {p.length:g} · 内宽 {p.width:g} · 内高 {p.height:g} · 平板厚 {p.base:g} · 侧壁厚 {p.wall:g} mm'
            if isinstance(p,ClosedCoverParameters) else
            f'U 形盖板 · 内宽 {p.width:g} · 长度 {p.length:g} · 侧壁内高 {p.height:g} · 平板厚 {p.base:g} · 侧壁厚 {p.wall:g} mm'
            if isinstance(p,UCoverParameters) else
            f'三面护角 · X 包覆 {p.x:g} · Y 包覆 {p.y:g} · Z 包覆 {p.z:g} · 壁厚 {p.wall:g} mm'
            if isinstance(p,CuboidParameters) else
            f'内嵌 {p.overlap:g} · 夹槽 {p.slot:g} · 上垫高 {p.top:g} · 下垫高 {p.bottom:g} · 边长 {p.arm:g} mm')
    template = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PCB 护角模型预览</title><style>
body{margin:0;background:#f3f6fa;color:#233044;font:16px system-ui,sans-serif}
main{max-width:1000px;margin:35px auto;padding:0 24px}h1{font-size:26px}
canvas{display:block;width:100%;height:520px;background:white;border-radius:18px;touch-action:none}
p{line-height:1.7}small{color:#596777}button{border:0;border-radius:8px;background:#dce6f2;padding:10px 16px;cursor:pointer}
</style><main><h1>PCB 四角护套</h1><p>__TEXT__</p>
<canvas id="view" aria-label="可拖动旋转的护角模型"></canvas>
<p><button id="reset">重置视角</button>　拖动旋转，滚轮缩放。</p>
<small>边长指沿 PCB 每条边的延伸长度，不含外侧壁厚。此处显示单个护角，不含 PCB 和包装。先打印单件试配。</small></main>
<script>
const mesh=__DATA__,canvas=document.getElementById('view'),ctx=canvas.getContext('2d');
let a=.78,b=-.45,zoom=1,drag=null;
const lo=[0,1,2].map(i=>Math.min(...mesh.v.map(v=>v[i]))),hi=[0,1,2].map(i=>Math.max(...mesh.v.map(v=>v[i])));
const center=lo.map((n,i)=>(n+hi[i])/2),extent=Math.max(...hi.map((n,i)=>n-lo[i]));
function render(){
 const r=canvas.getBoundingClientRect(),d=devicePixelRatio||1;canvas.width=r.width*d;canvas.height=r.height*d;ctx.scale(d,d);
 const s=Math.min(r.width,r.height)*.55/extent*zoom;
 const points=mesh.v.map(v=>{let x=v[0]-center[0],y=v[1]-center[1],z=v[2]-center[2];
 let u=Math.cos(a)*x-Math.sin(a)*y,t=Math.sin(a)*x+Math.cos(a)*y;
 return [u,Math.sin(b)*t+Math.cos(b)*z,Math.cos(b)*t-Math.sin(b)*z];});
 const faces=mesh.f.map(f=>({f,z:f.reduce((n,i)=>n+points[i][2],0)/3})).sort((x,y)=>x.z-y.z);
 for(const {f} of faces){const p=f.map(i=>points[i]);let u=p[1].map((n,i)=>n-p[0][i]),v=p[2].map((n,i)=>n-p[0][i]);
 const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],len=Math.hypot(...n)||1;
 const light=.6+.4*Math.abs((n[0]*.3+n[1]*.5+n[2]*.8)/len);
 ctx.beginPath();p.forEach((q,i)=>ctx[i?'lineTo':'moveTo'](r.width/2+q[0]*s,r.height/2-q[1]*s));ctx.closePath();
 ctx.fillStyle=`rgb(${Math.round(239*light)},${Math.round(163*light)},${Math.round(63*light)})`;ctx.fill();ctx.strokeStyle='#65543b';ctx.lineWidth=.4;ctx.stroke();}
}
canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId)};
canvas.onpointermove=e=>{if(!drag)return;a+=(e.clientX-drag[0])*.01;b-=(e.clientY-drag[1])*.01;drag=[e.clientX,e.clientY];render()};
canvas.onpointerup=canvas.onpointercancel=()=>drag=null;
canvas.onwheel=e=>{e.preventDefault();zoom=Math.max(.3,Math.min(3,zoom*Math.exp(-e.deltaY*.001)));render()};
document.getElementById('reset').onclick=()=>{a=.78;b=-.45;zoom=1;render()};window.onresize=render;render();
</script></html>'''
    if isinstance(p,CuboidParameters):
        template=template.replace('PCB 护角模型预览','三面护角模型预览').replace('PCB 四角护套','立方体 / 长方体三面护角').replace('边长指沿 PCB 每条边的延伸长度，不含外侧壁厚。此处显示单个护角，不含 PCB 和包装。先打印单件试配。','X/Y/Z 为沿物体三条棱的包覆长度，不含壁厚；三个相邻面封闭，对向全部开口。先打印单件试配。')
    if isinstance(p,UCoverParameters):
        template=template.replace('PCB 护角模型预览','U 形盖板预览').replace('PCB 四角护套','U 形盖板：两端开口').replace('边长指沿 PCB 每条边的延伸长度，不含外侧壁厚。此处显示单个护角，不含 PCB 和包装。先打印单件试配。','一块平板和两条相对侧壁，长度方向两端开口。内宽和内高均为净尺寸，不会额外增加装配间隙。')
    if isinstance(p,ClosedCoverParameters):
        template=template.replace('U 形盖板预览','四周封闭盖板预览').replace('U 形盖板：两端开口','四周封闭盖板：套入面开口').replace('一块平板和两条相对侧壁，长度方向两端开口。内宽和内高均为净尺寸，不会额外增加装配间隙。','一块平板和四周侧壁，仅套入面开口。内长、内宽、内高均为净尺寸，不额外增加装配间隙。')
    if isinstance(p,PLATES):
        template=template.replace('PCB 护角模型预览','实心平板预览').replace('PCB 四角护套','实心平板').replace('边长指沿 PCB 每条边的延伸长度，不含外侧壁厚。此处显示单个护角，不含 PCB 和包装。先打印单件试配。','R 为俯视四角圆角半径；C 为上下边缘 45° 倒角。尺寸为最大成品外尺寸。')
    return template.replace('__TEXT__',text).replace('__DATA__',data)


def generate_ucover(p,destination):
    import numpy as np
    import trimesh
    mesh=build(p)
    destination=Path(destination).expanduser().resolve()
    destination.mkdir(parents=True,exist_ok=True)
    mesh.export(destination/'cover_single.stl')
    reread=trimesh.load_mesh(destination/'cover_single.stl')
    check(reread,1)
    if not np.allclose(reread.extents,p.extents,atol=.001,rtol=0):
        raise RuntimeError('盖板导出尺寸校验失败。')
    (destination/'cover_parametric.scad').write_text(scad_source(p),encoding='utf-8')
    (destination/'preview.html').write_text(preview_html(p,mesh),encoding='utf-8')
    closed=isinstance(p,ClosedCoverParameters)
    report={'units':'mm','type':'closedcover' if closed else 'ucover','parameters':asdict(p),'outer_dimensions_mm':mesh.extents.tolist(),
            'volume_mm3':float(mesh.volume),'single_closed':True,'components':[1],'physically_print_tested':False}
    (destination/'parameters.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if closed:
        note=f'''四周封闭盖板（单位：mm）
内长 {p.length:g}，内宽 {p.width:g}，内高 {p.height:g}，平板厚度 {p.base:g}，侧壁厚度 {p.wall:g}。
外形：外长 {p.length+2*p.wall:g} × 外宽 {p.width+2*p.wall:g} × 总高 {p.height+p.base:g}。
结构为一块平板和四周侧壁，仅套入物体的一面开口，不是六面封死的盒体。
内长、内宽是相对侧壁内表面的净距离，内高从平板内表面量起。不自动增加装配间隙。
cover_single.stl 为单件；cover_parametric.scad 可修改；preview.html 可离线旋转查看。
平板外表面朝下打印，切片单位毫米、100% 比例。确认打印平台尺寸及物体配合间隙。
四周侧壁等高等厚，无卡扣、圆角或螺丝孔。预览开口朝上，作盖板使用时可以翻转。
已检查数字模型封闭性和尺寸，未进行实物打印、配合或承载测试。
'''
    else:
        note=f'''U 形盖板（单位：mm）
内宽 {p.width:g}，长度 {p.length:g}，侧壁内高 {p.height:g}，平板厚度 {p.base:g}，侧壁厚度 {p.wall:g}。
外形：长度 {p.length:g} × 外宽 {p.width+2*p.wall:g} × 总高 {p.height+p.base:g}。
结构为一块平板和两条相对的侧壁，沿长度方向两端敞开，没有端墙、顶盖、卡扣或螺丝孔。
内宽为两侧壁内表面净距离；侧壁内高从平板内表面量起。不会自动添加装配间隙。
cover_single.stl 为单件；cover_parametric.scad 可修改；preview.html 可离线旋转查看。
平板外表面朝下打印，导入切片软件时使用毫米、100% 比例。确认模型适合打印平台。
尺寸较大时需检查平板翘曲和设备设置。用于套住物体时，先确认内宽和内高的装配余量。
已验证数字模型封闭性和尺寸，未进行实物打印、配合或承载测试。
'''
    (destination/'打印说明.txt').write_text(note,encoding='utf-8')
    return report


def generate(p, destination):
    if isinstance(p,PLATES):return generate_plate(p,destination)
    if isinstance(p,UCoverParameters):return generate_ucover(p,destination)
    mesh = build(p)
    import trimesh
    import numpy as np
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True,exist_ok=True)
    cuboid=isinstance(p,CuboidParameters)
    stride_x=(p.x if cuboid else p.arm)+p.wall+6
    stride_y=(p.y if cuboid else p.arm)+p.wall+6
    mirrored=None
    if cuboid:
        mirrored=mesh.copy();mirrored.apply_scale([-1,1,1])
        mirrored.apply_translation(-mirrored.bounds[0]);check(mirrored,1)
    count=8 if cuboid else 4
    parts = []
    for index in range(count):
        cols=4 if cuboid else 2
        piece=(mirrored if cuboid and index%2 else mesh).copy()
        piece.apply_translation(((index%cols)*stride_x,(index//cols)*stride_y,0));parts.append(piece)
    plate=trimesh.util.concatenate(parts)
    check(plate,count)
    exports=[('corner_single.stl',mesh,1),('corner_eight.stl' if cuboid else 'corner_four.stl',plate,count)]
    if cuboid:exports.append(('corner_mirrored.stl',mirrored,1))
    for name,obj,components in exports:
        path=destination/name
        obj.export(path)
        reread=trimesh.load_mesh(path)
        check(reread,components)
        if not np.allclose(reread.extents,obj.extents,atol=.001,rtol=0):
            raise RuntimeError('导出尺寸校验失败。')
    (destination/'corner_parametric.scad').write_text(scad_source(p),encoding='utf-8')
    (destination/'preview.html').write_text(preview_html(p,mesh),encoding='utf-8')
    report={'units':'mm','type':'cuboid' if cuboid else 'pcb','parameters':asdict(p),'outer_dimensions_mm':mesh.extents.tolist(),
            'volume_mm3':float(mesh.volume),'single_closed':True,'pack_closed':True,
            'pack_count':count,'components':[1,count],'physically_print_tested':False}
    if not cuboid:report['four_closed']=True
    (destination/'parameters.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if cuboid:
        note=f'''立方体 / 长方体三面护角（单位：mm）
X 包覆长度 {p.x:g}；Y 包覆长度 {p.y:g}；Z 包覆长度 {p.z:g}；壁厚 {p.wall:g}。
外形 {p.x+p.wall:g} × {p.y+p.wall:g} × {p.z+p.wall:g}。
仅有一个顶点相邻的三个互相垂直的面，其余方向敞开。包覆长度不含壁厚，不是物体的完整长宽高。
没有 PCB 夹槽、上下夹持唇边或自动添加的配合间隙；三个内壁直接贴近物体相邻表面。
corner_single.stl 是单件；corner_mirrored.stl 是镜像件；corner_eight.stl 为四个原件和四个镜像件。
当 X/Y/Z 不同时，使用镜像件并适当旋转，才能在八个顶点保持包覆长度与物体轴向一致。
每条棱两端包覆长度之和不应超过物体对应尺寸，否则相邻护角会重叠。
底面朝下导入切片软件，单位毫米、100% 比例；八件排版可能超出打印平台，可在切片软件重新排布。
先打印单件验证贴合。运输包装需定位，防止滑脱。该模型未做实物打印、承载或运输测试。
preview.html 为单件离线三维预览；corner_parametric.scad 可修改并重新导出。
'''
    else:
        note=f'''PCB 护角打印说明（单位：mm）

内嵌深度：{p.overlap:g}；夹槽：{p.slot:g}；上垫高：{p.top:g}；下垫高：{p.bottom:g}。
护角边长：{p.arm:g}；外侧壁厚：{p.wall:g}。
单件外形：{p.arm+p.wall:g} × {p.arm+p.wall:g} × {p.height:g}。

corner_single.stl 为单件，corner_four.stl 为四件排版，导入切片软件时使用毫米、100% 比例。
corner_parametric.scad 是可编辑源文件；preview.html 可离线打开、拖动旋转。
边长指沿 PCB 每条边的延伸长度，不含壁厚。内嵌深度按到相邻板边的垂直距离计算。
夹槽是实际建模净高，不是板厚；程序不会额外添加装配间隙。
上下垫高从夹槽上下表面分别向外计算；护角总高=下垫高+夹槽+上垫高。
四个护角相同，装配时转向四角。PCB 长宽不影响单件形状。

先打印单件，清理槽内毛刺并用废板试配。夹槽上沿有局部悬空，请检查切片并按设备能力设置支撑。
仅允许接触板边安全区域。当前项目原有安全边界为 3 mm；更换 PCB 时请重新确认。
这是开槽护套，无主动锁扣；运输包装须限制护角向外滑脱。上下包装支撑面必须避开芯片。
模型已做数字几何检查，未验证实物松紧、承载、材料性能或运输保护效果。
'''
    (destination/'打印说明.txt').write_text(note,encoding='utf-8')
    return report


def gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root=tk.Tk(); root.title('护角、盖板与平板生成器 v1.4'); root.geometry('1040x740'); root.minsize(1000,720)
    outer=ttk.Frame(root,padding=24); outer.pack(fill='both',expand=True)
    ttk.Label(outer,text='护角、盖板与平板生成器',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
    ttk.Label(outer,text='选择结构类型，输入毫米尺寸，生成 STL 和可旋转预览。').pack(anchor='w',pady=(8,16))
    notebook=ttk.Notebook(outer);notebook.pack(fill='x')
    form=ttk.Frame(notebook,padding=12);notebook.add(form,text='PCB 夹槽护角')
    cubeform=ttk.Frame(notebook,padding=12);notebook.add(cubeform,text='立方体 / 长方体三面护角')
    uform=ttk.Frame(notebook,padding=12);notebook.add(uform,text='U 形盖板')
    closedform=ttk.Frame(notebook,padding=12);notebook.add(closedform,text='四周封闭盖板')
    fields={}
    spec=[('overlap','内嵌深度','覆盖 PCB 边缘的宽度'),('slot','夹槽高度','槽的净高，已包含你需要的间隙'),
          ('top','上垫高','从夹槽上表面向上'),('bottom','下垫高','从夹槽下表面向下'),
          ('arm','护角边长','沿 PCB 每条边延伸，不含外侧壁厚'),('wall','外侧壁厚','一般保持 3 mm')]
    for row,(key,label,hint) in enumerate(spec):
        ttk.Label(form,text=label+' (mm)').grid(row=row,column=0,sticky='w',pady=7)
        var=tk.StringVar(value=f'{getattr(Parameters(),key):g}'); fields[key]=var
        ttk.Entry(form,textvariable=var,width=12).grid(row=row,column=1,padx=14)
        ttk.Label(form,text=hint).grid(row=row,column=2,sticky='w')
    cubefields={}
    for row,(key,label) in enumerate([('x','X 方向包覆长度'),('y','Y 方向包覆长度'),('z','Z 方向包覆长度'),('wall','三个面的壁厚')]):
        ttk.Label(cubeform,text=label+' (mm)').grid(row=row,column=0,sticky='w',pady=7)
        var=tk.StringVar(value=f'{getattr(CuboidParameters(),key):g}');cubefields[key]=var
        ttk.Entry(cubeform,textvariable=var,width=12).grid(row=row,column=1,padx=14)
    ttk.Label(cubeform,text='三个相邻面围住顶点，其余方向敞开。\n包覆长度不含壁厚，不是物体完整长宽高。\n输出单件、镜像件与八件排版。',wraplength=580).grid(row=4,column=0,columnspan=3,sticky='w',pady=10)
    ufields={}
    for row,(key,label,hint) in enumerate([('width','内宽','两侧壁内表面的净距离'),('length','长度','沿侧壁方向，两开口之间的距离'),('height','侧壁内高','从平板内表面到侧壁顶部'),('base','平板厚度','中间平板的厚度'),('wall','侧壁厚度','两条侧壁的共同厚度')]):
        ttk.Label(uform,text=label+' (mm)').grid(row=row,column=0,sticky='w',pady=7)
        var=tk.StringVar(value=f'{getattr(UCoverParameters(),key):g}');ufields[key]=var
        ttk.Entry(uform,textvariable=var,width=12).grid(row=row,column=1,padx=14)
        ttk.Label(uform,text=hint).grid(row=row,column=2,sticky='w')
    ttk.Label(uform,text='两端开口；不额外添加装配间隙。输出单件盖板。').grid(row=5,column=0,columnspan=3,sticky='w',pady=10)
    closedfields={}
    for row,(key,label,hint) in enumerate([('length','内长','两端侧壁内表面之间的净距离'),('width','内宽','左右侧壁内表面之间的净距离'),('height','内高','从平板内表面到侧壁口沿'),('base','平板厚度','中间平板的厚度'),('wall','侧壁厚度','四周侧壁的共同厚度')]):
        ttk.Label(closedform,text=label+' (mm)').grid(row=row,column=0,sticky='w',pady=7)
        var=tk.StringVar(value=f'{getattr(ClosedCoverParameters(),key):g}');closedfields[key]=var
        ttk.Entry(closedform,textvariable=var,width=12).grid(row=row,column=1,padx=14)
        ttk.Label(closedform,text=hint).grid(row=row,column=2,sticky='w')
    ttk.Label(closedform,text='四周封闭，仅套入面开口；不额外添加装配间隙。').grid(row=5,column=0,columnspan=3,sticky='w',pady=10)
    plateforms=[]
    for cls,title,spec in [
        (CirclePlateParameters,'圆形板',[('diameter','直径 D'),('thickness','厚度 T'),('bevel','边缘倒角 C')]),
        (RectPlateParameters,'矩形板',[('length','长度 L'),('width','宽度 W'),('thickness','厚度 T'),('radius','四角圆角半径 R'),('bevel','边缘倒角 C')]),
        (SquarePlateParameters,'方形板',[('side','边长 A'),('thickness','厚度 T'),('radius','四角圆角半径 R'),('bevel','边缘倒角 C')])]:
        panel=ttk.Frame(notebook,padding=12);notebook.add(panel,text=title);values={}
        for row,(key,label) in enumerate(spec):
            ttk.Label(panel,text=label+' (mm)').grid(row=row,column=0,sticky='w',pady=7)
            var=tk.StringVar(value=f'{getattr(cls(),key):g}');values[key]=var
            ttk.Entry(panel,textvariable=var,width=12).grid(row=row,column=1,padx=14)
        ttk.Label(panel,text='R / C 默认为 0。C 为上下周边 45° 倒角，须小于厚度一半。\nR 为俯视四角圆角半径，最大为短边的一半。圆形板无需 R。',wraplength=700).grid(row=len(spec),column=0,columnspan=3,sticky='w',pady=12)
        plateforms.append((cls,values))
    def current():
        cls,values=([(Parameters,fields),(CuboidParameters,cubefields),(UCoverParameters,ufields),(ClosedCoverParameters,closedfields)]+plateforms)[notebook.index(notebook.select())]
        p=cls(**{k:float(v.get()) for k,v in values.items()});p.validate();return p
    dims=tk.StringVar()
    def update(*_):
        try:
            p=current()
            size=plate_size(p) if isinstance(p,PLATES) else (p.extents if isinstance(p,UCoverParameters) else ([p.x+p.wall,p.y+p.wall,p.z+p.wall] if isinstance(p,CuboidParameters) else [p.arm+p.wall,p.arm+p.wall,p.height]))
            dims.set('单件外形：'+' × '.join(f'{v:g}' for v in size)+' mm')
        except ValueError: dims.set('请填写有效尺寸。')
    for v in [*fields.values(),*cubefields.values(),*ufields.values(),*closedfields.values(),*[v for _,f in plateforms for v in f.values()]]: v.trace_add('write',update)
    notebook.bind('<<NotebookTabChanged>>',update)
    update();ttk.Label(outer,textvariable=dims).pack(anchor='w',pady=12)
    dest=tk.StringVar(value=str(Path(__file__).resolve().parent/'生成的模型'))
    folder=ttk.Frame(outer);folder.pack(fill='x',pady=8)
    ttk.Entry(folder,textvariable=dest).pack(side='left',fill='x',expand=True)
    def browse():
        path=filedialog.askdirectory(title='选择输出文件夹')
        if path:dest.set(path)
    ttk.Button(folder,text='选择目录',command=browse).pack(side='right',padx=(8,0))
    status=tk.StringVar(value='每次生成会新建一个带时间的文件夹。')
    ttk.Label(outer,textvariable=status,wraplength=615).pack(anchor='w',pady=10)
    last=[None]
    def run():
        try:
            p=current()
            if not dest.get().strip():raise ValueError('请选择输出目录。')
            button.config(state='disabled'); status.set('正在生成并检查模型……');root.update_idletasks()
            prefix=({CirclePlateParameters:'圆形板_',RectPlateParameters:'矩形板_',SquarePlateParameters:'方形板_'}[type(p)] if isinstance(p,PLATES) else ('四周封闭盖板_' if isinstance(p,ClosedCoverParameters) else ('U形盖板_' if isinstance(p,UCoverParameters) else ('三面护角_' if isinstance(p,CuboidParameters) else 'PCB护角_'))))
            path=Path(dest.get())/(prefix+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            generate(p,path);last[0]=path.resolve();status.set(f'已生成并通过封闭性检查：{last[0]}')
            preview.config(state='normal')
        except ImportError:
            messagebox.showerror('缺少运行依赖','请先双击“安装依赖.cmd”，完成后重新打开生成器。')
        except Exception as exc:messagebox.showerror('未能生成',str(exc));status.set('未完成，请检查参数或错误提示。')
        finally:button.config(state='normal')
    buttons=ttk.Frame(outer);buttons.pack(fill='x',pady=8)
    button=ttk.Button(buttons,text='生成模型',command=run);button.pack(side='left')
    preview=ttk.Button(buttons,text='打开 3D 预览',state='disabled',command=lambda:webbrowser.open((last[0]/'preview.html').as_uri()));preview.pack(side='left',padx=12)
    ttk.Label(outer,text='先确认尺寸和切片效果，再打印试配。护角用于运输时需包装定位。',wraplength=650).pack(anchor='w',pady=12)
    root.mainloop()


def main():
    ap=argparse.ArgumentParser(description='生成护角、盖板、圆形/矩形/方形板 STL，单位 mm。无参数启动窗口。')
    ap.add_argument('--gui',action='store_true')
    types={'pcb':Parameters,'cuboid':CuboidParameters,'ucover':UCoverParameters,'closedcover':ClosedCoverParameters,'circle':CirclePlateParameters,'rectangle':RectPlateParameters,'square':SquarePlateParameters}
    allkeys=set().union(*(asdict(cls()) for cls in types.values()))
    ap.add_argument('--type',choices=list(types),default='pcb')
    for key in sorted(allkeys):
        ap.add_argument('--'+key,type=float,default=None)
    ap.add_argument('--out',type=Path,help='输出目录；命令行模式必填。已有同名模型文件会更新。')
    args=ap.parse_args()
    if args.gui or len(sys.argv)==1:gui();return
    if args.out is None:ap.error('命令行生成需要 --out 输出目录。')
    try:
        cls=types[args.type]
        valid=asdict(cls())
        irrelevant=allkeys
        irrelevant={k for k in irrelevant-set(valid) if getattr(args,k) is not None}
        if irrelevant:ap.error('当前类型不使用这些参数：'+', '.join(sorted(irrelevant)))
        p=cls(**{k:getattr(args,k) if getattr(args,k) is not None else v for k,v in valid.items()})
        result=generate(p,args.out)
    except ImportError as exc:ap.exit(2,f'缺少依赖：{exc}。请安装 requirements.txt 中的库。\n')
    except (ValueError,RuntimeError,OSError) as exc:ap.exit(2,f'生成失败：{exc}\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
