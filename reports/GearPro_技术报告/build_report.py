"""Build offline reading artifacts from existing GearPro experiment records.

This script does not train, infer, tune thresholds or alter experiment inputs.
"""
from pathlib import Path, PureWindowsPath
from collections import Counter
import base64
import csv
import hashlib
import json
import math
import os
import re
import xml.etree.ElementTree as ET
import zipfile

os.environ.setdefault('MPLCONFIGDIR', '/tmp/gearpro-report-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.ticker import PercentFormatter
import markdown
import numpy as np
from PIL import Image
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
ASSETS = ROOT / 'assets'
ASSETS.mkdir(exist_ok=True)
INPUTS = {}
DATA = []
FONT = Path('/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc')
font_manager.fontManager.addfont(str(FONT))
plt.rcParams.update({
    'font.family': font_manager.FontProperties(fname=str(FONT)).get_name(),
    'font.size': 11, 'axes.unicode_minus': False,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#bbcbd1', 'text.color': '#163342',
    'axes.labelcolor': '#365563', 'xtick.color': '#536b77',
    'ytick.color': '#536b77', 'figure.facecolor': 'white',
    'savefig.facecolor': 'white', 'svg.fonttype': 'none',
})
TEAL, BLUE, GOLD, RED = '#2457a7', '#6d9ecf', '#b47928', '#b74c4d'


def read_bytes(path):
    path = REPO / path if not Path(path).is_absolute() else Path(path)
    raw = path.read_bytes()
    INPUTS[str(path.relative_to(REPO))] = hashlib.sha256(raw).hexdigest()
    return raw


def load_json(path):
    return json.loads(read_bytes(path).decode('utf-8-sig'))


def load_csv(path):
    import io
    return list(csv.DictReader(io.StringIO(read_bytes(path).decode('utf-8-sig'))))


def record(figure, label, metric, value, source, k='', n=''):
    DATA.append(dict(figure=figure, label=label, metric=metric, value=value,
                     numerator=k, denominator=n, source=source))


def save(fig, name):
    fig.savefig(ASSETS / f'{name}.png', dpi=180, bbox_inches='tight', pad_inches=.18)
    fig.savefig(ASSETS / f'{name}.svg', bbox_inches='tight', pad_inches=.18)
    plt.close(fig)


def wilson(k, n):
    z = 1.96
    p = k/n
    d = 1+z*z/n
    c = (p+z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return c-h, c+h


def box(ax, x, y, w, h, title, sub='', color=TEAL, pending=False):
    patch=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.008,rounding_size=0.02',
                              facecolor='#f3f6fb',edgecolor=color,lw=1.3,
                              linestyle='--' if pending else '-')
    ax.add_patch(patch)
    ax.text(x+w/2,y+h*(.70 if sub else .5),title,ha='center',va='center',
            fontsize=12,fontweight='bold',color=color)
    if sub:
        ax.text(x+w/2,y+h*.32,sub,ha='center',va='center',fontsize=9,linespacing=1.7)
    return patch


def arrow(ax, a, b, pending=False, patch_a=None, patch_b=None):
    props=dict(arrowstyle='->',color='#879ca5',lw=1.5,
               linestyle='--' if pending else '-')
    if patch_a is not None and patch_b is not None:
        # 按实际圆角矩形边界裁剪连接线，不依赖手填边缘坐标。
        props.update(patchA=patch_a,patchB=patch_b,shrinkA=0,shrinkB=0)
    ax.annotate('',xy=b,xytext=a,arrowprops=props)


def photo(task, stem):
    import io
    image_path = f'dataset_defects/images/test_{task}/{stem}.jpg'
    image = np.asarray(Image.open(io.BytesIO(read_bytes(image_path))).convert('RGB'))
    xml_path = REPO / f'dataset_defects/annotations/test_{task}/{stem}.xml'
    boxes = []
    if xml_path.exists():
        doc = ET.fromstring(read_bytes(xml_path))
        assert int(doc.findtext('size/width')) == image.shape[1]
        assert int(doc.findtext('size/height')) == image.shape[0]
        for obj in doc.findall('object'):
            b = [int(float(obj.findtext('bndbox/'+k))) for k in ['xmin','ymin','xmax','ymax']]
            boxes.append((obj.findtext('name'), b))
    return image, boxes, image_path


def show_photo(ax, image, boxes, region=None):
    ax.imshow(image, interpolation='nearest')
    for _, (x1,y1,x2,y2) in boxes:
        ax.add_patch(Rectangle((x1,y1),x2-x1,y2-y1,fill=False,edgecolor=RED,lw=1.5))
    if region:
        x1,y1,x2,y2=region
        ax.set_xlim(x1,x2); ax.set_ylim(y2,y1)
    ax.axis('off')


def zoom_region(image, boxes):
    h,w=image.shape[:2]
    if boxes:
        b=max(boxes,key=lambda o:(o[1][2]-o[1][0])*(o[1][3]-o[1][1]))[1]
        cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
        side=max(b[2]-b[0],b[3]-b[1])*1.6
        side=max(side,min(h,w)*.22)
        return (max(0,cx-side/2),max(0,cy-side/2),min(w,cx+side/2),min(h,cy+side/2))
    return (.13*w,.13*h,.87*w,.87*h)


sc = load_json('outputs/scratch_v5/inference_config.json')
mh = load_json('outputs/missing_hole_v1/inference_config.json')
st = load_json('outputs/scratch_v5/test_scratch/test_report.json')
mt = load_json('outputs/missing_hole_v1/test/test_report.json')
sl = load_json('outputs/scratch_v5/leaderboard.json')
ml = load_json('outputs/missing_hole_v1/leaderboard.json')
fl = load_json('outputs/missing_hole_v1/fusion_leaderboard.json')
sm = load_csv('dataset_defects/scratch_v5/scratch_manifest.csv')
mm = load_csv('dataset_defects/missing_hole_v1/master_manifest.csv')
predictions = load_csv('outputs/scratch_v5/test_scratch/test_predictions.csv')
prediction_by_stem = {PureWindowsPath(r['image']).stem:r for r in predictions}

# 1: original image and annotation views, not generated model outputs.
assert prediction_by_stem['test_001']['truth'] == 'normal'
assert next(r for r in mm if r['stem']=='test_001' and r['split']=='test')['defect']=='0'
fig,axs=plt.subplots(2,4,figsize=(12.8,6.8),layout='constrained')
samples=[('scratch','test_001','无可见目标缺陷（两类均无）'),('scratch','test_040','划痕 scratch'),
         ('missing_tooth','test_002','齿部缺损 · side标签'),('missing_tooth','test_011','齿部缺损 · oblique标签')]
for i,(task,stem,label) in enumerate(samples):
    img,boxes,source=photo(task,stem)
    show_photo(axs[0,i],img,boxes)
    axs[0,i].set_title(label+'\n'+stem,fontsize=11)
    show_photo(axs[1,i],img,boxes,zoom_region(img,boxes))
    axs[1,i].set_title('局部查看 · 原图像素' if boxes else '中心外观 · 原图像素',fontsize=10)
fig.suptitle('人工标注框：划痕与局部齿部缺损',fontsize=16,weight='bold')
save(fig,'fig01_defect_examples')

# 2: current prototype, software and explicitly pending human review.
fig,ax=plt.subplots(figsize=(12.7,6.0));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
ax.text(.005,.97,'上下双相机、边缘计算与缺陷检测结果',fontsize=18,weight='bold')
top=[(.01,'输送与成像','上下双工业相机'),(.26,'边缘平台','Jetson NX · 简单现场测试'),
     (.51,'软件结果','Web显示 · 统计 · 串口'),(.76,'机构支路','第一代分拣原型')]
top_patches=[box(ax,x,.70,.22,.16,t,sub) for x,t,sub in top]
for i in range(3):
    arrow(ax,(top[i][0]+.11,.78),(top[i+1][0]+.11,.78),patch_a=top_patches[i],patch_b=top_patches[i+1])
roi=box(ax,.01,.32,.18,.21,'齿轮定位 → ROI','裁剪边界扩展4%')
scratch=box(ax,.25,.44,.30,.17,'划痕检测','分类分数 + 检测置信度',TEAL)
missing=box(ax,.25,.18,.30,.17,'齿部缺损检测','分类分数 + 检测置信度',BLUE)
fusion=box(ax,.61,.32,.15,.21,'决策级融合','或规则 · 保留预测类别',GOLD)
review=box(ax,.82,.32,.16,.21,'疑似件复核','流程与记录待设计',GOLD,True)
arrow(ax,(.10,.425),(.40,.525),patch_a=roi,patch_b=scratch)
arrow(ax,(.10,.425),(.40,.265),patch_a=roi,patch_b=missing)
arrow(ax,(.40,.525),(.685,.425),patch_a=scratch,patch_b=fusion)
arrow(ax,(.40,.265),(.685,.425),patch_a=missing,patch_b=fusion)
arrow(ax,(.685,.425),(.90,.425),True,patch_a=fusion,patch_b=review)
ax.text(.01,.055,'实线：原型或既有软件规则　虚线：待设计人工复核　当前NX上没有系统性能记录',fontsize=10,color='#607681')
# 本图使用真实微软雅黑字体文件，并分别指定常规及粗体，避免中文伪粗体。
for artist in ax.texts:
    font_path='/usr/share/fonts/TTF/msyhbd.ttc' if artist.get_fontweight()=='bold' else '/usr/share/fonts/TTF/msyh.ttc'
    artist.set_fontproperties(font_manager.FontProperties(family="Microsoft YaHei",fname=font_path,weight=artist.get_fontweight(),size=artist.get_fontsize()))
save(fig,'fig02_system_route')

# 3: entities and image counts are separate units.
fig,axs=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
labels=['正常','划痕','侧部缺损','齿角缺损'];counts=[10,15,15,10]
axs[0].barh(labels,counts,color=[TEAL,BLUE,GOLD,RED],height=.55)
for i,(label,n) in enumerate(zip(labels,counts)):
    axs[0].text(n+.3,i,f'{n}个',va='center');record('03',label,'physical_gears',n,'项目负责人确认')
axs[0].set(xlim=(0,18),title='齿轮工件：50个',xlabel='不同工件数量（负责人确认）')
axs[0].invert_yaxis();axs[0].grid(axis='x',alpha=.12)
split_counts=[Counter(r['split'] for r in sm),Counter(r['split'] for r in mm)]
split_counts[0]['test']=st['counts']['images']
for y,(label,counts) in enumerate(zip(['Scratch V5','Missing Hole V1'],split_counts)):
    left=0
    for split,col,name in [('train',TEAL,'训练'),('val',BLUE,'验证'),('test',GOLD,'测试')]:
        n=counts[split];axs[1].barh(y,n,left=left,color=col,height=.5)
        axs[1].text(left+n/2,y,f'{name}\n{n}张',ha='center',va='center',color='white',fontsize=10)
        record('03',label+'/'+split,'images',n,'划痕与齿部缺损数据清单；划痕测试数量来自划痕测试记录')
        left+=n
axs[1].set(yticks=[0,1],yticklabels=['划痕（V5）','齿部缺损（V1）'],title='图像样本：同工件多角度观察',xlabel='图像数量；同一齿轮可拍摄多张图像',xlim=(0,690))
save(fig,'fig03_dataset_units')

# 4: rationale timeline.
fig,ax=plt.subplots(figsize=(12.5,5.3));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
ax.text(.005,.97,'从早期发现到最终配置：问题推动方案收敛',fontsize=18,weight='bold')
stages=[('V3','图像分类与目标定位','三分类 / 定位 / 异常距离','划痕测试召回率低\n缺损检测受视角影响'),
        ('V4','统一缺陷分类','二分类 / 多骨干 / 集成','补检伴随误报\n划痕瓶颈未解除'),
        ('V5 + V1','按缺陷类别分别建模','结构 / 标签 / 融合搜索','不同缺陷采用不同配置\n漏检仍需改善'),
        ('当前系统','决策级融合（或规则）','同150张图像对照','保留基准系统\n辅助人工复核')]
for i,(t,q,m,e) in enumerate(stages):
    x=.01+i*.25;box(ax,x,.43,.23,.36,t,q+'\n'+m,TEAL if i<2 else BLUE)
    ax.text(x+.115,.28,e,ha='center',va='center',fontsize=11,linespacing=1.6)
    if i<3:arrow(ax,(x+.23,.61),(x+.25,.61))
ax.text(.01,.065,'各阶段的数据和任务条件变化；此图表达研究认识，不表示可直接比较的性能曲线。',fontsize=10,color='#607681')
save(fig,'fig04_research_path')

# 5: actual V5 pilot operating points; annotate configuration confounding.
pilots=[r for r in sl if r['stage']=='pilot']
fig,axs=plt.subplots(1,2,figsize=(12.4,4.7),layout='constrained')
for ax,kind,title in [(axs[0],'classifier','初步分类实验：输入与损失权重'),(axs[1],'detector','初步目标检测实验：960输入')]:
    subset=[r for r in pilots if r['kind']==kind]
    for i,row in enumerate(subset):
        op=row['operating_points']['0.2']
        label=(row.get('family','')+' '+str(row.get('size',''))+' / w'+str(int(row.get('defect_weight',1)))) if kind=='classifier' else ('含P2检测层' if 'p2' in row['name'] else '原始YOLO26n')
        color=[TEAL,BLUE,GOLD][i//2] if kind=='classifier' else [BLUE,TEAL][i]
        marker='o' if i%2==0 else 's'
        ax.scatter(op['fpr'],op['recall'],s=70,color=color,marker=marker,label=label)
        record('05',row['name'],'Recall',op['recall'],'划痕候选模型评价表',op['tp'],op['tp']+op['fn'])
        record('05',row['name'],'FPR',op['fpr'],'划痕候选模型评价表',op['fp'],op['fp']+op['tn'])
        record('05',row['name'],'AUPRC',row['auprc'],'划痕候选模型评价表')
        if kind=='detector':ax.annotate(label+'\n'+f"AUPRC {row['auprc']:.3f}",(op['fpr'],op['recall']),xytext=(-4,12 if i==1 else -32),textcoords='offset points',ha='center',fontsize=10)
    ax.set(xlim=(.09,.225),ylim=(.65,1.0),xlabel='验证集误报率（FPR）',ylabel='验证集召回率（Recall）',title=title)
    ax.xaxis.set_major_formatter(PercentFormatter(1));ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(alpha=.12)
    if kind=='classifier':ax.legend(fontsize=8,loc='lower left')
save(fig,'fig05_scratch_candidates')

# 6: exact 12-factorial records.
fig,axs=plt.subplots(1,2,figsize=(12.3,5.9),layout='constrained')
rows=[(scheme,policy) for scheme in ['three_class','two_class','one_class'] for policy in ['include_difficult','exclude_difficult']]
labels=[{'three_class':'三类','two_class':'两类','one_class':'单类'}[s]+' · '+('保留' if p.startswith('include') else '排除')+'困难目标' for s,p in rows]
for ax,metric,cmap,vmin,vmax,title in [(axs[0],'recall','Blues',.85,1,'验证集召回率'),(axs[1],'fpr','YlOrBr',0,.22,'验证集误报率')]:
    vals=np.empty((6,2))
    for i,(scheme,policy) in enumerate(rows):
        for j,arch in enumerate(['standard','p2']):
            row=next(r for r in ml if r['name']==f'p_det_{scheme}_{policy}_{arch}_960')
            op=row['primary'];vals[i,j]=op[metric]
            k,n=(op['tp'],op['tp']+op['fn']) if metric=='recall' else (op['fp'],op['fp']+op['tn'])
            record('06',row['name'],metric.upper(),op[metric],'齿部缺损候选模型评价表',k,n)
    im=ax.imshow(vals,cmap=cmap,vmin=vmin,vmax=vmax,aspect='auto')
    for i in range(6):
        for j in range(2):
            dark=vals[i,j]>.95 if metric=='recall' else vals[i,j]>.17
            ax.text(j,i,f'{vals[i,j]:.3f}',ha='center',va='center',weight='bold',color='white' if dark else '#163342')
    ax.set(xticks=[0,1],xticklabels=['原始YOLO26n','含P2检测层'],yticks=range(6),yticklabels=labels,title=title)
    ax.tick_params(length=0);fig.colorbar(im,ax=ax,shrink=.7,pad=.03)
fig.suptitle('齿部缺损初步实验：类别划分、困难目标处理与检测结构',fontsize=16,weight='bold')
save(fig,'fig06_missing_matrix')

# 7: coefficients expanded directly from production configurations.
fig,ax=plt.subplots(figsize=(11.8,3.7),layout='constrained')
for y,label,config in [(1,'划痕（V5）',sc),(0,'齿部缺损（V1）',mh)]:
    alpha=config['fusion']['alpha'];weights=[alpha/2,alpha/2,1-alpha];left=0
    for name,w,col in zip(['EfficientNet','ResNet18','检测模型'],weights,[TEAL,BLUE,GOLD]):
        ax.barh(y,w,left=left,height=.45,color=col)
        ax.text(left+w/2,y,f'{name}\n{w:.1%}',ha='center',va='center',color='white',fontsize=10)
        record('07',label,name+'_coefficient',w,'划痕与齿部缺损发布配置');left+=w
    assert abs(sum(weights)-1)<1e-12
ax.set(yticks=[0,1],yticklabels=['齿部缺损（V1）','划痕（V5）'],xlim=(0,1),title='分数级加权融合：分类平均分数 × α + 检测分数 × (1−α)')
ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('验证集选择：划痕 α=0.25；齿部缺损 α=0.50。系数为分数计算中的权重。')
save(fig,'fig07_fusion_weights')

# 8: the same-test comparison; no arbitrary acceptance line.
combined=mt['combined_systems']
systems=[('决策融合系统',combined['specialist_or'],TEAL),('统一缺陷分类模型',combined['unified_single_model'],BLUE)]
fig,axs=plt.subplots(1,2,figsize=(12.0,4.7),layout='constrained')
for ax,metric,title in [(axs[0],'recall','召回率（Recall）'),(axs[1],'fpr','误报率（FPR）')]:
    for i,(label,op,color) in enumerate(systems):
        k,n=(op['tp'],op['tp']+op['fn']) if metric=='recall' else (op['fp'],op['fp']+op['tn'])
        p=k/n;lo,hi=wilson(k,n)
        ax.errorbar(p,i,xerr=[[p-lo],[hi-p]],fmt='o',color=color,ms=9,lw=2,capsize=5)
        ax.text(p,i-.16,f'{p:.2%}  ({k}/{n})',ha='center',fontsize=10)
        record('08',label,metric,p,'齿部缺损及联合测试记录',k,n)
        record('08',label,metric+'_wilson95_low',lo,'A4计数推导',k,n)
        record('08',label,metric+'_wilson95_high',hi,'A4计数推导',k,n)
    ax.set(yticks=[0,1],yticklabels=[r[0] for r in systems],xlim=(0,1),ylim=(1.6,-.6),title=title)
    ax.xaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='x',alpha=.14)
fig.suptitle('相同150张测试图：71张有缺陷 + 79张无可见目标缺陷（两类均无）',fontsize=16,weight='bold')
save(fig,'fig08_system_comparison')

# 9: validation is selection data, and each task has its own negative class.
fig,axs=plt.subplots(1,2,figsize=(12,4.4),layout='constrained')
task_data=[('划痕（V5）',sc['operating_points']['0.2'],st['metrics'],TEAL),
           ('齿部缺损（V1）',mh['operating_points']['0.2'],mt['image_metrics']['all'],BLUE)]
for ax,metric in [(axs[0],'recall'),(axs[1],'fpr')]:
    for label,val,test,col in task_data:
        vals=[val[metric],test[metric]];ax.plot([0,1],vals,'o-',lw=2,ms=7,color=col,label=label)
        for i,op in enumerate([val,test]):
            above = (label == '齿部缺损（V1）') if metric == 'recall' else (label == '划痕（V5）')
            ax.annotate(f'{op[metric]:.2%}',(i,op[metric]),xytext=(-10 if i==0 else 7,10 if above else -20),ha='right' if i==0 else 'left',textcoords='offset points',fontsize=10,color=col)
            k,n=(op['tp'],op['tp']+op['fn']) if metric=='recall' else (op['fp'],op['fp']+op['tn'])
            record('09',label+'/'+['validation','test'][i],metric,op[metric],'划痕与齿部缺损发布配置及测试记录',k,n)
    ax.set(xticks=[0,1],xticklabels=['参与选择的验证集','固定配置后的测试集'],xlim=(-.13,1.30),title='召回率（Recall）' if metric=='recall' else '误报率（FPR）')
    ax.set_ylim((.7,1.06) if metric=='recall' else (0,.23))
    if metric == 'recall':
        ax.set_yticks(np.arange(.7,1.001,.05))
    ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='y',alpha=.14);ax.legend(fontsize=9,loc='lower left' if metric=='recall' else 'upper left')
