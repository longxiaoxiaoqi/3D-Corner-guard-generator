"""Offline desktop workspace; geometry stays in corner_guard.py."""
from dataclasses import asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import math
import os
import tkinter as tk
from tkinter import ttk, filedialog
import webbrowser

VERSION = '1.6.0'
BG, PANEL, INK, MUTED, ACCENT = '#eef2f6', '#ffffff', '#182c43', '#64748b', '#087f8c'
HISTORY = [
    ('1.6.0', '圆形封闭盖板与边缘修饰', [
        '新增第八种模型：圆形顶板和一圈侧壁，仅套入面开口。',
        '支持内径、内高、顶板厚度、侧壁厚度，以及开口内缘 45° 倒角。',
        '支持顶板外缘凸圆角和内腔底角凹圆角；三个修饰参数默认均为 0。',
        '新增特征组合校验、可滚动参数面板及圆形盖板的 STL、SCAD 和离线预览。']),
    ('1.5.0', '桌面工作台与独立 EXE', [
        '全新侧栏导航、分组参数和窗口内三维预览；拖动旋转、滚轮缩放、重置视角。',
        '后台生成与参数校验，记住各类型参数及输出目录，支持恢复默认。',
        '新增版本更新页面，收录 v1.0.0 至今的历史更新。',
        '提供内置依赖的 Windows EXE；源码首次启动自动准备独立环境。']),
    ('1.4.0', '圆形、矩形与方形平板', [
        '新增三种实心平板，模型类型扩展至七种。',
        '矩形和方形支持四角圆角 R；三种平板支持上下边缘 45° 倒角 C。',
        '支持圆角与倒角组合、最大圆角及 R 小于 C 的情况，增加几何与非法输入验证。']),
    ('1.3.0', '四周封闭盖板', [
        '新增四面侧壁、仅套入面开口的盖板。',
        '支持内长、内宽、内高、平板厚度和侧壁厚度，输出 STL、SCAD 和离线预览。']),
    ('1.2.0', 'U 形盖板', [
        '新增两端开口的 U 形盖板，支持内宽、长度、侧壁内高及两种厚度。',
        '输出单件盖板、参数记录、打印说明和可旋转预览。']),
    ('1.1.0', '立方体 / 长方体三面护角', [
        '新增围住一个顶点的三个相邻面的护角，X / Y / Z 包覆长度可分别设置。',
        '输出单件、镜像件及八件打印排版，保留 PCB 夹槽护角功能。']),
    ('1.0.0', 'PCB 夹槽护角 · 初始版本', [
        '提供本地参数窗口、命令行和配套技能，生成 PCB 四角保护结构。',
        '支持内嵌深度、夹槽净高、上下垫高、边长及壁厚。',
        '导出 STL、参数化 SCAD、离线预览和打印说明；后续补充首次依赖安装指引。']),
]
LABELS = {
    'overlap': ('内嵌深度', '覆盖 PCB 边缘的宽度'), 'slot': ('夹槽净高', '请自行预留装配间隙'),
    'top': ('上垫高', '夹槽上方厚度'), 'bottom': ('下垫高', '夹槽下方厚度'),
    'arm': ('护角边长', '沿 PCB 边延伸，不含壁厚'), 'wall': ('侧壁厚度', '各侧壁共同厚度'),
    'x': ('X 包覆长度', '沿 X 棱延伸，不含壁厚'), 'y': ('Y 包覆长度', '沿 Y 棱延伸，不含壁厚'),
    'z': ('Z 包覆长度', '沿 Z 棱延伸，不含壁厚'), 'width': ('内宽', '相对侧壁内表面净距'),
    'length': ('长度', '沿两端开口方向'), 'height': ('侧壁内高', '平板内表面至侧壁顶部'),
    'base': ('平板厚度', '底部平板厚度'), 'diameter': ('直径 D', '成品最大外径'),
    'side': ('边长 A', '成品最大外尺寸'), 'thickness': ('厚度 T', '成品总厚度'),
    'opening_chamfer': ('开口倒角 C', '开口内缘 45° 斜面，0 为无倒角'),
    'outer_radius': ('外缘圆角 R外', '封闭顶板与外侧壁交界的圆角'),
    'inner_radius': ('内部圆角 R内', '内腔底面与侧壁交界，占用内腔'),
    'radius': ('圆角 R', '四角圆角半径，0 为尖角'), 'bevel': ('倒角 C', '上下边缘 45° 倒角，0 为无倒角'),
}


