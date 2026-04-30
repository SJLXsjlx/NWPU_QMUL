import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# --- 1. 机构几何参数设计 ---
# 目标：BD摆角从 0° (与AB共线向右) 到 135°
L1 = 100.0   # 固定杆 AB (机架)
L4 = 100.0   # 摇杆 BD
# 根据几何极限位置推导出的精确值
L2 = 61.73   # 曲柄 AC
L3 = 138.27  # 连杆 CD


def solve_kinematics(theta2):
    """
    求解各关节点坐标
    """
    Ax, Ay = 0, 0
    Bx, By = L1, 0
    
    # C点坐标 (曲柄)
    Cx = L2 * np.cos(theta2)
    Cy = L2 * np.sin(theta2)
    
    # 计算 C 到 B 的距离
    dist_CB = np.sqrt((Bx - Cx)**2 + (By - Cy)**2)
    
    # 几何干涉检查
    if dist_CB > (L3 + L4) or dist_CB < abs(L3 - L4):
        return None
    
    # 余弦定理求角 ∠DBC
    cos_val = (L4**2 + dist_CB**2 - L3**2) / (2 * L4 * dist_CB)
    cos_val = np.clip(cos_val, -1.0, 1.0)
    angle_DBC = np.arccos(cos_val)
    
    # 向量 CB 的基础角度
    beta = np.arctan2(Cy - By, Cx - Bx)
    
    # D点坐标 (选择上方分路实现 0-135度摆动)
    theta4 = beta - angle_DBC
    Dx = Bx + L4 * np.cos(theta4)
    Dy = By + L4 * np.sin(theta4)
    
    # 计算BD杆的实际角度 (0度为水平向右)
    current_angle = np.degrees(np.arctan2(Dy - By, Dx - Bx))
    if current_angle < 0: current_angle += 360
    
    return (Ax, Ay), (Bx, By), (Cx, Cy), (Dx, Dy), current_angle

# --- 2. 动画与绘图设置 ---
fig, ax = plt.subplots(figsize=(10, 7))
ax.set_aspect('equal')
ax.set_xlim(-80, 220)
ax.set_ylim(-60, 140)
ax.grid(True, linestyle='--', alpha=0.5)

# 装饰物：绘制固定支座符号
ax.plot([0], [0], 'ks', markersize=10, label='支座 A')
ax.plot([L1], [0], 'ks', markersize=10, label='支座 B')
ax.axhline(0, color='gray', lw=1, ls=':') # 水平基准线

line, = ax.plot([], [], 'o-', lw=4, color='#2980b9', mfc='white', mew=2, label='机构连杆')
trace, = ax.plot([], [], 'r-', alpha=0.3, lw=1.5)
text_info = ax.text(-70, 120, '', fontsize=12, family='monospace', fontweight='bold')

history_x, history_y = [], []

def init():
    line.set_data([], [])
    trace.set_data([], [])
    text_info.set_text('')
    return line, trace, text_info

def animate(frame):
    theta2 = np.radians(frame)
    res = solve_kinematics(theta2)
    
    if res:
        (A, B, C, D, ang) = res
        # 连杆路径: A -> C -> D -> B
        line.set_data([A[0], C[0], D[0], B[0]], [A[1], C[1], D[1], B[1]])
        
        # 记录D点轨迹
        history_x.append(D[0])
        history_y.append(D[1])
        trace.set_data(history_x[-100:], history_y[-100:])
        
        text_info.set_text(f'曲柄 AC 角度: {frame:>3}°\n摇杆 BD 角度: {ang:>5.1f}°')
    
    return line, trace, text_info

# --- 3. 生成动画 ---
# frames=360 表示旋转一整圈
ani = FuncAnimation(fig, animate, frames=range(0, 360, 2), 
                    init_func=init, blit=True, interval=30)

# --- 4. 导出 GIF ---
save_name = r'D:\.NWPU_QMUL\工程力学\four_bar_linkage.gif'
print(f"正在保存动画至 {save_name}，请稍候...")
# fps 控制播放速度，writer 使用 pillow
ani.save(save_name, writer='pillow', fps=30)
print("保存成功！")

plt.legend(loc='lower right')
plt.title("四连杆机构运动仿真：BD杆 (0° - 135°)")
plt.show()