save(fig,'fig09_validation_test')

# 10: fixed-test case illustration only; no new threshold search.
fig,axs=plt.subplots(2,3,figsize=(11.8,7.1),layout='constrained')
for i,(stem,kind) in enumerate([('test_040','漏检 FN'),('test_074','漏检 FN'),('test_012','误报 FP')]):
    row=prediction_by_stem[stem];img,boxes,source=photo('scratch',stem)
    assert int(row['correct'])==0
    assert (row['truth']=='scratch') == (kind=='漏检 FN')
    show_photo(axs[0,i],img,boxes)
    axs[0,i].set_title(f"{kind} · {stem}\n分数 {float(row['scratch_probability']):.3f}",fontsize=11)
    show_photo(axs[1,i],img,boxes,zoom_region(img,boxes))
    axs[1,i].set_title('人工标注区域局部放大' if boxes else '正常加工纹/高光外观 · 无划痕标注',fontsize=10)
    record('10',stem,'fixed_scratch_score',float(row['scratch_probability']),'划痕逐图预测与标注')
fig.suptitle(f"划痕阈值 {sc['default_threshold']:.4f} 下的错误案例",fontsize=15,weight='bold')
save(fig,'fig10_scratch_errors')

# 11: overlapping positional strata.
fig,ax=plt.subplots(figsize=(11.8,3.6),layout='constrained')
groups=mt['image_metrics']['all']['groups']
for i,label in enumerate(['bottom','oblique','side']):
    g=groups[label];n=g['images'];k=round(g['recall']*n);p=k/n;lo,hi=wilson(k,n)
    ax.errorbar(p,i,xerr=[[p-lo],[hi-p]],fmt='o',color=RED if label=='oblique' else TEAL,ms=9,lw=2,capsize=5)
    ax.text(p,i-.16,f'{k}/{n} = {p:.1%}',ha='center',fontsize=10)
    for metric,value in [('recall',p),('wilson95_low',lo),('wilson95_high',hi)]:record('11',label,metric,value,'齿部缺损及联合测试记录',k,n)