class MeshView(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, bg='#e4edf2', highlightthickness=0)
        self.mesh = None
        self.yaw, self.pitch, self.zoom = -.65, .65, 1.
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<ButtonPress-1>', self.press)
        self.bind('<B1-Motion>', self.drag)
        self.bind('<MouseWheel>', self.wheel)

    def press(self, e):
        self.anchor = (e.x, e.y)

    def drag(self, e):
        self.yaw += (e.x-self.anchor[0])*.01
        self.pitch = max(-1.5, min(1.5, self.pitch+(e.y-self.anchor[1])*.01))
        self.anchor = (e.x, e.y)
        self.draw()

    def wheel(self, e):
        self.zoom = max(.3, min(3., self.zoom*(1.1 if e.delta > 0 else 1/1.1)))
        self.draw()

    def reset(self):
        self.yaw, self.pitch, self.zoom = -.65, .65, 1.
        self.draw()

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        for x in range(0, w, 32):
            for y in range(0, h, 32):
                self.create_oval(x, y, x+1, y+1, fill='#bfced8', outline='')
        if self.mesh is None:
            self.create_text(w/2, h/2, text='正在准备模型预览…', fill=MUTED)
            return
        import numpy as np
        vertices = self.mesh.vertices-self.mesh.bounds.mean(axis=0)
        cy, sy, cp, sp = math.cos(self.yaw), math.sin(self.yaw), math.cos(self.pitch), math.sin(self.pitch)
        rotation = np.array([[cy,-sy,0], [sy*sp,cy*sp,-cp], [sy*cp,cy*cp,sp]])
        points = vertices @ rotation.T
        scale = min(w, h)*.66/max(float(np.linalg.norm(self.mesh.extents)), .01)*self.zoom
        faces = self.mesh.faces
        normals = self.mesh.face_normals @ rotation.T
        for index in np.argsort(points[faces, 2].mean(axis=1)):
            if normals[index, 2] <= 0: continue
            face = points[faces[index], :2]*scale+[w/2,h/2]
            shade = .55+.45*abs(float(normals[index] @ np.array([.3,-.5,.812])))
            color = '#%02x%02x%02x' % (int(30*shade),int(168*shade),int(179*shade))
            self.create_polygon(*face.flatten().tolist(), fill=color, outline=color)
        self.create_text(20, h-22, anchor='w', text='拖动旋转   ·   滚轮缩放', fill=MUTED, font=('Microsoft YaHei UI', 10))


