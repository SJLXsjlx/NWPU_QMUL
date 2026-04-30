import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# ==========================================
# 1. 数据处理与逻辑细化
# ==========================================
file_path = r"D:\.NWPU_QMUL\Experiments in Materials 2\EXP2-3\Team C.xlsx"
df = pd.read_excel(file_path)

# 补全分类信息
df['Batch Number'] = df['Batch Number'].ffill().astype(int).astype(str)
df['Filler Type'] = df['Filler Type'].ffill()

# 提取应变数据行
strain_df = df[df['Initial Length (cm)'] == 'Strain (%)'].copy()

# 转换测试数据为数值
test_cols = [f'test {i} (cm)' for i in range(1, 11)]
for col in test_cols:
    strain_df[col] = strain_df[col].astype(str).str.replace('%', '', regex=False)
    strain_df[col] = pd.to_numeric(strain_df[col], errors='coerce')

# 转换为长表
df_plot = strain_df.melt(id_vars=['Filler Type', 'Batch Number'], 
                         value_vars=test_cols,
                         value_name='Strain_Value').dropna()

# 关键步骤：创建一个排序用的辅助列，并在不同 Filler Type 之间插入“空位”
df_plot['Group'] = df_plot['Filler Type'] + "\nBatch " + df_plot['Batch Number']

# 获取排序顺序：先按 Filler Type 排，再按 Batch 排
order = df_plot.groupby(['Filler Type', 'Batch Number']).size().index.tolist()

# 在不同 Filler Type 变化的地方插入一个 None，制造视觉间隔
final_order = []
last_type = None
for ft, bn in order:
    if last_type is not None and ft != last_type:
        final_order.append(f"spacer_{ft}") # 插入一个虚假的占位符
    final_order.append(f"{ft}\nBatch {bn}")
    last_type = ft

# ==========================================
# 2. 绘图美化与屏幕适配
# ==========================================
# 设置一个适合屏幕的尺寸 (10x6 比较通用)，dpi设为100方便实时显示
plt.figure(figsize=(10, 6), dpi=100)
sns.set_theme(style="white")

# 自定义调色板：为3个大类准备3种主色调
# 200℃-SCA (1组), 210℃-Ag/Gl (3组), 195℃-Ni/G (4组) -> 这里根据你的实际数据组数调整
main_colors = sns.color_palette("husl", 3)
color_map = {}
unique_types = df_plot['Filler Type'].unique()
for i, t in enumerate(unique_types):
    color_map[t] = main_colors[i]

# 为 final_order 中的每个项分配颜色
palette_colors = []
for item in final_order:
    if "spacer" in item:
        palette_colors.append((0,0,0,0)) # 透明占位
    else:
        # 找到对应的 Filler Type 颜色
        t = item.split('\n')[0]
        palette_colors.append(color_map[t])

# 绘图
ax = sns.boxplot(
    data=df_plot, 
    x='Group', 
    y='Strain_Value',
    order=final_order,
    palette=palette_colors,
    width=0.7,
    linewidth=1.2,
    showfliers=False
)

# 叠加散点
sns.stripplot(
    data=df_plot, x='Group', y='Strain_Value', order=final_order,
    size=3, color=".3", alpha=0.4, jitter=True
)

# ==========================================
# 3. 屏幕显示优化与标注
# ==========================================
plt.title('Tensile Strain Analysis by Filler Type & Batch', fontsize=14, pad=20)
plt.ylabel('Strain (%)', fontsize=12)
plt.xlabel('', fontsize=12)

# 处理X轴标签：隐藏占位符的文字
labels = [l if "spacer" not in l else "" for l in final_order]
ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)

# 在顶部添加大类的标注（Filler Type）
for i, t in enumerate(unique_types):
    # 这里是一个简单的位置估算逻辑，将大类名字写在对应的组上方
    # 你可以手动微调这里的 x 坐标
    pass 

sns.despine()
plt.tight_layout()

# 关键：如果屏幕还是放不下，可以使用这个命令强行调整显示窗口
# plt.get_current_fig_manager().window.state('zoomed') # 仅限 Windows 窗口最大化

print("图表已生成。")
print(f"识别到 Filler Type: {list(unique_types)}")
print(f"总计显示组数: {len(order)} 个 Batch")

plt.show()