ax.set(yticks=range(3),yticklabels=['bottom标签','oblique标签','side标签'],xlim=(.25,1.04),ylim=(2.6,-.6),title='不同位置齿部缺损的测试集召回率')
ax.xaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='x',alpha=.14)
ax.set_xlabel('点为召回率，线为Wilson 95%置信区间；位置分组可重叠')
save(fig,'fig11_position_recall')

# 12: software semantics, not a claimed finished review workflow.
fig,ax=plt.subplots(figsize=(12.6,4.6));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
ax.text(.01,.94,'同一份结果贯穿软件与机构输出',fontsize=18,weight='bold')
box(ax,.01,.35,.19,.30,'采集线程','保留最新帧\n相机/固定测试视频')
box(ax,.25,.35,.22,.30,'推理线程','定位 → ROI → 两类检测\n模型与配置校验')
box(ax,.52,.35,.20,.30,'统一检测结果','分数 · 阈值 · 预测类别\n预测框 · 耗时')
arrow(ax,(.20,.50),(.25,.50));arrow(ax,(.47,.50),(.52,.50))
for y,title,sub,pending in [(.69,'Web / 统计','共享同次判断',False),(.37,'串口 / 机构','原型命令支路',False),(.05,'人工复核','处理规则与记录待设计',True)]:
    box(ax,.79,y,.19,.22,title,sub,GOLD if pending else BLUE,pending)
    arrow(ax,(.72,.50),(.79,y+.11),pending)
