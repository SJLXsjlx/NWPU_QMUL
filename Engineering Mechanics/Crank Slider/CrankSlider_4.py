import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

# ================= 全局样式配置 (调小字号) =================
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["SimHei", "Times New Roman"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white",
    "figure.dpi": 150,
    "axes.titlesize": 10,  # 标题字号调小
    "axes.labelsize": 9,   # 坐标轴标签字号调小
    "xtick.labelsize": 8,  # 刻度字号
    "ytick.labelsize": 8
})

def crank_slider_final_clean():
    # 1. 题目已知参数 (OA=2, AB=6)
    r = 2.0; L = 6.0; omega = 1.0; l1_2d = 1.0

    # 2. 数据计算
    t_3d = np.linspace(0, 4 * np.pi, 100)
    l1_3d = np.linspace(0, L, 60)
    T, L1 = np.meshgrid(t_3d, l1_3d)

    Ax = r * np.cos(omega * T)
    Ay = r * np.sin(omega * T)
    Bx = Ax + np.sqrt(L**2 - Ay**2)
    
    Px_3d = Ax + (L1 / L) * (Bx - Ax)
    Py_3d = Ay * (1 - L1 / L)
    Vpy_3d = r * omega * np.cos(omega * T) * (1 - L1 / L)
    Apy_3d = -r * (omega**2) * np.sin(omega * T) * (1 - L1 / L)

    # 2D 轨迹计算 (l1 = 1.0)
    t_2d = np.linspace(0, 2 * np.pi, 150)
    Ax_2d = r * np.cos(omega * t_2d); Ay_2d = r * np.sin(omega * t_2d)
    Bx_2d = Ax_2d + np.sqrt(L**2 - Ay_2d**2)
    Px_2d = Ax_2d + (l1_2d / L) * (Bx_2d - Ax_2d)
    Py_2d = Ay_2d * (1 - l1_2d / L)

    # 3. 绘图
    fig = plt.figure(figsize=(14, 10))
    # 增加子图间的物理间距
    plt.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.92, wspace=0.25, hspace=0.3)
    
    fig.suptitle('曲柄滑块机构运动学综合分析仪表盘', fontsize=14, fontweight='bold', y=0.98)

    # --- [A] 位置流形 ---
    ax1 = fig.add_subplot(221, projection='3d')
    surf1 = ax1.plot_surface(Px_3d, L1, Py_3d, cmap='viridis', alpha=0.7, edgecolor='none')
    ax1.set_title('Fig. 7-17(a) 位置轨迹流形', pad=10)
    ax1.set_xlabel('$x_p$(m)', labelpad=5)
    ax1.set_ylabel('$l_1$(m)', labelpad=5)
    ax1.set_zlabel('$y_p$(m)', labelpad=5)
    ax1.view_init(elev=20, azim=-130)

    # --- [B] 速度流形 ---
    ax2 = fig.add_subplot(222, projection='3d')
    surf2 = ax2.plot_surface(L1, T, Vpy_3d, cmap='coolwarm', alpha=0.8, edgecolor='none')
    ax2.plot_surface(L1, T, np.zeros_like(T), color='black', alpha=0.1) 
    ax2.set_title('Fig. 7-18 速度动态流形', pad=10)
    ax2.set_xlabel('$l_1$(m)', labelpad=5)
    ax2.set_ylabel('$t$(s)', labelpad=5)
    ax2.set_zlabel('$v_{py}$(m/s)', labelpad=5)
    ax2.view_init(elev=25, azim=-45)

    # --- [C] 加速度流形 ---
    ax3 = fig.add_subplot(223, projection='3d')
    surf3 = ax3.plot_surface(L1, T, Apy_3d, cmap='magma', alpha=0.8, edgecolor='none')
    ax3.set_title('加速度能量场流形', pad=10)
    ax3.set_xlabel('$l_1$(m)', labelpad=5)
    ax3.set_ylabel('$t$(s)', labelpad=5)
    ax3.set_zlabel('$a_{py}$(m/s²)', labelpad=5)
    ax3.view_init(elev=25, azim=-45)

    # --- [D] 2D 精确轨迹 ---
    ax4 = fig.add_subplot(224)
    ax4.plot(Px_2d, Py_2d, 'k-', linewidth=1.5)
    for spine in ax4.spines.values(): spine.set_color('none')
    ax4.grid(True, linestyle=':', alpha=0.4)
    
    # 手动箭头坐标轴
    x_max = np.max(Px_2d)
    y_max = np.max(Py_2d)
    ax4.annotate('', xy=(x_max + 1, 0), xytext=(np.min(Px_2d)-0.5, 0),
                 arrowprops=dict(arrowstyle='-|>', color='black', lw=1))
    ax4.annotate('', xy=(0, y_max + 0.8), xytext=(0, np.min(Py_2d)-0.8),
                 arrowprops=dict(arrowstyle='-|>', color='black', lw=1))
    
    ax4.text(x_max + 1.1, 0, '$x/m$', fontsize=9)
    ax4.text(0.1, y_max + 0.8, '$y/m$', fontsize=9)
    ax4.set_title('Fig. 7-17(b) 特定点($l_1=1m$)平面轨迹', pad=10)
    ax4.set_aspect('equal')

    # 统一背景美化
    for ax in [ax1, ax2, ax3]:
        ax.xaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
        ax.yaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))
        ax.zaxis.set_pane_color((1.0, 1.0, 1.0, 0.0))

    print("✅ 布局已优化，标题与轴标签不再重叠。")
    plt.show()

if __name__ == '__main__':
    crank_slider_final_clean()