"""Rebuild the evidence figures and offline HTML for the GearPro report demo."""
from pathlib import Path
import base64
import csv
import html
import math
import re
import shutil
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import PercentFormatter
import markdown
import numpy as np

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
SOURCE = ROOT.parent / 'GearPro_综合技术报告_Markdown含配图/GearPro_assets/media'
ASSETS.mkdir(exist_ok=True)
FONT = '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc'
font_manager.fontManager.addfont(FONT)
plt.rcParams.update({
    'font.family': font_manager.FontProperties(fname=FONT).get_name(),
    'font.size': 11, 'axes.unicode_minus': False,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#c6ccd2', 'text.color': '#172b3a',
    'axes.labelcolor': '#304450', 'xtick.color': '#52616b',
    'ytick.color': '#52616b', 'figure.facecolor': '#ffffff',
    'savefig.facecolor': '#ffffff', 'svg.fonttype': 'none',
})
TEAL, BLUE, AMBER, RED = '#168477', '#3479ac', '#b8792b', '#b8514e'
DATA = []


def datum(figure, label, metric, value, source, numerator='', denominator=''):
    DATA.append(dict(figure=figure, label=label, metric=metric, value=value,
                     numerator=numerator, denominator=denominator, source=source))


def save(fig, name):
    fig.savefig(ASSETS / (name + '.png'), dpi=180, bbox_inches='tight', pad_inches=.18)
    fig.savefig(ASSETS / (name + '.svg'), bbox_inches='tight', pad_inches=.18)
    plt.close(fig)


def box(ax, x, y, w, h, title, sub='', color=TEAL):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.01,rounding_size=0.025',
                              facecolor='#f2f7f8', edgecolor=color, linewidth=1.2))
    ax.text(x+w/2, y+h*.65 if sub else y+h/2, title,
            ha='center', va='center', fontsize=12, fontweight='bold', color=color)
    if sub:
        ax.text(x+w/2, y+h*.30, sub, ha='center', va='center', fontsize=9, color='#425864', linespacing=1.6)


def arrow(ax, a, b, color='#83929b'):
    ax.annotate('', xy=b, xytext=a, arrowprops=dict(arrowstyle='->', color=color, lw=1.5))


def wilson(k, n):
    z=1.96; p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return c-h,c+h


# Figure 1: structural diagram; no fabricated measurements.
fig, ax=plt.subplots(figsize=(12.3,6.1))
ax.set(xlim=(0,1),ylim=(0,1)); ax.axis('off')
ax.text(0, .97, '从图像到分拣：每一次判定保持同一份结果', fontsize=18, weight='bold')
nodes=[(.015,'输送与采集','相机原帧'),(.255,'Model1定位','齿轮框 → 外扩4% ROI'),(.495,'两专项识别','分别校准、融合、阈值'),(.735,'OR与结果输出','Web · 统计 · 串口 · 分拣')]
for x,t,s in nodes: box(ax,x,.69,.225,.17,t,s)
for x,_,_ in nodes[:-1]: arrow(ax,(x+.225,.775),(x+.24,.775))
box(ax,.055,.27,.345,.27,'Scratch V5','EfficientNet / ResNet18 / YOLO-P2\n0.125 / 0.125 / 0.750\n阈值约 0.3003',TEAL)
box(ax,.435,.27,.345,.27,'Missing Hole V1','EfficientNet / ResNet18 / YOLO-standard\n0.250 / 0.250 / 0.500\n阈值约 0.3413',BLUE)
box(ax,.82,.30,.16,.20,'联合判废','任一专项命中\n即 REJECT',AMBER)
arrow(ax,(.40,.405),(.82,.405)); arrow(ax,(.78,.405),(.82,.405))
ax.text(.015,.095,'框级定位：辅助复核　　图像级决定：融合分数　　工件级验收：实际处理与分拣',fontsize=11)
ax.text(.015,.035,'依据综合报告 §2、§13 重绘。Jetson专项性能与逐工件验收仍待测量。',fontsize=9,color='#6a7881')
save(fig,'fig01_architecture')

