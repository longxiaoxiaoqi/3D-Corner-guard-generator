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


def build(p):
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
    text = f'内嵌 {p.overlap:g} · 夹槽 {p.slot:g} · 上垫高 {p.top:g} · 下垫高 {p.bottom:g} · 边长 {p.arm:g} mm'
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
    return template.replace('__TEXT__',text).replace('__DATA__',data)


def generate(p, destination):
    mesh = build(p)
    import trimesh
    import numpy as np
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True,exist_ok=True)
    stride = p.arm + p.wall + 6
    parts = []
    for x,y in [(0,0),(stride,0),(0,stride),(stride,stride)]:
        piece=mesh.copy(); piece.apply_translation((x,y,0)); parts.append(piece)
    plate=trimesh.util.concatenate(parts)
    check(plate,4)
    for name,obj,count in [('corner_single.stl',mesh,1),('corner_four.stl',plate,4)]:
        path=destination/name
        obj.export(path)
        reread=trimesh.load_mesh(path)
        check(reread,count)
        if not np.allclose(reread.extents,obj.extents,atol=.001,rtol=0):
            raise RuntimeError('导出尺寸校验失败。')
    (destination/'corner_parametric.scad').write_text(scad_source(p),encoding='utf-8')
    (destination/'preview.html').write_text(preview_html(p,mesh),encoding='utf-8')
    report={'units':'mm','parameters':asdict(p),'outer_dimensions_mm':mesh.extents.tolist(),
            'volume_mm3':float(mesh.volume),'single_closed':True,'four_closed':True,
            'components':[1,4],'physically_print_tested':False}
    (destination/'parameters.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
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
    root=tk.Tk(); root.title('PCB 护角模型生成器'); root.geometry('690x620'); root.minsize(650,600)
    outer=ttk.Frame(root,padding=24); outer.pack(fill='both',expand=True)
    ttk.Label(outer,text='PCB 护角模型生成器',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
    ttk.Label(outer,text='输入毫米尺寸，一次生成单件和四件排版 STL。').pack(anchor='w',pady=(8,16))
    form=ttk.Frame(outer); form.pack(fill='x')
    fields={}
    spec=[('overlap','内嵌深度','覆盖 PCB 边缘的宽度'),('slot','夹槽高度','槽的净高，已包含你需要的间隙'),
          ('top','上垫高','从夹槽上表面向上'),('bottom','下垫高','从夹槽下表面向下'),
          ('arm','护角边长','沿 PCB 每条边延伸，不含外侧壁厚'),('wall','外侧壁厚','一般保持 3 mm')]
    for row,(key,label,hint) in enumerate(spec):
        ttk.Label(form,text=label+' (mm)').grid(row=row,column=0,sticky='w',pady=7)
        var=tk.StringVar(value=f'{getattr(Parameters(),key):g}'); fields[key]=var
        ttk.Entry(form,textvariable=var,width=12).grid(row=row,column=1,padx=14)
        ttk.Label(form,text=hint).grid(row=row,column=2,sticky='w')
    dims=tk.StringVar()
    def update(*_):
        try:
            p=Parameters(**{k:float(v.get()) for k,v in fields.items()});p.validate()
            dims.set(f'单件外形：{p.arm+p.wall:g} × {p.arm+p.wall:g} × {p.height:g} mm')
        except ValueError: dims.set('请填写有效尺寸。')
    for v in fields.values(): v.trace_add('write',update)
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
            p=Parameters(**{k:float(v.get()) for k,v in fields.items()});p.validate()
            if not dest.get().strip():raise ValueError('请选择输出目录。')
            button.config(state='disabled'); status.set('正在生成并检查模型……');root.update_idletasks()
            path=Path(dest.get())/datetime.now().strftime('护角_%Y%m%d_%H%M%S_%f')
            generate(p,path);last[0]=path.resolve();status.set(f'已生成并通过封闭性检查：{last[0]}')
            preview.config(state='normal')
        except ImportError:
            messagebox.showerror('缺少运行依赖','请先双击“安装依赖.cmd”，完成后重新打开生成器。')
        except Exception as exc:messagebox.showerror('未能生成',str(exc));status.set('未完成，请检查参数或错误提示。')
        finally:button.config(state='normal')
    buttons=ttk.Frame(outer);buttons.pack(fill='x',pady=8)
    button=ttk.Button(buttons,text='生成护角模型',command=run);button.pack(side='left')
    preview=ttk.Button(buttons,text='打开 3D 预览',state='disabled',command=lambda:webbrowser.open((last[0]/'preview.html').as_uri()));preview.pack(side='left',padx=12)
    ttk.Label(outer,text='先打印单件试配。运输时用包装定位，防止独立护角滑脱。',wraplength=615).pack(anchor='w',pady=12)
    root.mainloop()


def main():
    ap=argparse.ArgumentParser(description='生成可打印 PCB 护角 STL，单位为 mm。无参数启动图形窗口。')
    ap.add_argument('--gui',action='store_true')
    for key in asdict(Parameters()):ap.add_argument('--'+key,type=float,default=getattr(Parameters(),key))
    ap.add_argument('--out',type=Path,help='输出目录；命令行模式必填。已有同名模型文件会更新。')
    args=ap.parse_args()
    if args.gui or len(sys.argv)==1:gui();return
    if args.out is None:ap.error('命令行生成需要 --out 输出目录。')
    try:
        p=Parameters(**{k:getattr(args,k) for k in asdict(Parameters())})
        result=generate(p,args.out)
    except ImportError as exc:ap.exit(2,f'缺少依赖：{exc}。请安装 requirements.txt 中的库。\n')
    except (ValueError,RuntimeError,OSError) as exc:ap.exit(2,f'生成失败：{exc}\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
