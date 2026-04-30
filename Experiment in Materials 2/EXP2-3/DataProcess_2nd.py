import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# ==========================================
# 1. 字体环境配置 (解决 ℃ 显示问题)
# ==========================================
# 针对 Windows 环境，设置黑体显示特殊符号
plt.rcParams['font.sans-serif'] = ['SimHei'] 
plt.rcParams['axes.unicode_minus'] = False # 解决负号显示问题

# ==========================================
# 2. 数据处理
# ==========================================
file_path = r"D:\.NWPU_QMUL\Experiments in Materials 2\EXP2-3\Team C.xlsx"
df = pd.read_excel(file_path)

df['Batch Number'] = df['Batch Number'].ffill().astype(int).astype(str)
df['Filler Type'] = df['Filler Type'].ffill()

strain_df = df[df['Initial Length (cm)'] == 'Strain (%)'].copy()
test_cols = [f'test {i} (cm)' for i in range(1, 11)]
for col in test_cols:
    strain_df[col] = strain_df[col].astype(str).str.replace('%', '', regex=False)
    strain_df[col] = pd.to_numeric(strain_df[col], errors='coerce')

df_plot = strain_df.melt(id_vars=['Filler Type', 'Batch Number'], 
                         value_vars=test_cols,
                         value_name='Strain_Value').dropna()

# 创建复合标签并排序
df_plot['Full_Label'] = df_plot['Filler Type'] + "\nBatch " + df_plot['Batch Number']
unique_groups = df_plot.groupby(['Filler Type', 'Batch Number']).size().index.tolist()

# 插入空位制造“三大块”间隔
final_order = []
last_type = None
for ft, bn in unique_groups:
    if last_type is not None and ft != last_type:
        final_order.append(f"spacer_{ft}") 
    final_order.append(f"{ft}\nBatch {bn}")
    last_type = ft

# ==========================================
# 3. 莫兰迪高级感配色 (解决“丑”的问题)
# ==========================================
# 预定义三组不同色调的高级色（冷灰、柔蓝、雅绿）
morandi_colors = [
    "#92A8D1", # 柔和蓝
    "#88B04B", # 草本绿
    "#F7CAC9", # 樱花粉 (或可选 #955251 玛萨拉红)
]

color_map = {}
unique_types = df_plot['Filler Type'].unique()
for i, t in enumerate(unique_types):
    color_map[t] = morandi_colors[i % len(morandi_colors)]

palette_colors = []
for item in final_order:
    if "spacer" in item:
        palette_colors.append((0,0,0,0)) # 占位符透明
    else:
        t = item.split('\n')[0]
        palette_colors.append(color_map[t])

# ==========================================
# 4. 绘图与显示优化
# ==========================================
fig, ax = plt.subplots(figsize=(10, 6), dpi=100) # 减小了尺寸以适配屏幕
sns.set_style("ticks")

# 4.1 绘制箱型图
sns.boxplot(
    data=df_plot, x='Full_Label', y='Strain_Value', order=final_order,
    palette=palette_colors, width=0.6, linewidth=1.5, showfliers=False,
    ax=ax, boxprops=dict(edgecolor='0.3', alpha=0.85)
)

# 4.2 绘制散点 (颜色调浅，让整体更干净)
sns.stripplot(
    data=df_plot, x='Full_Label', y='Strain_Value', order=final_order,
    size=4, color="0.4", alpha=0.3, jitter=True, ax=ax
)

# 4.3 坐标轴美化 (使用 Unicode ℃)
ax.set_title(u'不同材料组别的断裂伸长率 (Tensile Strain) 分布图', fontsize=14, fontweight='bold', pad=20)
ax.set_ylabel(u'Strain (%)', fontsize=12)
ax.set_xlabel('')

# 隐藏占位符文字，优化标签
display_labels = [l if "spacer" not in l else "" for l in final_order]
ax.set_xticklabels(display_labels, rotation=30, ha='right', fontsize=9)

# 去除多余边框
sns.despine(offset=5)

# 添加横向参考线
ax.yaxis.grid(True, linestyle='--', alpha=0.4)

plt.tight_layout()

# 自动最大化窗口 (仅限 Windows)
try:
    mng = plt.get_current_fig_manager()
    mng.window.state('zoomed')
except:
    pass

plt.show()