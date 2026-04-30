import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# 参数设置
r = 0.5      # 曲柄半径 (m)
l = 1.5      # 连杆长度 (m)
omega = 2.0  # 角速度 (rad/s)
t = np.linspace(0, 2 * np.pi / omega, 100)  # 一个完整周期
l1_range = np.linspace(0, l, 50)            # 连杆上点 P 的位置分布

# 准备绘图数据
T, L1 = np.meshgrid(t, l1_range)

# 计算轨迹 (x, y)
# 使用精确运动学方程以获得更好的视觉效果
theta = omega * T
phi = np.arcsin((r / l) * np.sin(theta)) # 连杆倾角

x_P = r * np.cos(theta) + L1 * np.cos(phi)
y_P = r * np.sin(theta) - L1 * np.sin(phi)

# 计算速度 (vx, vy)
v_px = -r * omega * (np.sin(theta) + (r * L1 * np.sin(2 * theta)) / (2 * l**2 * np.cos(phi)**3))
v_py = r * omega * np.cos(theta) - (L1 * r * omega * np.cos(theta)) / (l * np.cos(phi))
v_total = np.sqrt(v_px**2 + v_py**2)

# --- 绘图 ---
fig = plt.figure(figsize=(14, 6))

# 图1：连杆上任一点的轨迹随位置 l1 的变化 (类似 Fig 7-17)
ax1 = fig.add_subplot(121, projection='3d')
ax1.plot_surface(x_P, y_P, L1, cmap='viridis', alpha=0.8)
ax1.set_title('Trajectory of Point P along Connecting Rod')
ax1.set_xlabel('x_p (m)')
ax1.set_ylabel('y_p (m)')
ax1.set_zlabel('l1 (Position on rod)')

# 图2：连杆上任一点的速度分布 (类似 Fig 7-18)
ax2 = fig.add_subplot(122, projection='3d')
ax2.plot_surface(T, L1, v_total, cmap='magma', alpha=0.8)
ax2.set_title('Velocity Distribution of Point P')
ax2.set_xlabel('Time (s)')
ax2.set_ylabel('l1 (Position on rod)')
ax2.set_zlabel('Velocity (m/s)')

plt.tight_layout()
plt.show()