# Figure 2: changes in research questions, not a cross-version accuracy curve.
fig,ax=plt.subplots(figsize=(12.3,5.3));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
ax.text(0,.96,'研究方向的变化由失败证据推动',fontsize=18,weight='bold')
stages=[('V3','判废与定位能否分开？','三分类 + 独立定位\n增强 / P2 / 异常距离','划痕泛化弱\n视角造成缺口差异'),
        ('V4','任意缺陷二分类是否更稳？','20个正式模型\n470个融合配置','集成补检伴随误报\n划痕瓶颈仍存在'),
        ('V5 + V1','两种缺陷怎样分别适配？','专项数据与结构\n标签矩阵 / 校准融合','不同任务选择不同头\n测试召回仍不足'),
        ('联合对照','能否用统一模型替代？','固定专项阈值后OR\n同150张测试图对照','保留当前双专项\n联合误报仍超目标')]
for i,(t,q,m,e) in enumerate(stages):
    x=.01+i*.25
    box(ax,x,.43,.23,.37,t,q+'\n'+m,TEAL if i<2 else BLUE)
    ax.text(x+.115,.29,e,ha='center',va='center',fontsize=11,linespacing=1.7)
    if i<3: arrow(ax,(x+.23,.62),(x+.25,.62))
ax.text(.01,.07,'不同阶段的标签、数据与测试条件改变；本图表达研究认识，不用于计算跨版本性能提升。',fontsize=10,color='#6a7881')
save(fig,'fig02_research_path')

# Figure 3: common-test system comparison with Wilson intervals.
fig,axs=plt.subplots(1,2,figsize=(11.5,4.6),layout='constrained')
systems=[('双专项 OR',63,71,18,79),('统一 EfficientNet-B0',54,71,33,79)]
for j,(metric,idx,denidx,target,title) in enumerate([
    ('Recall',1,2,.95,'缺陷检出率 / Recall（越高越好）'),
    ('FPR',3,4,.20,'正常误剔率 / FPR（越低越好）')]):
    ax=axs[j]
    for i,row in enumerate(systems):
        k,n=row[idx],row[denidx]; p=k/n; lo,hi=wilson(k,n)
        ax.errorbar(p,i,xerr=[[p-lo],[hi-p]],fmt='o',color=TEAL if i==0 else BLUE,capsize=5,markersize=9,lw=2)
        ax.text(p,i-.15,f'{p:.1%}  ({k}/{n})',ha='center',fontsize=10)
        datum('03',row[0],metric,p,'P §10—11',k,n)
        datum('03',row[0],metric+'_wilson95_low',lo,'由计数推导',k,n)
        datum('03',row[0],metric+'_wilson95_high',hi,'由计数推导',k,n)
    ax.axvline(target,color=AMBER,ls='--',lw=1.4,label=f'阶段目标 {target:.0%}')
    ax.set(yticks=[0,1],yticklabels=[s[0] for s in systems],xlim=(.0,1),ylim=(1.55,-.55),title=title)
    ax.xaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='x',alpha=.15);ax.legend(loc='lower right',fontsize=9)
fig.suptitle('同一测试集：71张任意缺陷图 + 79张完全正常图',fontsize=15,weight='bold')
save(fig,'fig03_system_comparison')

# Figure 4: reported pilot values, rounded in the source.
labels=['三类 · 保留 difficult','三类 · 排除 difficult','两类 · 保留 difficult',
        '两类 · 排除 difficult','单类 · 保留 difficult','单类 · 排除 difficult']
