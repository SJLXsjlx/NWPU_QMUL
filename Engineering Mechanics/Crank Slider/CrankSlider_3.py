import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm

# ================= 0. 全局样式优化 =================
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["SimHei", "Times New Roman"],
    "axes.unicode_minus": False,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.dpi": 120  # 提高分辨率
})

def draw_academic_style():
    # ================= 1. 机构参数设置 =================
    r = 1.0       # 曲柄半径
    L = 3.0       # 连杆长度
    omega = 1.0   # 角速度

    # 创建更高密度的网格以获得极致平滑度
    t_vec = np.linspace(0, 2 * np.pi, 150)
    l1_vec = np.linspace(0, L, 100)
    T, L1 = np.meshgrid(t_vec, l1_vec)

    # ================= 2. 运动学解算 =================
    # 位置解算
    Ax = r * np.cos(omega * T)
    Ay = r * np.sin(omega * T)
    Bx = Ax + np.sqrt(L**2 - Ay**2)
    
    # 连杆上点 P 的精确位置流形
    Px = Ax + (L1 / L) * (Bx - Ax)
    Py = Ay * (1 - L1 / L) # 因为 By = 0，简化后的比例关系

    # 速度解算 (垂直方向分速度 v_py)
    Vpy = r * omega * np.cos(omega * T) * (1 - L1 / L)

    # ================= 3. 绘图：图 7-17(a) 位置流形 =================
    fig1 = plt.figure(figsize=(10, 8))
    ax1 = fig1.add_subplot(111, projection='3d')
    
    # 核心：绘制带网格线的渐变曲面
    # rstride/cstride 控制网格线的疏密程度
    surf1 = ax1.plot_surface(Px, L1, Py, cmap='viridis', 
                             alpha=0.8, antialiased=True, 
                             rcount=50, ccount=50, # 采样率
                             shade=True, linewidth=0.1, edgecolors='#333333')
    
    # 增加底部等高线投影 (增强空间位置感)
    cset = ax1.contour(Px, L1, Py, zdir='z', offset=np.min(Py)-0.5, cmap='viridis', alpha=0.5)

    # 轴标签优化 (使用 LaTeX)
    ax1.set_title(r'$\mathbf{Fig\ 7-17(a)\ Trajectory\ Manifold\ of\ Point\ P}$', pad=20, fontsize=14)
    ax1.set_xlabel(r'$x_p\ \mathrm{(m)}$', labelpad=10)
    ax1.set_ylabel(r'$l_1\ \mathrm{(m)}$', labelpad=10)
    ax1.set_zlabel(r'$y_p\ \mathrm{(m)}$', labelpad=10)
    
    # 固定 Z 轴范围，防止投影被切断
    ax1.set_zlim(np.min(Py)-0.5, np.max(Py)+0.2)
    ax1.view_init(elev=28, azim=-125)
    fig1.colorbar(surf1, ax=ax1, shrink=0.5, aspect=20, pad=0.1)

    # ================= 4. 绘图：图 7-18 速度流形 =================
    fig2 = plt.figure(figsize=(10, 8))
    ax2 = fig2.add_subplot(111, projection='3d')
    
    # 核心：绘制速度曲面，采用 coolwarm 色图（冷暖色代表速度正负）
    surf2 = ax2.plot_surface(T, L1, Vpy, cmap='coolwarm', 
                             alpha=0.9, antialiased=True, 
                             rcount=60, ccount=60, 
                             shade=True, linewidth=0.05, edgecolors='gray')

    # 在 X-Y 平面投影网格
    ax2.contour(T, L1, Vpy, zdir='z', offset=np.min(Vpy)-0.2, cmap='coolwarm', alpha=0.3)

    ax2.set_title(r'$\mathbf{Fig\ 7-18\ Velocity\ Manifold\ of\ Point\ P}$', pad=20, fontsize=14)
    ax2.set_xlabel(r'$t\ \mathrm{(s)}$')
    ax2.set_ylabel(r'$l_1\ \mathrm{(m)}$')
    ax2.set_zlabel(r'$v_{py}\ \mathrm{(m/s)}$')
    
    ax2.view_init(elev=25, azim=-135)
    fig2.colorbar(surf2, ax=ax2, shrink=0.5, aspect=20, pad=0.1)

    # 调整整体布局
    fig1.tight_layout()
    fig2.tight_layout()
    
    print("✨ 高清图片已生成！你可以手动旋转 3D 图表以观察最佳角度。")
    plt.show()

if __name__ == '__main__':
    draw_academic_style()