ax.text(.01,.10,'已有PASS/REJECT字段与人工最终确认分开解释；视频模式禁用串口。',fontsize=10,color='#607681')
save(fig,'fig12_software_flow')

# Additional V3/V4 documentary evidence for the chapter-three tables.
v3=load_json('outputs/defect_search_v3/final_report.json')
v4_base=load_json('outputs/binary_defect_v4/baseline_report_before_extended.json')
v4_final=load_json('outputs/binary_defect_v4/final_report.json')
v4_cfg=load_json('outputs/binary_defect_v4/inference_config.json')
v4_candidates=load_json('outputs/binary_defect_v4/leaderboard.json')
v4_text=read_bytes('reports/V4实验详细技术报告.md').decode('utf-8')
v4_extended=next(row for row in v4_candidates if row['name']=='xfull_resnet18_384_w1_s73_r1')

# Substantive checks against the exact experiment artifacts and current scope.
checks=[]
def check(condition, name):
    if not condition: raise AssertionError(name)
    checks.append(name)

v3_image=v3['gate_test']['classes']['missing_tooth']
v3_boxes=v3['localization_test']['missing_tooth']['overall']
check(v3_image['tp']==15 and v3_image['tp']+v3_image['fn']==19,'V3缺损图像计数15/19')
check(v3_boxes['tp']==25 and v3_boxes['tp']+v3_boxes['fn']==52,'V3缺损区域计数25/52')
check(v3['localization_test']['scratch']['overall']['tp']==0 and v3['localization_test']['scratch']['by_view']['oblique']['iou_0.5']['tp']==1,'V3划痕两套计数差异保留')
for label,report,counts in [('baseline',v4_base,[17,6,14,13]),('fusion',v4_final,[19,7,13,11])]:
    op=report['test']['overall']
    check([op[k] for k in ['tp','fp','tn','fn']]==counts,'V4留出混淆矩阵/'+label)
    check(math.isclose(report['test']['subgroups']['scratch']['recall'],4/11),'V4划痕检出计数未改善/'+label)
