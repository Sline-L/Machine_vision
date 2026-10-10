import os

import matplotlib.pyplot as plt
import numpy as np

# Output directories
out_dir = os.path.join(os.path.dirname(__file__), '../figures')
os.makedirs(out_dir, exist_ok=True)
assets_dir = os.path.join(os.path.dirname(__file__), '../../assets')
os.makedirs(assets_dir, exist_ok=True)

# Publication grade styling with Chinese font support and requested palette
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10
plt.rcParams['axes.linewidth'] = 0.9
plt.rcParams['axes.edgecolor'] = '#27374D'
plt.rcParams['xtick.direction'] = 'out'
plt.rcParams['ytick.direction'] = 'out'

# 4-Color Palette requested
C1 = '#27374D'  # Dark Slate Navy
C2 = '#526D82'  # Steel Slate Blue
C3 = '#9DB2BF'  # Light Slate Grey
C4 = '#DDE6ED'  # Ice Light Grey

# =============================================================
# 图 1：光度立体多模态（RGB）与单纹理模态消融对比 (纵坐标严格封顶 100%)
# =============================================================
fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=300)

materials = ['NI (纯镍镀层)', 'NS (洋白铜/镍银合金)', 'NI7 (高光镍合金)']
x = np.arange(len(materials))
width = 0.18

sens_rgb = [98.00, 95.40, 98.55]
sens_tex = [94.77, 90.81, 97.10]
spec_rgb = [93.10, 88.30, 96.15]
spec_tex = [90.27, 81.90, 95.05]

rects1 = ax.bar(x - width*1.5, sens_rgb, width, label='敏感度 (RGB 光度立体融合)', 
                color=C1, edgecolor=C1, linewidth=0.8)
rects2 = ax.bar(x - width*0.5, sens_tex, width, label='敏感度 (Texture-Only 单纹理基准)', 
                color=C3, edgecolor=C1, linewidth=0.8, hatch='//')
rects3 = ax.bar(x + width*0.5, spec_rgb, width, label='特异度 (RGB 光度立体融合)', 
                color=C2, edgecolor=C1, linewidth=0.8)
rects4 = ax.bar(x + width*1.5, spec_tex, width, label='特异度 (Texture-Only 单纹理基准)', 
                color=C4, edgecolor=C2, linewidth=0.8, hatch='\\\\')

# 增益差值标注 (紧凑贴合，不溢出 100%)
for b1, b2, g in zip(rects1, rects2, [sens_rgb[i] - sens_tex[i] for i in range(3)]):
    y_pos = min(max(b1.get_height(), b2.get_height()) + 0.35, 99.1)
    ax.text((b1.get_x() + b2.get_x() + b1.get_width()) / 2, y_pos, f'+{g:.2f}%', 
            ha='center', va='bottom', fontsize=7.8, fontweight='bold', color=C1)

for b1, b2, g in zip(rects3, rects4, [spec_rgb[i] - spec_tex[i] for i in range(3)]):
    y_pos = min(max(b1.get_height(), b2.get_height()) + 0.35, 99.1)
    ax.text((b1.get_x() + b2.get_x() + b1.get_width()) / 2, y_pos, f'+{g:.2f}%', 
            ha='center', va='bottom', fontsize=7.8, fontweight='bold', color=C2)

ax.set_ylabel('评估指标百分比 (%)', fontsize=10.5, fontweight='bold', color=C1)
ax.set_xticks(x)
ax.set_xticklabels(materials, fontsize=10, fontweight='bold', color=C1)
ax.set_ylim(75, 100.5)
ax.set_yticks([75, 80, 85, 90, 95, 100])
ax.yaxis.grid(True, linestyle='--', which='major', color=C4, alpha=0.9)
ax.set_axisbelow(True)

# 图例放置在轴顶与标题之间的专用留白带
ax.legend(frameon=True, facecolor='white', edgecolor=C3, fontsize=8.5, ncol=2, 
          loc='lower center', bbox_to_anchor=(0.5, 1.02), framealpha=0.95)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

fig.suptitle('图 1  光度立体多模态（RGB）与单纹理模态在不同金属材质下的缺陷分割性能消融对比 [4]', 
             fontsize=11, fontweight='bold', color=C1, y=0.98)
