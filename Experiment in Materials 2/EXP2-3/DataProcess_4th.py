import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# ==========================================
# 1. 环境配置 (极致清晰度与符号支持)
# ==========================================
# 使用 STIX 字体渲染数学符号，确保 $^\circ$C 完美显示
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['font.family'] = 'STIXGeneral' 
plt.rcParams['axes.unicode_minus'] = False 

# ==========================================
# 2. 数据预处理
# ==========================================
file_path = r"D:\.NWPU_QMUL\Experiments in Materials 2\EXP2-3\Team C.xlsx"
df = pd.read_excel(file_path)

# 自动填充 Batch 和 Filler 类型
df['Batch Number'] = df['Batch Number'].ffill().astype(int).astype(str)
df['Filler Type'] = df['Filler Type'].ffill()

# 将原始 ℃ 替换为 LaTeX 格式，解决乱码
df['Filler Type'] = df['Filler Type'].str.replace('℃', r'$^\circ$C', regex=False)

# 提取 Strain 数据行并清洗百分号
strain_df = df[df['Initial Length (cm)'] == 'Strain (%)'].copy()
test_cols = [f'test {i} (cm)' for i in range(1, 11)]

for col in test_cols:
    strain_df[col] = strain_df[col].astype(str).str.replace('%', '', regex=False)
    strain_df[col] = pd.to_numeric(strain_df[col], errors='coerce')

# 宽表转长表
df_plot = strain_df.melt(id_vars=['Filler Type', 'Batch Number'], 
                         value_vars=test_cols,
                         value_name='Strain_Value').dropna()

# 创建复合标签并保持原始顺序
df_plot['Full_Label'] = df_plot['Filler Type'] + "\nBatch " + df_plot['Batch Number']
unique_groups = df_plot.groupby(['Filler Type', 'Batch Number'], sort=False).size().index.tolist()

# 制造三大块之间的视觉间隔
final_order = []
last_type = None
for ft, bn in unique_groups:
    if last_type is not None and ft != last_type:
        final_order.append(f"spacer_{ft}") 
    final_order.append(f"{ft}\nBatch {bn}")
    last_type = ft

# ==========================================
# 3. 学术配色方案 (Nature/Science Style)
# ==========================================
academic_palette = ["#4C72B0", "#55A868", "#C44E52"] # 经典三色：深蓝、森绿、砖红
color_map = {t: academic_palette[i % 3] for i, t in enumerate(df_plot['Filler Type'].unique())}

palette_colors = []
for item in final_order:
    if "spacer" in item:
        palette_colors.append((0,0,0,0)) # 占位符设为透明
    else:
        t = item.split('\n')[0]
        palette_colors.append(color_map[t])

# ==========================================
# 4. 绘图与标注执行
# ==========================================
fig, ax = plt.subplots(figsize=(10, 5.5), dpi=200) # 屏幕预览清晰度
sns.set_style("white")

# 4.1 绘制基础箱型图
sns.boxplot(
    data=df_plot, x='Full_Label', y='Strain_Value', order=final_order,
    palette=palette_colors, width=0.6, linewidth=1.5, showfliers=False,
    ax=ax, boxprops=dict(edgecolor='0.2', alpha=0.6)
)

# 4.2 叠加背景原始数据点
sns.stripplot(
    data=df_plot, x='Full_Label', y='Strain_Value', order=final_order,
    size=3, color="black", alpha=0.15, jitter=True, ax=ax
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
# 5. 细节修饰与超清保存
# ==========================================
title_str = "Comparative Analysis of Ultimate Tensile Strain\nacross Diverse Filler Formulations and Processing Batches"
ax.set_title(title_str, fontsize=14, fontweight='bold', pad=20, fontname='Arial')

ax.set_ylabel("Ultimate Tensile Strain (%)", fontsize=11, fontweight='bold')
ax.set_xlabel("") # 下方已经有详细标签，此处留空更简洁

# 隐藏占位符文字
display_labels = [l if "spacer" not in l else "" for l in final_order]
ax.set_xticklabels(display_labels, fontsize=9)

# 去除多余边框并增加网格感
sns.despine(offset=10)
ax.yaxis.grid(True, linestyle='--', which='major', color='grey', alpha=0.15)

plt.tight_layout()

# 保存 600 DPI 极清图片（印刷标准）
plt.savefig("Strain_Analysis_Final_Version.png", dpi=1200, bbox_inches='tight')
plt.show()