check(math.isclose(v4_base['test']['subgroups']['missing_tooth']['recall'],13/19),'V4基线缺损13/19')
check(math.isclose(v4_final['test']['subgroups']['missing_tooth']['recall'],15/19),'V4融合缺损15/19')
check(v4_base['winner']['tta']=='tta_mean' and len(v4_cfg['models'])==3 and all(row['tta']=='tta_mean' for row in v4_cfg['models']),'V4单成员与三成员增强配置')
check(v4_extended['tta']=='tta_mean' and math.isclose(v4_extended['operating_points']['0.3']['threshold'],0.5711258729487544),'V4扩展模型增强与验证阈值')
check(all(value in v4_text for value in ['0.467','0.050','0.899','12 次模型前向']),'V4历史摘要数值及前向说明存在')

check(Counter(r['split'] for r in sm)=={'train':364,'val':150},'V5图像拆分364/150')
check(Counter(r['split'] for r in mm)=={'train':397,'val':99,'test':150},'V1图像拆分397/99/150')
check(not any('gear_id' in r or 'part_id' in r for r in sm+mm),'当前清单没有工件ID字段')
check(st['metrics']['threshold']==sc['default_threshold'],'V5测试/发布阈值一致')
check(mt['image_metrics']['all']['threshold']==mh['default_threshold'],'V1测试/发布阈值一致')
check(combined['counts']['scratch']+combined['counts']['missing_hole']-combined['counts']['both']==71,'含任一类缺陷的图像并集计数71')
check(len(sl)==10 and len(ml)==34 and len(fl)==21,'正式候选10/34/21')
observed=Counter()
for r in predictions:
    positive=r['truth']=='scratch';selected=r['prediction']=='REJECT'
    observed['tp' if positive and selected else 'fn' if positive else 'fp' if selected else 'tn']+=1
    check(float(r['threshold'])==sc['default_threshold'],f"固定CSV阈值 {PureWindowsPath(r['image']).name}")