rec=np.array([[.912,.941],[.912,.912],[.912,.941],[.941,.882],[.971,.882],[.971,.971]])
fpr=np.array([[.123,.108],[.092,.154],[.108,.108],[.077,.092],[.185,.123],[.092,.200]])
fig,axs=plt.subplots(1,2,figsize=(11.6,5.9),layout='constrained')
for ax,vals,metric,cmap,vmin,vmax,title in [
    (axs[0],rec,'Recall','GnBu',.85,1,'验证召回率'),
    (axs[1],fpr,'FPR','YlOrBr',0,.22,'验证误报率')]:
    im=ax.imshow(vals,cmap=cmap,vmin=vmin,vmax=vmax,aspect='auto')
    for r in range(6):
        for c in range(2):
            dark=(vals[r,c]>.95) if metric=='Recall' else (vals[r,c]>.17)
            ax.text(c,r,f'{vals[r,c]:.3f}',ha='center',va='center',color='white' if dark else '#173142',weight='bold')
            datum('04',labels[r]+' / '+['standard','P2'][c],metric,float(vals[r,c]),f'P §9.5 E{r*2+c+1:02d}（源表三位小数）')
    ax.set(xticks=[0,1],xticklabels=['Standard','P2'],yticks=range(6),yticklabels=labels,title=title)
    ax.tick_params(length=0);fig.colorbar(im,ax=ax,shrink=.7,pad=.03)
fig.suptitle('缺口检测先导：3种标签 × 2种困难标注策略 × 2种结构',fontsize=15,weight='bold')
save(fig,'fig04_factorial_matrix')

# Figure 5: coefficients only, not measured contribution.
fig,ax=plt.subplots(figsize=(11.5,3.6),layout='constrained')
for y,label,weights in [(1,'Scratch V5',[.125,.125,.75]),(0,'Missing Hole V1',[.25,.25,.5])]:
    left=0
    for name,w,col in zip(['EfficientNet','ResNet18','YOLO检测分支'],weights,[TEAL,BLUE,AMBER]):
        ax.barh(y,w,left=left,height=.43,color=col)
        ax.text(left+w/2,y,f'{name}\n{w:.1%}',ha='center',va='center',color='white',fontsize=10)
        datum('05',label,name+'_coefficient',w,'P §8.5 / §9.6')
        left+=w
ax.set(xlim=(0,1),yticks=[0,1],yticklabels=['缺口 V1','划痕 V5'],title='验证搜索得到的线性分数系数')
ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('两个分类器先取均值，再与检测分支融合；系数不代表正确识别贡献率')
save(fig,'fig05_fusion_weights')

# Figure 6: within-task validation and test points, exact count ratios.
fig,axs=plt.subplots(1,2,figsize=(11.6,4.4),layout='constrained')
task_data=[('划痕 V5',[(42,43),(25,31)],[(9,107),(20,119)],TEAL),
           ('缺口 V1',[(34,34),(36,44)],[(4,65),(4,106)],BLUE)]
for ax,metric,target,j in [(axs[0],'Recall',.95,1),(axs[1],'FPR',.20,2)]:
    for row in task_data:
        label,pairs,col=row[0],row[j],row[3]
        vals=[k/n for k,n in pairs]
        ax.plot([0,1],vals,'o-',color=col,lw=2,ms=7,label=label)
        for x,(k,n) in enumerate(pairs):
            ax.annotate(f'{k/n:.2%}',(x,k/n),xytext=(6,9 if label=='划痕 V5' else -19),textcoords='offset points',fontsize=10)
            datum('06',label+' / '+['validation','test'][x],metric,k/n,'P §11.1',k,n)
    ax.axhline(target,color=AMBER,ls='--',lw=1.3)
    ax.set(xticks=[0,1],xticklabels=['参与选择的验证集','冻结后的测试集'],xlim=(-.12,1.33),title=metric+'：两专项分别统计')
    ax.set_ylim((.7,1.06) if metric=='Recall' else (0,.26))
    ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='y',alpha=.15);ax.legend(loc='lower left' if metric=='Recall' else 'upper left',fontsize=9)
save(fig,'fig06_validation_test')

