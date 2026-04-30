import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from matplotlib.patheffects import withStroke

# ==========================================
# 1. 环境配置与数据加载
# ==========================================
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['axes.unicode_minus'] = False 

file_path = r"D:\.NWPU_QMUL\Experiments in Materials 2\EXP2-3\Team B.xlsx"
df = pd.read_excel(file_path)

# 数据清洗
df['Batch Number'] = df['Batch Number'].ffill().astype(int).astype(str)
df['Filler Type'] = df['Filler Type'].ffill().str.replace('℃', r'$^\circ$C', regex=False)
df['Condition'] = df['Processing  Condition'].apply(
    lambda x: 'Original' if 'original' in str(x).lower() else 'Stretched'
)

test_cols = [f'test {i} (cm)' for i in range(1, 11)]
df_melted = df.melt(id_vars=['Filler Type', 'Batch Number', 'Condition'], 
                    value_vars=test_cols, value_name='Res').dropna()

# 确定大类排序和 Batch 顺序
filler_order = df.groupby('Filler Type', sort=False)['Batch Number'].unique()
ordered_batches = [b for batches in filler_order.values for b in batches]

# ==========================================
# 2. 创建分断坐标轴 (解决原长度箱子太小的问题)
# ==========================================
# 增加底部子图的高度比例 (1.2)，让低电阻数据的箱子更“高”更清晰
fig, (ax_top, ax_bottom) = plt.subplots(2, 1, sharex=True, figsize=(14, 9), 
                                         gridspec_kw={'height_ratios': [1, 1.2]})
plt.subplots_adjust(hspace=0.08) # 缩小子图间隙

colors = {"Original": "#546A7B", "Stretched": "#E8985E"}

# 定义绘图函数
def draw_on_axis(ax):
    sns.boxplot(data=df_melted, x='Batch Number', y='Res', hue='Condition',
                order=ordered_batches, palette=colors, width=0.6, 
                linewidth=1.2, showfliers=False, ax=ax, boxprops=dict(alpha=0.7))
    sns.stripplot(data=df_melted, x='Batch Number', y='Res', hue='Condition',
                  order=ordered_batches, dodge=True, size=2.5, palette=colors, 
                  alpha=0.2, jitter=True, ax=ax, legend=False)

draw_on_axis(ax_top)
draw_on_axis(ax_bottom)

# ==========================================
# 3. 核心修复：设置量级区间与标签标注
# ==========================================
# 根据数据动态设置上下轴范围
orig_max = df_melted[df_melted['Condition'] == 'Original']['Res'].max()
ax_bottom.set_ylim(0, orig_max * 1.5)  # 下轴只显示 0 到微小电阻区间
ax_top.set_ylim(20, df_melted['Res'].max() * 1.1) # 上轴显示高电阻区间

# 修复 IndexError：直接使用数据列表而非从 ax 中提取 label
for i, batch in enumerate(ordered_batches):
    for j, cond in enumerate(['Original', 'Stretched']):
        subset = df_melted[(df_melted['Batch Number'] == batch) & (df_melted['Condition'] == cond)]['Res']
        if not subset.empty:
            m = subset.mean()
            x_pos = i - 0.15 if j == 0 else i + 0.15
            
            # 判断该数据点应该标在哪个子图上
            if m > orig_max * 1.5:
                curr_ax = ax_top
                va, offset = 'bottom', 1.1
            else:
                curr_ax = ax_bottom
                # 针对 Original 数据，标签往下放，Stretched 往上放，避免重叠
                va = 'bottom' if cond == 'Stretched' else 'top'
                offset = 1.1 if cond == 'Stretched' else 0.9

            curr_ax.plot(x_pos, m, marker='D', color='white', markersize=4, markeredgecolor='black', zorder=20)
            curr_ax.text(x_pos, m * offset, f'{m:.1f}', ha='center', va=va, 
                         fontsize=8, fontweight='bold', 
                         path_effects=[withStroke(linewidth=2, foreground="white")])

# ==========================================
# 4. 视觉装饰（断裂线与大类标签）
# ==========================================
# 隐藏中间的轴线
ax_top.spines['bottom'].set_visible(False)
ax_bottom.spines['top'].set_visible(False)
ax_top.tick_params(labelbottom=False)

# 绘制典型的“断裂”斜线标志
d = .012 
kwargs = dict(transform=ax_top.transAxes, color='k', clip_on=False, linewidth=1)
ax_top.plot((-d, +d), (-d, +d), **kwargs); ax_top.plot((1 - d, 1 + d), (-d, +d), **kwargs)
kwargs.update(transform=ax_bottom.transAxes)
ax_bottom.plot((-d, +d), (1 - d, 1 + d), **kwargs); ax_bottom.plot((1 - d, 1 + d), (1 - d, 1 + d), **kwargs)

# 顶部标注 Filler Type
y_lim_top = ax_top.get_ylim()[1]
curr_idx = 0
for ft, batches in filler_order.items():
    n = len(batches)
    center = curr_idx + (n-1)/2
    ax_top.text(center, y_lim_top * 1.02, ft, ha='center', fontweight='bold', fontsize=12, color='0.2')
    curr_idx += n

# 标签润色
fig.text(0.04, 0.5, 'Electrical Resistance ($\Omega$)', va='center', rotation='vertical', fontsize=14, fontweight='bold')
ax_bottom.set_xlabel('Specimen Batch Number', fontsize=12, fontweight='bold')
ax_top.set_ylabel(''); ax_bottom.set_ylabel('')
ax_top.legend().remove()
ax_bottom.legend(title="Testing State", loc='upper right')

plt.savefig("Resistance_BrokenAxis_Final.png", dpi=600, bbox_inches='tight')
plt.show()