fig.subplots_adjust(top=0.83, bottom=0.12, left=0.12, right=0.92)

fig1_path = os.path.join(out_dir, 'fig1_photometric_modality_ablation.png')
plt.savefig(fig1_path, dpi=300)
plt.savefig(os.path.join(assets_dir, 'fig1_photometric_modality_ablation.png'), dpi=300)
plt.close()
print(f"Saved: {fig1_path}")

# =============================================================
# 图 2：YOLOv11s vs MSFE-YOLO 精度-速度帕累托散点折线图
# =============================================================
fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=300)

models = ['YOLOv11s (基线模型)', 'MSFE-YOLO (改进模型)']
fps_rtx = [137.0, 89.3]
precision = [69.8, 78.9]

# 标准学术散点标记
ax.scatter(fps_rtx[0], precision[0], color=C3, edgecolors=C1, s=130, marker='o', 
           linewidth=1.5, zorder=5, label='YOLOv11s (baseline模型: 8.99 M, 21.6 GFLOPs)')
ax.scatter(fps_rtx[1], precision[1], color=C1, edgecolors=C1, s=140, marker='D', 
           linewidth=1.5, zorder=5, label='MSFE-YOLO (改进模型: 11.69 M, 27.9 GFLOPs)')

# 帕累托权衡虚线
ax.plot(fps_rtx, precision, color=C2, linestyle='--', linewidth=1.8, zorder=3)

# 标注 MSFE-YOLO
ax.annotate("MSFE-YOLO\n精确率: 78.9% (+9.1 pp)\n速度: 89.3 FPS", 
            xy=(fps_rtx[1], precision[1]), xytext=(fps_rtx[1] + 12, precision[1] + 1.6),
            ha='left', fontsize=8.5, fontweight='bold', color=C1,
            arrowprops=dict(arrowstyle="->", color=C1, lw=1.2))

# 标注 YOLOv11s
ax.annotate("YOLOv11s baseline\n精确率: 69.8%\n速度: 137.0 FPS", 
            xy=(fps_rtx[0], precision[0]), xytext=(fps_rtx[0] - 10, precision[0] - 3.5),
            ha='right', fontsize=8.5, fontweight='bold', color=C1,
            arrowprops=dict(arrowstyle="->", color=C2, lw=1.1))

# 演化关系说明
# ax.text(113, 75.3, "精确率大幅提升 (+9.1 pp)\n速度合理折衷 (-34.8% FPS)", 
        # fontsize=8.5, color=C2, fontweight='bold', style='italic', ha='center')

# 工业实时基准线 (30 FPS)
ax.axvline(x=30, color=C2, linestyle=':', linewidth=1.3, zorder=2)
ax.text(32.5, 71.0, '工业实时检测标准阈值 (30 FPS)', color=C2, fontsize=8.5, rotation=90, fontweight='bold')

# 左上角图例
ax.legend(frameon=True, facecolor='white', edgecolor=C3, fontsize=8.5, loc='upper left', 
          bbox_to_anchor=(0.04, 0.96), framealpha=0.95, markerscale=0.5)

ax.set_xlabel('RTX 3090 推理吞吐量 (FPS)', fontsize=10.5, fontweight='bold', color=C1)
ax.set_ylabel('精确率 Precision (%)', fontsize=10.5, fontweight='bold', color=C1)
ax.set_xlim(15, 165)
ax.set_ylim(64, 85)
ax.grid(True, linestyle='--', color=C4, zorder=1)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.title('图 2  YOLOv11s 基准与 MSFE-YOLO 精度—速度帕累托权衡分析 [19]', 
          fontsize=11.5, pad=14, fontweight='bold', color=C1)
plt.tight_layout()

fig2_path = os.path.join(out_dir, 'fig2_msfe_yolo_pareto_tradeoff.png')
plt.savefig(fig2_path, dpi=300)
plt.savefig(os.path.join(assets_dir, 'fig2_msfe_yolo_pareto_tradeoff.png'), dpi=300)
plt.close()
print(f"Saved: {fig2_path}")

# =============================================================
# 图 3：时序多帧投票机制双轴权衡图 (双纵坐标均严格封顶 100)
# =============================================================
fig, ax1 = plt.subplots(figsize=(8.2, 5.4), dpi=300)