# Figure 7: overlapping positional groups.
fig,ax=plt.subplots(figsize=(11.4,3.6),layout='constrained')
for i,(label,k,n) in enumerate([('bottom',11,12),('oblique',10,17),('side',20,20)]):
    p=k/n;lo,hi=wilson(k,n)
    ax.errorbar(p,i,xerr=[[p-lo],[hi-p]],fmt='o',color=RED if i==1 else TEAL,ms=9,lw=2,capsize=5)
    ax.text(p,i-.15,f'{k}/{n} = {p:.1%}',ha='center',fontsize=10)
    datum('07',label,'Recall',p,'P §9.7',k,n)
    datum('07',label,'wilson95_low',lo,'由计数推导',k,n)
    datum('07',label,'wilson95_high',hi,'由计数推导',k,n)
ax.set(yticks=range(3),yticklabels=['底部 bottom','斜视 oblique','侧部 side'],xlim=(.25,1.04),ylim=(2.6,-.6),title='缺口测试瓶颈集中在斜视位置')
ax.xaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='x',alpha=.15)
ax.set_xlabel('点为观测召回率，线为Wilson 95%区间；位置分组可重叠')
save(fig,'fig07_position_recall')

shutil.copyfile(SOURCE/'image8.jpg',ASSETS/'scratch_fn.jpg')
shutil.copyfile(SOURCE/'image9.jpg',ASSETS/'scratch_fp.jpg')
with (ASSETS/'chart_data.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['figure','label','metric','value','numerator','denominator','source'])
    writer.writeheader();writer.writerows(DATA)

# Offline HTML uses embedded figures and paper links, with print-specific layout.
md=(ROOT/'GearPro_技术报告_Demo.md').read_text(encoding='utf-8')
renderer=markdown.Markdown(extensions=['tables','toc','fenced_code'],extension_configs={'toc':{'toc_depth':'2-3'}})
body=renderer.convert(md)
def embed(match):
    src=match.group(1)
    if src.startswith('assets/'):
        p=ROOT/src;mime='image/jpeg' if p.suffix=='.jpg' else 'image/png'
        return 'src="data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode()+'"'
    return match.group(0)
body=re.sub(r'src="([^"]+)"',embed,body)
body=re.sub(r'(<table>.*?</table>)',r'<div class="table-wrap">\1</div>',body,flags=re.S)
body=re.sub(r'<p><img ([^>]+) /></p>',r'<figure><img \1 /></figure>',body)
body=body.replace('href="../GearPro_综合技术报告_Markdown含配图/GearPro_综合实验与部署技术报告.md"',
                  'href="../GearPro_综合技术报告_Markdown含配图/GearPro_综合实验与部署技术报告.md" data-project-source="true"')
css='''
:root{--ink:#182e3c;--muted:#61717d;--teal:#168477;--line:#d8e1e5;--paper:#fff;--bg:#edf1f2}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif;font-size:15px;line-height:1.9}
.layout{max-width:1360px;margin:auto;display:grid;grid-template-columns:242px minmax(0,1fr);gap:28px;padding:36px 32px 64px}
aside{position:sticky;top:26px;height:calc(100vh - 52px);overflow:auto;padding:8px 8px 20px}
.brand{font-size:23px;font-weight:750;letter-spacing:.07em;margin-bottom:4px}.edition{font-size:11px;letter-spacing:.13em;color:var(--muted);margin-bottom:24px}
aside ul{list-style:none;padding:0;margin:0}aside li{margin:6px 0}aside li ul{padding-left:12px;margin:4px 0 14px}aside a{color:#526771;font-size:12px;line-height:1.55;text-decoration:none;display:block;padding:3px 0}aside a:hover{color:var(--teal)}
article{background:var(--paper);padding:56px 62px;box-shadow:0 8px 36px #21374408;border-top:5px solid var(--teal);min-width:0}
.eyebrow{color:var(--teal);font-size:12px;font-weight:700;letter-spacing:.12em;margin-bottom:16px}
h1{font-size:34px;line-height:1.4;letter-spacing:-.02em;margin:0 0 12px}h2{font-size:23px;line-height:1.5;margin:52px 0 18px;padding-top:18px;border-top:1px solid var(--line);font-weight:700}h1+h2{font-size:20px;color:#4f6572;border:0;padding:0;margin:0 0 25px;font-weight:400}h3{font-size:18px;margin:28px 0 12px}p{margin:12px 0;text-align:justify}a{color:#167a72;text-underline-offset:3px}strong{font-weight:700}
blockquote{margin:26px 0;padding:16px 20px;background:#f3f8f8;border-left:3px solid var(--teal);font-size:13px;color:#526771}blockquote p{margin:0}
.table-wrap{width:100%;overflow:auto;margin:22px 0}table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.65}th{background:#eaf2f3;color:#264a58;text-align:left;font-weight:700}th,td{padding:10px 11px;border-bottom:1px solid #dce5e8;vertical-align:top;min-width:54px}tr:nth-child(even) td{background:#f8fafb}
figure{margin:28px 0 10px;break-inside:avoid}img{max-width:100%;height:auto;display:block}figure+p:has(em:only-child){font-size:12px;line-height:1.7;color:var(--muted);margin-top:10px}
code{font-family:"Noto Sans Mono CJK SC",monospace;background:#f1f5f6;padding:2px 5px;border-radius:3px;overflow-wrap:anywhere;font-size:.9em}
.footer{margin-top:48px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:11px}
@media(max-width:1050px){.layout{grid-template-columns:190px minmax(0,1fr);gap:16px;padding:20px}article{padding:38px 30px}}
@media(max-width:760px){.layout{display:block;padding:12px}aside{position:static;height:auto;max-height:240px;margin-bottom:18px}aside .toc>ul{columns:2}aside li ul{display:none}article{padding:28px 18px}h1{font-size:27px}h2{font-size:20px}body{font-size:14px}}
@media print{@page{size:A4;margin:18mm 16mm}body{background:#fff;font-size:10pt;line-height:1.7}.layout{display:block;padding:0;max-width:none}aside{display:none}article{padding:0;box-shadow:none;border:0}h1{font-size:24pt}h2{font-size:15pt;break-after:avoid;margin-top:24pt}h3{font-size:12pt;break-after:avoid}p{orphans:3;widows:3}.table-wrap{overflow:visible}table{font-size:8pt}th,td{padding:6px}thead{display:table-header-group}tr{break-inside:avoid}figure{break-inside:avoid}a{color:inherit}blockquote{break-inside:avoid}.eyebrow{font-size:8pt}}
'''
page='<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GearPro 技术报告 Demo</title><style>'+css+'</style></head><body><div class="layout"><aside><div class="brand">GEARPRO</div><div class="edition">TECHNICAL REPORT · DEMO</div>'+renderer.toc+'</aside><article><div class="eyebrow">研究方法 / 参数依据 / 实验证据</div>'+body+'<div class="footer">GearPro · 技术报告演示稿 · 2026-10-05<br>图表据项目现有报告重绘；各阶段证据边界见正文。文献链接需要网络，正文及全部图片可离线阅读。</div></article></div></body></html>'
(ROOT/'GearPro_技术报告_Demo.html').write_text(page,encoding='utf-8')

# Checks focus on substantive numerical and artifact consistency.
assert 31+44-4 == 71
assert len(DATA)==67, len(DATA)
assert all(abs(sum(w)-1)<1e-12 for w in [[.125,.125,.75],[.25,.25,.5]])
for image in re.findall(r'!\[[^]]*\]\(([^)]+)\)',md):
    assert (ROOT/image).is_file(), image
for p in ASSETS.glob('*.svg'):
    ET.parse(p)
assert 'src="assets/' not in page
assert not re.search(r'<(?:script|link)[^>]+(?:src|href)="https?://',page)
assert '[wordlim' not in md and 'turn7search' not in md
print('Created Markdown, standalone HTML, 7 PNG/SVG figure pairs, 2 source case images and chart_data.csv.')
print('Chart rows:',len(DATA),'HTML bytes:',len(page.encode()),'Markdown characters:',len(md))
