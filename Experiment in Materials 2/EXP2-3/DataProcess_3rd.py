import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# ==========================================
# 1. 环境配置 (无需依赖中文字体，解决符号乱码)
# ==========================================
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'Liberation Sans', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False 

# ==========================================
# 2. 数据处理与符号转换
# ==========================================
file_path = r"D:\.NWPU_QMUL\Experiments in Materials 2\EXP2-3\Team C.xlsx"
df = pd.read_excel(file_path)

# 补全分类信息
df['Batch Number'] = df['Batch Number'].ffill().astype(int).astype(str)
df['Filler Type'] = df['Filler Type'].ffill()

# 【核心修复】将数据中的 ℃ 替换为 LaTeX 格式的 $^\circ$C，确保 100% 显示成功
df['Filler Type'] = df['Filler Type'].str.replace('℃', r'$^\circ$C', regex=False)

# 提取应变行
strain_df = df[df['Initial Length (cm)'] == 'Strain (%)'].copy()
test_cols = [f'test {i} (cm)' for i in range(1, 11)]

for col in test_cols:
    strain_df[col] = strain_df[col].astype(str).str.replace('%', '', regex=False)
    strain_df[col] = pd.to_numeric(strain_df[col], errors='coerce')

df_plot = strain_df.melt(id_vars=['Filler Type', 'Batch Number'], 
                         value_vars=test_cols,
                         value_name='Strain_Value').dropna()

# 整合标签
df_plot['Full_Label'] = df_plot['Filler Type'] + "\nBatch " + df_plot['Batch Number']
unique_groups = df_plot.groupby(['Filler Type', 'Batch Number'], sort=False).size().index.tolist()

# 制造间隔逻辑
final_order = []
last_type = None
for ft, bn in unique_groups:
    if last_type is not None and ft != last_type:
        final_order.append(f"spacer_{ft}") 
    final_order.append(f"{ft}\nBatch {bn}")
    last_type = ft

# ==========================================
# 3. 审美优化 (Nature 风格配色)
# ==========================================
# 选用更具质感的深浅色系
academic_palette = [
    "#4C72B0", # 深邃蓝 (200°C 组)
    "#55A868", # 森林绿 (210°C 组)
    "#C44E52", # 砖石红 (195°C 组)
]

color_map = {t: academic_palette[i % len(academic_palette)] 
             for i, t in enumerate(df_plot['Filler Type'].unique())}

palette_colors = []
for item in final_order:
    if "spacer" in item:
        palette_colors.append((0,0,0,0))
    else:
        t = item.split('\n')[0]
        palette_colors.append(color_map[t])

# ==========================================
# 4. 绘图执行
# ==========================================
# 调整画布比例，使其在屏幕上显示更紧凑
fig, ax = plt.subplots(figsize=(10, 5.5), dpi=200) 
sns.set_style("white")

# 绘制箱型图 (Boxplot)
sns.boxplot(
    data=df_plot, x='Full_Label', y='Strain_Value', order=final_order,
    palette=palette_colors, width=0.6, linewidth=1.2, showfliers=False,
    ax=ax, boxprops=dict(edgecolor='0.2', alpha=0.9)
)

# 叠加抖动散点 (Stripplot)
sns.stripplot(
    data=df_plot, x='Full_Label', y='Strain_Value', order=final_order,
    size=3.5, color="black", alpha=0.25, jitter=True, ax=ax
)

# 4.3 核心：绘制均值、误差棒及数据标签
for i, label in enumerate(final_order):
    if "spacer" not in label:
        group_data = df_plot[df_plot['Full_Label'] == label]['Strain_Value']
        if not group_data.empty:
            mean_val = group_data.mean()
            std_val = group_data.std()
            
            # 绘制均值标记与误差棒 (白色钻石)
            ax.errorbar(i, mean_val, yerr=std_val, fmt='D', color='white', 
                        ecolor='black', elinewidth=1.5, capsize=4, 
                        markersize=7, markeredgecolor='black', zorder=10)
            
            # 【新增】打上均值数值标签
            # 格式：保留1位小数 + % 符号，位置在均值点右侧
            ax.text(i + 0.15, mean_val, f'{mean_val:.1f}%', 
                    va='center', ha='left', fontsize=9, 
                    fontweight='bold', color='black', 
                    bbox=dict(facecolor='white', alpha=0.5, edgecolor='none', pad=1))

# ==========================================
# 5. 英文标题与细节打磨
# ==========================================
# 一个既专业又地道的标题
title_str = "Comparative Analysis of Ultimate Tensile Strain\nacross Diverse Filler Formulations and Processing Batches"
ax.set_title(title_str, fontsize=14, fontweight='bold', pad=20, fontname='Arial')

ax.set_ylabel("Ultimate Tensile Strain (%)", fontsize=11, fontweight='bold')
ax.set_xlabel("") # 下方已经有详细标签，此处留空更简洁

# 隐藏占位符文字
display_labels = [l if "spacer" not in l else "" for l in final_order]
ax.set_xticklabels(display_labels, fontsize=9)

# 移除冗余边框并添加淡色网格线
sns.despine()
ax.yaxis.grid(True, linestyle='--', which='major', color='grey', alpha=0.15)

plt.tight_layout()

# 保存高质量图表
plt.savefig("Academic_Strain_Analysis.png", dpi=1200, bbox_inches='tight')
plt.show()