class App:
    def __init__(self, root, generator, state_path=None):
        self.root, self.g = root, generator
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.revision = 0
        self.preview_revision = -1
        self.last = None
        self.closed = False
        self.state_path = Path(state_path) if state_path else Path(os.environ.get('LOCALAPPDATA', Path.home()))/'CoverGenerator'/'settings.json'
        try:
            self.saved = json.loads(self.state_path.read_text(encoding='utf-8'))
            if not isinstance(self.saved, dict): self.saved = {}
        except (OSError, ValueError): self.saved = {}
        self.types = [
            ('pcb','PCB 夹槽护角',generator.Parameters,'为 PCB 四角提供夹槽与上下垫高。'),
            ('cuboid','三面护角',generator.CuboidParameters,'包覆一个顶点的三个相邻面，其余方向敞开。'),
            ('ucover','U 形盖板',generator.UCoverParameters,'两端开口，内宽与内高不自动添加间隙。'),
            ('closedcover','四周封闭盖板',generator.ClosedCoverParameters,'四面侧壁，仅套入面开口；长度和宽度均为内尺寸。'),
            ('circle','圆形板',generator.CirclePlateParameters,'实心圆板，支持上下边缘倒角。'),
            ('rectangle','矩形板',generator.RectPlateParameters,'实心平板，支持四角圆角和上下边缘倒角。'),
            ('square','方形板',generator.SquarePlateParameters,'实心平板，支持四角圆角和上下边缘倒角。'),
            ('roundcover','圆形封闭盖板',generator.RoundCoverParameters,'圆形顶板与一圈侧壁，仅套入面开口；内径和内高不自动添加间隙。'),
        ]
        self.values = {}
        saved_parameters = self.saved.get('parameters', {})
        if not isinstance(saved_parameters, dict): saved_parameters = {}
        for key, _, cls, _ in self.types:
            previous = saved_parameters.get(key, {})
            if not isinstance(previous, dict): previous = {}
            self.values[key] = {name: tk.StringVar(value=str(previous.get(name, value))) for name, value in asdict(cls()).items()}
        root.title(f'护角、盖板与平板生成器 · v{VERSION}')
        root.geometry('1280x850'); root.minsize(1120,800); root.configure(bg=BG)
        style = ttk.Style(root); style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI',10), background=PANEL, foreground=INK)
        style.configure('TEntry', padding=7, fieldbackground='#f5f8fb', bordercolor='#dce4ec')
        style.configure('TButton', padding=(12,8), borderwidth=0, background='#e9f0f5')
        style.map('TButton', background=[('active','#d7e6ed')])
        style.configure('Primary.TButton', background=ACCENT, foreground='white')
        style.map('Primary.TButton', background=[('disabled','#9ab5bd'),('active','#096975')])
        sidebar = tk.Frame(root,bg=INK,width=210); sidebar.pack(side='left',fill='y'); sidebar.pack_propagate(False)
        tk.Label(sidebar,text='COVER / 3D',bg=INK,fg='white',font=('Segoe UI',19,'bold')).pack(anchor='w',padx=22,pady=(30,4))
        tk.Label(sidebar,text='参数化模型工作台',bg=INK,fg='#a8becf').pack(anchor='w',padx=22,pady=(0,30))
        tk.Label(sidebar,text=f'模型库 / {len(self.types):02}',bg=INK,fg='#829db3',font=('Microsoft YaHei UI',9)).pack(anchor='w',padx=22,pady=(0,12))
        self.nav = []
        for index, (_, title, _, _) in enumerate(self.types):
            button = tk.Button(sidebar,text=f'{index+1:02}   {title}',anchor='w',bg=INK,fg='#c9d8e4',activebackground='#285069',activeforeground='white',relief='flat',bd=0,padx=20,pady=12,font=('Microsoft YaHei UI',10),command=lambda i=index:self.select(i))
            button.pack(fill='x',padx=10,pady=2); self.nav.append(button)
        tk.Label(sidebar,text=f'本地生成 · 离线可用\nv{VERSION}',bg=INK,fg='#829db3',justify='left').pack(side='bottom',anchor='w',padx=22,pady=24)
        tk.Button(sidebar,text='版本更新  ↗',command=self.show_history,bg='#284359',fg='white',relief='flat',pady=12).pack(side='bottom',fill='x',padx=16)
        self.main = tk.Frame(root,bg=BG); self.main.pack(fill='both',expand=True,padx=26,pady=24)
        self.workspace = tk.Frame(self.main,bg=BG)
        self.history = tk.Frame(self.main,bg=BG)
        self.title = tk.Label(self.workspace,bg=BG,fg=INK,font=('Microsoft YaHei UI',24,'bold'),anchor='w'); self.title.pack(fill='x')
        self.subtitle = tk.Label(self.workspace,bg=BG,fg=MUTED,anchor='w'); self.subtitle.pack(fill='x',pady=(8,20))
        body = tk.Frame(self.workspace,bg=BG); body.pack(fill='both',expand=True)
        form_box = tk.Frame(body,bg=PANEL,width=350); form_box.pack(side='left',fill='y'); form_box.pack_propagate(False)
        self.form_canvas = tk.Canvas(form_box,bg=PANEL,highlightthickness=0)
        form_scroll = ttk.Scrollbar(form_box,orient='vertical',command=self.form_canvas.yview)
        form_scroll.pack(side='right',fill='y'); self.form_canvas.pack(fill='both',expand=True)
        self.form_canvas.configure(yscrollcommand=form_scroll.set)
        self.form = tk.Frame(self.form_canvas,bg=PANEL,padx=18,pady=18)
        form_window = self.form_canvas.create_window((0,0),window=self.form,anchor='nw')
        self.form.bind('<Configure>',lambda e:self.form_canvas.configure(scrollregion=self.form_canvas.bbox('all')))
        self.form_canvas.bind('<Configure>',lambda e:self.form_canvas.itemconfigure(form_window,width=e.width))
        self.form_canvas.bind('<MouseWheel>',self.scroll_form)
        preview = tk.Frame(body,bg=PANEL); preview.pack(side='left',fill='both',expand=True,padx=(18,0))
        bar = tk.Frame(preview,bg=PANEL); bar.pack(fill='x',padx=16,pady=12)
        tk.Label(bar,text='模型预览',bg=PANEL,fg=INK,font=('Microsoft YaHei UI',12,'bold')).pack(side='left')
        self.view = MeshView(preview)
        ttk.Button(bar,text='重置视角',command=self.view.reset).pack(side='right')
        self.view.pack(fill='both',expand=True)
        self.dimensions = tk.StringVar(value='')
        tk.Label(preview,textvariable=self.dimensions,bg=PANEL,fg=INK,pady=14).pack(fill='x')
        self.validation = tk.StringVar()
        tk.Label(self.workspace,textvariable=self.validation,bg=BG,fg='#b54732',anchor='w',wraplength=880).pack(fill='x',pady=(10,4))
        export = tk.Frame(self.workspace,bg=PANEL,padx=16,pady=14); export.pack(fill='x')
        tk.Label(export,text='导出位置',bg=PANEL,fg=MUTED).pack(side='left',padx=(0,12))
        self.destination = tk.StringVar(value=str(self.saved.get('destination',Path.home()/'Documents'/'生成的模型')))
        ttk.Entry(export,textvariable=self.destination).pack(side='left',fill='x',expand=True)
        ttk.Button(export,text='选择目录',command=self.browse).pack(side='left',padx=8)
        self.generate_button = ttk.Button(export,text='生成模型',style='Primary.TButton',command=self.generate); self.generate_button.pack(side='left')
        footer = tk.Frame(self.workspace,bg=BG); footer.pack(fill='x',pady=(12,0))
        self.status = tk.StringVar(value='每次生成保留独立文件夹 · STL / SCAD / HTML / 参数记录')
        tk.Label(footer,textvariable=self.status,bg=BG,fg=MUTED,anchor='w',wraplength=540,justify='left').pack(side='left')
        self.folder_button = ttk.Button(footer,text='打开文件夹',state='disabled',command=lambda:os.startfile(self.last)); self.folder_button.pack(side='right')
        self.html_button = ttk.Button(footer,text='打开 3D 预览',state='disabled',command=lambda:webbrowser.open((self.last/'preview.html').as_uri())); self.html_button.pack(side='right',padx=8)
        self.build_history()
        for fields in self.values.values():
            for var in fields.values(): var.trace_add('write',self.changed)
        self.select(0)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(100,self.poll)

    def select(self, index):
        self.index = index
        self.history.pack_forget(); self.workspace.pack(fill='both',expand=True)
        for i, button in enumerate(self.nav): button.configure(bg='#285069' if i==index else INK,fg='white' if i==index else '#c9d8e4')
        key,title,cls,description = self.types[index]
        self.title.config(text=title); self.subtitle.config(text=description)
        for child in self.form.winfo_children(): child.destroy()
        tk.Label(self.form,text='尺寸参数',bg=PANEL,fg=INK,font=('Microsoft YaHei UI',13,'bold')).pack(anchor='w',pady=(0,12))
        for name,var in self.values[key].items():
            label,hint = LABELS[name]
            if key in ('rectangle','square') and name in ('length','width'):
                label,hint = ('长度 L' if name=='length' else '宽度 W'),'成品最大外尺寸'
            if key=='roundcover':
                label,hint = {
                    'diameter': ('内径 D','直壁段净直径，请自行预留间隙'),
                    'height': ('内高 H','内腔中央平面至开口的净高度'),
                    'base': ('顶板厚度 T','封闭顶板中央的厚度'),
                    'wall': ('侧壁厚度 S','直壁段的径向厚度'),
                }.get(name,(label,hint))
            if key=='closedcover' and name=='length': label,hint='内长','相对端墙内表面净距'
            row=tk.Frame(self.form,bg=PANEL); row.pack(fill='x',pady=(0,2))
            tk.Label(row,text=label,bg=PANEL,fg=INK).pack(side='left')
            tk.Label(row,text='mm',bg=PANEL,fg=MUTED).pack(side='right')
            ttk.Entry(row,textvariable=var,width=10,justify='right').pack(side='right',padx=6)
            tk.Label(self.form,text=hint,bg=PANEL,fg=MUTED,font=('Microsoft YaHei UI',9)).pack(anchor='w',pady=(0,12))
        ttk.Button(self.form,text='恢复此类型默认参数',command=self.defaults).pack(anchor='w',pady=(8,0))
        self.form_canvas.yview_moveto(0)
        def bind_scroll(parent):
            for widget in parent.winfo_children():
                widget.bind('<MouseWheel>',self.scroll_form)
                if isinstance(widget,ttk.Entry): widget.bind('<FocusIn>',self.reveal_field)
                bind_scroll(widget)
        bind_scroll(self.form)
        self.changed()

    def scroll_form(self,event):
        if self.form.winfo_reqheight()>self.form_canvas.winfo_height():
            self.form_canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
        return 'break'

    def reveal_field(self,event):
        self.root.update_idletasks()
        widget=event.widget
        y=widget.winfo_rooty()-self.form.winfo_rooty()
        top=self.form_canvas.canvasy(0)
        height=self.form_canvas.winfo_height()
        total=max(self.form.winfo_height(),1)
        if y<top: self.form_canvas.yview_moveto(max(0,y-8)/total)
        elif y+widget.winfo_height()>top+height:
            self.form_canvas.yview_moveto((y+widget.winfo_height()-height+8)/total)

    def current(self):
        key,_,cls,_ = self.types[self.index]
        try: p=cls(**{k:float(v.get()) for k,v in self.values[key].items()})
        except ValueError: raise ValueError('请将所有参数填写为有效数字。') from None
        p.validate(); return p

    def changed(self,*_):
        self.revision += 1
        try:
            self.current(); self.validation.set('')
        except ValueError as exc:
            self.validation.set(str(exc)); self.view.mesh=None; self.view.delete('all')
            self.dimensions.set('参数无效 · 预览暂停')
        else:
            self.dimensions.set('参数已改变 · 等待更新预览')
        self.generate_button.config(state='disabled' if self.validation.get() or self.future else 'normal')

    def defaults(self):
        key,_,cls,_=self.types[self.index]
        for name,value in asdict(cls()).items(): self.values[key][name].set(str(value))

    def browse(self):
        folder=filedialog.askdirectory(title='选择模型输出目录')
        if folder: self.destination.set(folder)

    def make_mesh(self,p):
        if isinstance(p,self.g.PLATES): return self.g.build_plate(p)
        if isinstance(p,self.g.UCoverParameters): return self.g.build_ucover(p)
        return self.g.build(p)

    def generate(self):
        if self.future: return
        try:
            p=self.current()
            if not self.destination.get().strip(): raise ValueError('请选择输出目录。')
            path=Path(self.destination.get()).expanduser().resolve()/(self.types[self.index][0]+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        except (ValueError,OSError) as exc: self.validation.set(str(exc)); return
        self.status.set('正在生成并校验 STL，请稍候…')
        self.job=('export',self.revision,path)
        self.future=self.pool.submit(self.g.generate,p,path)
        self.generate_button.config(state='disabled')
        self.save()

    def poll(self):
        if self.closed: return
        if self.future and self.future.done():
            mode,revision,path=self.job
            try:
                result=self.future.result()
                if mode=='export':
                    self.last=path; self.status.set('生成成功 · 已校验封闭性与尺寸')
                    self.folder_button.config(state='normal'); self.html_button.config(state='normal')
                elif revision==self.revision:
                    self.view.mesh=result; self.view.draw()
                    self.dimensions.set('单件外形  '+' × '.join(f'{n:g}' for n in result.extents)+' mm')
            except Exception as exc:
                if mode=='export' or revision==self.revision:
                    self.status.set(f'未完成：{exc}')
                    if mode=='preview': self.view.mesh=None; self.view.delete('all'); self.dimensions.set('预览不可用，请检查参数或运行依赖')
            self.future=None
            self.generate_button.config(state='disabled' if self.validation.get() else 'normal')
        if self.future is None and self.preview_revision!=self.revision and not self.validation.get():
            self.preview_revision=self.revision
            self.job=('preview',self.revision,None)
            self.future=self.pool.submit(self.make_mesh,self.current())
            self.generate_button.config(state='disabled')
        self.root.after(120,self.poll)

    def build_history(self):
        tk.Label(self.history,text='版本更新',bg=BG,fg=INK,font=('Microsoft YaHei UI',24,'bold')).pack(anchor='w')
        tk.Label(self.history,text=f'当前版本 v{VERSION}  ·  历史记录根据仓库 README 与提交记录整理',bg=BG,fg=MUTED).pack(anchor='w',pady=(8,22))
        frame=tk.Frame(self.history,bg=PANEL); frame.pack(fill='both',expand=True)
        scroll=ttk.Scrollbar(frame); scroll.pack(side='right',fill='y')
        text=tk.Text(frame,wrap='word',bg=PANEL,fg=INK,relief='flat',padx=28,pady=22,font=('Microsoft YaHei UI',11),yscrollcommand=scroll.set)
        text.pack(fill='both',expand=True); scroll.config(command=text.yview)
        text.tag_configure('version',font=('Microsoft YaHei UI',16,'bold'),foreground=ACCENT,spacing1=12,spacing3=10)
        text.tag_configure('body',spacing3=10,lmargin1=6,lmargin2=22)
        for version,title,notes in HISTORY:
            text.insert('end',f'v{version}   {title}\n','version')
            for note in notes: text.insert('end',f'•  {note}\n','body')
            text.insert('end','\n')
        text.config(state='disabled')
        ttk.Button(self.history,text='返回模型工作台',command=lambda:self.select(self.index)).pack(anchor='w',pady=(16,0))

    def show_history(self):
        self.workspace.pack_forget(); self.history.pack(fill='both',expand=True)
        for button in self.nav: button.configure(bg=INK,fg='#c9d8e4')

    def save(self):
        data={'destination':self.destination.get(),'parameters':{key:{k:v.get() for k,v in fields.items()} for key,fields in self.values.items()}}
        try:
            self.state_path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.state_path.with_suffix('.tmp'); temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); temporary.replace(self.state_path)
        except OSError: pass

    def close(self):
        self.closed=True; self.save(); self.pool.shutdown(wait=False,cancel_futures=True); self.root.destroy()


def launch(generator):
    root=tk.Tk(); App(root,generator); root.mainloop()