check(all(observed[k]==st['metrics'][k] for k in ['tp','fp','tn','fn']),'V5逐图CSV重计数与JSON一致')
metrics=[st['metrics'],mt['image_metrics']['all']]+[r[1] for r in systems]
for i,op in enumerate(metrics):
    check(op['tp']+op['fp']+op['tn']+op['fn']==150,f'测试总图数150/{i}')
    check(math.isclose(op['recall'],op['tp']/(op['tp']+op['fn'])),f'Recall计数一致/{i}')
    check(math.isclose(op['fpr'],op['fp']/(op['fp']+op['tn'])),f'FPR计数一致/{i}')
    record('summary',str(i),'selected_fraction',(op['tp']+op['fp'])/150,'划痕测试记录及齿部缺损联合测试记录',op['tp']+op['fp'],150)

# 正文新增对照：读取既有工作点，不搜索新阈值。
selection_rows = [
    ('划痕/EfficientNet单模型', next(x for x in sl if x['name']=='f_efficientnet_b0_384_w1_s20260911'), (41,13), '划痕候选模型评价表'),
    ('划痕/P2检测模型', next(x for x in sl if x['name']=='p_detector_p2_960'), (38,19), '划痕候选模型评价表'),
    ('划痕/最终融合', sc, (42,9), '划痕发布配置'),
]
for name, expected in [
    ('f_cls_efficientnet_b0_512_exclude_difficult_s20260913', (34,6)),
    ('p_det_one_class_exclude_difficult_standard_960', (33,6)),
    ('classifier_mean', (34,5)),
    ('weighted_f_cls_efficientnet_b0_512_exclude_difficult_s20260913_0.25', (34,4)),
    ('weighted_classifier_mean_0.5', (34,4)),
]:
    selection_rows.append(('齿部缺损/'+name, next(x for x in fl if x['name']==name), expected, '齿部缺损融合候选评价表'))
for label, row, expected, source in selection_rows:
    op = row['operating_points']['0.2']
    check((op['tp'],op['fp']) == expected, '新增验证选型计数/'+label)
    for metric in ['tp','fp']:
        record('selection_comparison',label,metric,op[metric],source)

