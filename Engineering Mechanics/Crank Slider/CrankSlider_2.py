import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# 设置绘图风格
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

def draw_textbook_style():
    # ================= 1. 机构参数设置 =================
    r = 1.0       # 曲柄半径 (轴 OA)
    L = 3.0       # 连杆长度 (轴 AB)
    omega = 2.0   # 角速度

    # 创建网格：时间 t 和 连杆上的位置 l1 (从A点到P点的距离)
    # 教材图表展示的是整根杆上所有点的集合
    t_vec = np.linspace(0, 2 * np.pi, 100)      # 一个周期的时间
    l1_vec = np.linspace(0, L, 50)              # 连杆上从 0 到 L 的所有点
    T, L1 = np.meshgrid(t_vec, l1_vec)

    # ================= 2. 运动学计算 =================
    # 曲柄销 A 的坐标
    Ax = r * np.cos(omega * T)
    Ay = r * np.sin(omega * T)

    # 滑块 B 的坐标 (y=0)
    # Bx = r*cos(phi) + sqrt(L^2 - (r*sin(phi))^2)
    Bx = Ax + np.sqrt(L**2 - Ay**2)
    
    # 连杆上任意一点 P 的坐标 (根据截长比公式)
    # P点在AB连线上，距离A为L1
    Px = Ax + (L1 / L) * (Bx - Ax)
    Py = Ay + (L1 / L) * (0 - Ay)  # 因为 By = 0

    # 计算 P 点的垂直速度 Vy (对时间求导)
    # Vy = d(Py)/dt = d/dt [ Ay * (1 - L1/L) ]
    # Ay = r * sin(omega * t) -> d(Ay)/dt = r * omega * cos(omega * t)
    Vpy = r * omega * np.cos(omega * T) * (1 - L1 / L)

    # ================= 3. 绘制图表 =================
    fig = plt.figure(figsize=(15, 7))

    # --- 左侧：还原图 7-17(a) 位置轨迹流形 ---
    ax1 = fig.add_subplot(121, projection='3d')
    # 注意教材坐标轴：X=xp, Y=l1, Z=yp
    surf1 = ax1.plot_surface(Px, L1, Py, cmap='viridis', alpha=0.8, edgecolor='none')
    ax1.set_title('图 7-17(a): 连杆点 P 的位置轨迹流形', pad=20)
    ax1.set_xlabel('$x_p / m$')
    ax1.set_ylabel('$l_1 / m$')
    ax1.set_zlabel('$y_p / m$')
    # 调整视角还原教材观感
    ax1.view_init(elev=30, azim=-120)

    # --- 右侧：还原图 7-18 速度轨迹流形 ---
    ax2 = fig.add_subplot(122, projection='3d')
    # 注意教材坐标轴：X=t, Y=l1, Z=v_py
    surf2 = ax2.plot_surface(T, L1, Vpy, cmap='coolwarm', alpha=0.8, edgecolor='none')
    ax2.set_title('图 7-18: 连杆点 P 的速度流形', pad=20)
    ax2.set_xlabel('$t / s$')
    ax2.set_ylabel('$l_1 / m$')
    ax2.set_zlabel('$v_{py} / (m/s)$')
    # 调整视角还原教材观感
    ax2.view_init(elev=30, azim=-140)

    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    draw_textbook_style()