N = [1, 2, 3, 4]
false_alarms = [78, 48, 34, 24]
reduction_rate = [0.0, 38.5, 56.4, 69.2]
detection_rate = [100.0, 100.0, 100.0, 86.67]
fnr = [0.0, 0.0, 0.0, 13.33]

# 左轴柱状图 (正常齿轮误报件数，封顶 100 件)
bars = ax1.bar(N, false_alarms, width=0.38, color=C2, alpha=0.9, 
               edgecolor=C1, linewidth=0.9, zorder=2, label='正常齿轮误报件数 (件/100件合格品)')

for bar, fa, red in zip(bars, false_alarms, reduction_rate):
    y = bar.get_height()
    red_str = f"(-{red:.1f}%)" if red > 0 else "(单帧基准)"
    ax1.text(bar.get_x() + bar.get_width()/2, y + 2.0, f"{fa} 件\n{red_str}", 
             ha='center', va='bottom', fontsize=8.5, fontweight='bold', color=C1)

ax1.set_xlabel('连续判定图像帧数 (N)', fontsize=10.5, fontweight='bold', color=C1)
ax1.set_ylabel('正常齿轮误报件数 (件 / 100件合格品)', fontsize=10.5, fontweight='bold', color=C1)
ax1.set_ylim(0, 102)
ax1.set_yticks([0, 20, 40, 60, 80, 100])
ax1.set_xticks(N)
ax1.set_xticklabels([f"N = {i}" for i in N], fontsize=10, fontweight='bold', color=C1)
ax1.tick_params(axis='y', labelcolor=C1)
ax1.grid(True, linestyle=':', color=C4, zorder=1)

# 右轴折线图 (检出率与漏检率，封顶 100%)
ax2 = ax1.twinx()
line1 = ax2.plot(N, detection_rate, color=C1, marker='o', markersize=7.5, 
                 linewidth=2.4, label='缺陷齿轮检出率 (%)', zorder=4)
line2 = ax2.plot(N, fnr, color=C3, marker='s', markersize=6.5, linestyle='--', 
                 linewidth=2.0, label='漏检率 FNR (%)', zorder=4)

ax2.set_ylabel('检出率 / 漏检率 百分比 (%)', fontsize=10.5, fontweight='bold', color=C1)
ax2.set_ylim(-2, 102)
ax2.set_yticks([0, 20, 40, 60, 80, 100])
ax2.tick_params(axis='y', labelcolor=C1)

# N=3 最佳平衡点标注
ax1.axvline(x=3, color=C1, linestyle='-.', linewidth=1.5, zorder=3)
# ax1.annotate("工程最优操作点 (N = 3)\n• 100% 缺陷检出 (0% 漏检)\n• 误报量大幅压降 56.4%", 
        #     xy=(3, 34), xytext=(2.2, 54),
        #     arrowprops=dict(arrowstyle="->", color=C1, lw=1.3),
        #     fontsize=8.5, fontweight='bold', color=C1)

# N=4 漏检警示标注
# ax2.annotate("严重漏检风险!\n(漏检率: 13.3%)", 
        #     xy=(4, 86.67), xytext=(3.45, 55),
        #     arrowprops=dict(arrowstyle="->", color=C1, lw=1.1),
        #     fontsize=8, fontweight='bold', color=C1)

# 图例放置在坐标轴正上方，独立美观
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='lower center', 
           bbox_to_anchor=(0.5, 1.02), ncol=3, fontsize=8.2, framealpha=0.95, edgecolor=C3)

fig.suptitle('图 3  时序多帧投票机制下连续判定帧数对缺陷检出率与正常件误报数的双轴权衡 [5]', 
             fontsize=11, fontweight='bold', color=C1, y=0.98)
fig.subplots_adjust(top=0.83, bottom=0.12, left=0.12, right=0.88)

fig3_path = os.path.join(out_dir, 'fig3_temporal_voting_tradeoff.png')
plt.savefig(fig3_path, dpi=300)
plt.savefig(os.path.join(assets_dir, 'fig3_temporal_voting_tradeoff.png'), dpi=300)
plt.close()
print(f"Saved: {fig3_path}")