with (ASSETS/'chart_data.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['figure','label','metric','value','numerator','denominator','source'])
    writer.writeheader();writer.writerows(DATA)

# Static HTML: all figures embedded; no CDN, scripts or runtime downloads.
md=(ROOT/'GearPro_技术报告.md').read_text(encoding='utf-8')
renderer=markdown.Markdown(extensions=['tables','toc','fenced_code'],extension_configs={'toc':{'toc_depth':'2-3'}})
body=renderer.convert(md)
soup=BeautifulSoup(body,'html.parser')
for img in soup.find_all('img'):
    path=ROOT/img['src'];check(path.is_file(),'图片存在/'+img['src'])
    img['src']='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
    parent=img.parent
    if parent.name=='p':parent.name='figure'
for heading in soup.find_all('h2'):
    if heading.get_text().startswith('附录A'):
        heading['class']='appendix-start'
for table in soup.find_all('table'):
    wrap=soup.new_tag('div',attrs={'class':'table-wrap'});table.wrap(wrap)
for p in soup.find_all('p'):
    if len(list(p.children))==1 and p.find('em',recursive=False):p['class']='caption'
for a in soup.find_all('a',href=True):
    href=a['href']
    if not href.startswith(('http','data:','#')):
        check((ROOT/href).exists(),'本地资料链接存在/'+href)

check(not re.search(r'\[(?:[UP](?=[、，；;\]])|A\d+(?=[、，；;—–\]\-]))[^\]]*\]', md), '报告无内部来源代码')
check(len(re.findall(r'id="source-\d+"', md)) == 16, '16项具名实验来源完整')
review = ROOT / '教师审读问题与修改建议.md'
check(review.is_file(), '教师审读问题清单存在')
review_text = review.read_text(encoding='utf-8')
check(len(re.findall(r'^### \d+\.', review_text, re.M)) == 27, '教师审读27项问题完整')

ids=[tag['id'] for tag in soup.find_all(id=True)]
check(len(ids)==len(set(ids)),'章节锚点唯一')
check(len(soup.find_all('img'))==12,'正文与附录共12张图')
main_text=md.split('<a id="appendix-a"></a>')[0]
check(len(re.findall(r'^## [1-5]　',main_text,re.M))==5,'正文五章')
check(len(re.findall(r'!\[',main_text))==6,'正文六张核心图')
check('由人工摆放' in main_text and '确认看不到目标缺陷' in main_text, '采集与标注规则明确')
check('18/79是图像误报计数' in main_text and '不能证明三个成员都必要' in main_text, '评价单位与成员必要性边界明确')
check('### F.11' in md and '0.9634' in main_text and '0.9660' in main_text, '完整对照与近似AUPRC保留')
check('本轮没有恢复或改写工件对应关系' in md, '未将可辨识特征写成已恢复身份')
check('### 3.1　V3' in main_text and '### 3.2　V4' in main_text and '### 3.5　' in main_text,'新增关系融入第3章')
check('尚未由逐图预测重算' in main_text and '正文不以其“零检出”作为论据' in main_text,'补充证据来源与冲突边界明确')
check('Scratch V5' not in main_text and 'Missing Hole V1' not in main_text,'版本名移入附录')
for link in soup.find_all('a',href=True):
    if link['href'].startswith('#'):
        check(link['href'][1:] in ids,'内部跳转有效/'+link['href'])
check(len(list(ASSETS.glob('*.png')))==12,'12张PNG导出')
check(len(list(ASSETS.glob('*.svg')))==12,'12张SVG导出')
for svg in ASSETS.glob('*.svg'):ET.parse(svg)
check('生产验收标准' in md and '历史实验目标及选择约束' in md,'历史指标与正式验收区分')
check('只有图片顺序编号' in md and 'NX' in md and '未记录' in md,'当前事实纳入正文')
check(not re.search(r'\bturn\d+(?:search|view)\d+\b',md),'没有工具引用残留')
for obsolete in ['专项','逻辑OR','先导','长训','完整复训','难例精炼','排行榜','筛出可靠性','命中','历史留出','工程先验']:
    check(obsolete not in md, '正文术语检查/' + obsolete)
check('difficult表示识别困难' in md, '困难目标含义明确')
check('分数级加权融合' in md and '决策级融合' in md, '两层融合分别定义')
check('## 附录C' in md and (ROOT/'术语对照表.md').is_file(), '术语附录与独立对照表存在')


css='''
:root{--ink:#173544;--muted:#617581;--teal:#2457a7;--line:#d8e3e6;--paper:#fff;--bg:#edf2f3}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif;font-size:15px;line-height:1.9}
.layout{max-width:1400px;margin:auto;display:grid;grid-template-columns:238px minmax(0,1fr);gap:26px;padding:34px 30px 64px}
aside{position:sticky;top:24px;height:calc(100vh - 48px);overflow:auto;padding:10px 6px 20px}
.brand{font-size:25px;font-weight:750;letter-spacing:.07em;margin-bottom:5px}.edition{font-size:11px;letter-spacing:.09em;color:var(--muted);margin-bottom:23px}
aside ul{list-style:none;padding:0;margin:0}aside li{margin:6px 0}aside li ul{padding-left:12px;margin:3px 0 13px}aside a{color:#526c79;font-size:12px;line-height:1.6;text-decoration:none;display:block;padding:3px 0}aside a:hover{color:var(--teal)}
article{background:var(--paper);padding:52px 58px;box-shadow:0 8px 34px #21374409;border-top:5px solid var(--teal);min-width:0}
.eyebrow{color:var(--teal);font-size:12px;font-weight:700;letter-spacing:.1em;margin-bottom:17px}
h1{font-size:33px;line-height:1.4;letter-spacing:-.02em;margin:0 0 12px}h2{font-size:23px;line-height:1.5;margin:48px 0 17px;padding-top:17px;border-top:1px solid var(--line);font-weight:700}h1+h2{font-size:19px;color:#506b79;border:0;padding:0;margin:0 0 22px;font-weight:400}h3{font-size:18px;line-height:1.55;margin:26px 0 12px}p{margin:12px 0;text-align:justify}a{color:#2457a7;text-underline-offset:3px}strong{font-weight:700}
blockquote{margin:25px 0;padding:15px 19px;background:#f2f5fb;border-left:3px solid var(--teal);font-size:12px;line-height:1.8;color:#536e79}blockquote p{margin:0}
.table-wrap{width:100%;overflow:auto;margin:22px 0}table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.65}th{background:#eaf0fa;color:#294e5d;text-align:left;font-weight:700}th,td{padding:10px 10px;border-bottom:1px solid #dce7ea;vertical-align:top;min-width:54px}tr:nth-child(even) td{background:#f8fbfb}
figure{margin:26px 0 10px;break-inside:avoid}img{max-width:100%;height:auto;display:block}.caption{font-size:12px;line-height:1.75;color:var(--muted);margin-top:9px}
code{font-family:"Noto Sans Mono CJK SC",monospace;background:#f1f5f6;padding:2px 5px;border-radius:3px;overflow-wrap:anywhere;font-size:.9em}
.footer{margin-top:45px;border-top:1px solid var(--line);padding-top:15px;color:var(--muted);font-size:11px}
@media(max-width:1050px){.layout{grid-template-columns:185px minmax(0,1fr);gap:16px;padding:20px}article{padding:36px 28px}}
@media(max-width:760px){.layout{display:block;padding:12px}aside{position:static;height:auto;max-height:230px;margin-bottom:16px}aside .toc>ul{columns:2}aside li ul{display:none}article{padding:27px 18px}h1{font-size:27px}h2{font-size:20px}body{font-size:14px}}
@media print{@page{size:齿部缺损及联合测试记录;margin:18mm 16mm}body{background:#fff;font-size:10pt;line-height:1.7}.layout{display:block;padding:0;max-width:none}aside{display:none}article{padding:0;box-shadow:none;border:0}h1{font-size:24pt}h2{font-size:15pt;break-after:avoid;margin-top:24pt}h3{font-size:12pt;break-after:avoid}h2.appendix-start{break-before:page}p{orphans:3;widows:3}.table-wrap{overflow:visible}table{font-size:8pt}th,td{padding:6px}thead{display:table-header-group}tr{break-inside:avoid}figure{break-inside:avoid}a{color:inherit}blockquote{break-inside:avoid}.eyebrow{font-size:8pt}.caption{font-size:8pt}}
'''
page='<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GearPro：齿轮外观缺陷检测系统技术报告</title><style>'+css+'</style></head><body><div class="layout"><aside><div class="brand">GEARPRO</div><div class="edition">技术报告 · 2026-10-07</div>'+renderer.toc+'</aside><article><div class="eyebrow">项目任务 / 核心探索 / 参数依据 / 软件集成</div>'+str(soup)+'<div class="footer">GearPro · 阶段研究报告<br>正文与全部图片可离线阅读；文献网址需要网络，本地实验索引需要原项目目录。</div></article></div></body></html>'
(ROOT/'GearPro_技术报告.html').write_text(page,encoding='utf-8')
check('src="assets/' not in page,'HTML全部图片内嵌')
check(not re.search(r'<(?:script|link)[^>]+(?:src|href)="https?://',page),'无外部脚本或样式依赖')

verification={
    'report_date':'2026-10-07','body_chinese_characters':len(re.findall(r'[\u4e00-\u9fff]',main_text)),'body_figures':6,'appendix_figures':6,'input_sha256':INPUTS,
    'checks_passed':len(checks),'checks':checks,
    'chart_rows':len(DATA),'png_figures':12,'svg_figures':12,
    'physical_gears':{'normal':10,'scratch':15,'side_missing':15,'corner_missing':10,'source':'project_owner_confirmation'},
    'scope':'existing_artifacts_only; no_training; no_inference; no_threshold_change',
    'limitations':['physical_gear_split_unknown','human_review_workflow_pending','NX_systematic_metrics_not_recorded'],
}
(ROOT/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')

readme='''# GearPro技术报告阅读说明

- `GearPro_技术报告.html`：带目录的单文件阅读版，全部图片内嵌，可直接用浏览器离线打开。
- `GearPro_技术报告.md`：可修改正文，与`assets`目录放在一起阅读。
- `assets`：正文与附录共12组PNG/SVG图表及`chart_data.csv`，可用于后续排版或汇报。
- `教师审读问题与修改建议.md`：27项教师审读问题、当前回答、证据缺口与下一轮讨论重点。
- `术语对照表.md`：规范名称、历史称呼和方法定义。
- `verification.json`：输入文件哈希和数值/资料链接核对记录。
- `build_report.py`：在原项目中运行，读取已有实验记录重新生成图表及HTML；不训练或修改模型。

本轮取消内部来源代码，论文引用仍采用数字编号；实验资料按名称链接到附录B，项目事实统一说明。问题清单独立归档并跟踪本轮更新。当前版本补充可见缺陷标签规则、实际摄像头人工摆拍条件及单模型／融合验证对照；不训练、推理、调整部署阈值或恢复工件身份。选型优化前版本保存于相邻的`GearPro_技术报告_选型优化前_20261007`目录。来源规范前版本保存于相邻的`GearPro_技术报告_来源规范前_20261007`目录。

打包文件提供正文、图表及记录。附录中的本地实验资料链接和构建脚本需要原项目目录；文献链接需要网络。
本版本补充了V3判定与定位的区别，以及V4排序、阈值、集成的取舍；仍为五章精简正文（6张核心图）＋详细附录（6张补充图）。正文按约10—12页的阅读目标编排，实际打印页数取决于排版，尚未验证分页。参数细节、历史版本名、完整配置和补充分析见附录。修改前的完整版本保存于相邻的`GearPro_技术报告_完整版_20261007`目录。补充前的精简版本保存于相邻的`GearPro_技术报告_精简版_补充前_20261007`目录。方法名称及代码对应关系见`术语对照表.md`。
'''
(ROOT/'README.md').write_text(readme,encoding='utf-8')
archive=ROOT/'GearPro_技术报告_正文与图表.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted(ROOT.rglob('*')):
        if path.is_file() and path!=archive and '__pycache__' not in path.parts:
            z.write(path,str(Path('GearPro_技术报告')/path.relative_to(ROOT)))
print(json.dumps({'checks_passed':len(checks),'figures':12,'chart_rows':len(DATA),
                  'html_bytes':len(page.encode()),'markdown_characters':len(md),
                  'artifact_directory':str(ROOT)},ensure_ascii=False))
