---
name: pcb-corner-guard
description: 按尺寸生成可打印的 PCB 护角、三面护角、U 形或四周封闭盖板，以及带可选圆角和倒角的圆形、矩形、方形实心板，输出 STL、源文件与三维预览。
---

# PCB 护角、三面护角与 U 形盖板

使用 `scripts/corner_guard.py` 确定性生成模型，不要为每次尺寸修改重新编写几何算法。脚本支持命令行及 `--gui` 本地参数窗口，无需 OpenSCAD 即可输出 STL。

## 类型选择

- PCB、薄板上下夹持：`--type pcb`（兼容旧命令，默认）。
- 正方体、立方体、长方体、箱体三面护角：`--type cuboid`。只有一个顶点相邻的三个垂直面，其余方向敞开，不添加相对面或盖子。
- 两侧开口盖板、U 形盖板：`--type ucover`。一块平板加两条相对侧壁，沿长度方向两端开口，不能误做成三面护角。
- 四周封闭盖板：`--type closedcover`。一块平板加四周侧壁，仅套入面开口，不是六面完全封闭的盒体。
- 用户已指明物体类型时直接选择，无需重复确认。

## 实心平板

- 圆形板：`--type circle --diameter 100 --thickness 3 --bevel 0.5`。
- 矩形板：`--type rectangle --length 120 --width 100 --thickness 3 --radius 5 --bevel 0.5`。
- 方形板：`--type square --side 100 --thickness 3 --radius 5 --bevel 0.5`。

配合 `--out <输出目录>` 使用。尺寸均为最大成品外尺寸，厚度参数为 `--thickness`，不使用盖板的 `--base`。R 和 C 默认均为 0；未指定时不自动添加。

R 是矩形/方形俯视四角圆角半径，最大为短边一半；圆形无 R 参数。C 是上下周边同时施加的 45° 倒角，其水平和竖直退让量均为 C，必须小于板厚及短边/直径的一半。支持 R 与 C 组合、R<C、R 等于短边一半；不静默缩小非法输入。

输出 `plate_single.stl`、`plate_parametric.scad`、预览和参数记录。曲线采用多边形近似；最大支持尺寸下弦高误差约 0.04 mm。平放切片，检查底面倒角的悬空效果。当前没有孔洞选项。

## 四周封闭盖板参数

`--length 120 --width 100 --height 15 --base 3 --wall 3` 分别为内长、内宽、内高、平板厚度、四周侧壁厚度，单位 mm。长度与 U 形盖板的定义不同，这里是两端侧壁内表面的净距离。

外形为 `(length+2*wall) × (width+2*wall) × (height+base)`。不添加装配间隙，不添加孔、卡扣或顶盖。侧壁等高等厚。预览开口朝上，作盖板使用可翻转。

```text
python <skill目录>/scripts/corner_guard.py --type closedcover --length 120 --width 100 --height 15 --base 3 --wall 3 --out <当前任务输出目录>/closedcover
```

输出 `cover_single.stl`、`cover_parametric.scad`、`preview.html`、`parameters.json` 和 `打印说明.txt`。平板外表面朝下打印。

## U 形盖板参数

`--width 100 --length 120 --height 15 --base 3 --wall 3`：内宽、长度、侧壁内高、平板厚度、侧壁厚度，单位 mm。

- 内宽是两侧壁内表面的净距离；侧壁内高从平板内表面量起；不自动增加装配间隙。
- 长度沿侧壁方向，表示两开口间距离。外形为 `length × (width+2*wall) × (height+base)`。
- 两侧壁等高等厚，不包含端墙、盖子、孔或卡扣。不支持直接传入不等高参数；如果用户要求，应先扩展生成器，不能声称当前模型已支持。

```text
python <skill目录>/scripts/corner_guard.py --type ucover --width 100 --length 120 --height 15 --base 3 --wall 3 --out <当前任务输出目录>/ucover
```

输出 `cover_single.stl`、`cover_parametric.scad`、`preview.html`、`parameters.json` 和 `打印说明.txt`。盖板不自动生成护角排版。平板外表面朝下打印；确认打印平台尺寸和物体装配余量。

## 三面护角参数

`--x 20 --y 20 --z 20 --wall 3`：X/Y/Z 是沿物体三条棱的包覆长度，不含壁厚，也不是物体完整长宽高。若用户说“护角边长 20”则三方向均为 20；长方体可分别指定。不要把物体完整尺寸自动填成包覆长度。

不使用内嵌、夹槽、上下垫高参数。三个内壁直接贴近物体表面，无自动配合余量。外形为 `(x+wall) × (y+wall) × (z+wall)`。每条棱两端的护角不能互相重叠。

```text
python <skill目录>/scripts/corner_guard.py --type cuboid --x 20 --y 25 --z 30 --wall 3 --out <当前任务输出目录>/cuboid-corners
```

输出单件 `corner_single.stl`、镜像件 `corner_mirrored.stl` 和八件排版 `corner_eight.stl`，以及源文件、HTML 预览、参数和说明。八件为四个原件和四个镜像件；三方向长度不同时，镜像和旋转可保证八个顶点的轴向包覆长度匹配。技能名称保持不变以兼容旧调用。

## PCB 参数语义

单位为 mm。按用户明确数值生成；未指定的值使用当前对话最近确认的值，否则使用这些默认值并告知：

| 用户参数 | 参数名 | 默认 |
|---|---|---|
| 内嵌深度 | `--overlap` | 2.2 |
| 夹槽净高 | `--slot` | 4.1 |
| 上垫高 | `--top` | 5 |
| 下垫高 | `--bottom` | 5 |
| 护角边长 | `--arm` | 15 |
| 外侧壁厚 | `--wall` | 3 |

- “上下垫高 5”表示上、下分别 5；分别给数值时分别设置。
- 边长是沿 PCB 每条边延伸的长度，不包括外侧壁厚。外形长宽为边长加壁厚；总高为上垫高加夹槽加下垫高。用户明确给的是外形长宽时，转换成对应边长。
- 夹槽为实际建模净高，不再额外增加间隙。若只给 PCB 板厚而没有槽高，说明采用的试配余量，不能把板厚和槽高混为一谈。
- 内嵌是按相邻板边垂直距离计算的 L 形覆盖带；沿每条边的整个接触带均须可接触。
- 原项目 PCB 为 198 × 198 × 4，允许接触边缘带 3 mm。此限制属于原板，不能自动套用到所有新 PCB。用户修改原板内嵌深度超过 3 mm 时先指出冲突并确认可接触范围。
- PCB 长宽不影响单件护角形状，无需为相同结构重复询问长宽。该结构不含主动锁扣、包装定位件或芯片模型。

## 执行

```text
python <skill目录>/scripts/corner_guard.py --overlap 2.2 --slot 4.1 --top 5 --bottom 5 --arm 15 --wall 3 --out <当前任务输出目录>/pcb-corners
```

所有尺寸必须为有限正数，脚本支持 0.2～1000 mm；PCB 模式的边长须大于内嵌深度。输入范围不是打印适用性保证。不静默截断错误参数，不把一个类型的专属参数静默用于另一类型。

依赖列于 `scripts/requirements.txt`。如缺失，在合适的 Python 环境安装；不修改其他项目的依赖文件。
输出放到当前任务允许交付的目录。命令行会更新指定目录中的同名文件；新方案用新的目录以保留旧版，需要修改旧方案时可更新对应目录。

输出包括：`corner_single.stl`、`corner_four.stl`、`corner_parametric.scad`、`preview.html`、`parameters.json`、`打印说明.txt`。
脚本检查封闭性、法线、连通组件、外形尺寸，并回读导出的 STL。检查失败时不得声称模型有效。

## 交付

给出类型、实际参数及对应单件和排版 STL 下载链接；源文件及预览可合并列出。提醒先打印单件试配，不把几何校验说成实物测试。PCB 夹槽上沿有局部悬空，需要切片确认支撑。三面护角底面朝下打印。运输时包装需限制独立护角滑脱。

用户只要方案时不运行生成；用户要求生成或修改时直接执行已明确的参数，无需再次确认常规操作。
