import numpy as np
import matplotlib.pyplot as plt

# --- 设置中文字体，防止图中中文显示为方块 ---
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# --- 1. 机构几何参数设计 ---
L1 = 100.0   # 固定杆 AB (机架)
L4 = 100.0   # 摇杆 BD
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

# --- 2. 收集全周期的运动数据 ---
C_path_x, C_path_y = [], []
D_path_x, D_path_y = [], []
all_states = []

for deg in range(360):
    theta2 = np.radians(deg)
    res = solve_kinematics(theta2)
    if res:
        A, B, C, D, ang = res
        C_path_x.append(C[0])
        C_path_y.append(C[1])
        D_path_x.append(D[0])
        D_path_y.append(D[1])
        all_states.append({'deg': deg, 'A': A, 'B': B, 'C': C, 'D': D, 'ang': ang})

# 找出BD杆摆角的极小值和极大值（极限位置）
min_state = min(all_states, key=lambda s: s['ang'])
max_state = max(all_states, key=lambda s: s['ang'])

# --- 3. 静态绘图与渲染 ---
fig, ax = plt.subplots(figsize=(10, 7), dpi=150) # 提高 dpi 使图像更清晰
ax.set_aspect('equal')
ax.set_xlim(-80, 220)
ax.set_ylim(-80, 160)
ax.grid(True, linestyle='--', alpha=0.6)

# 绘制固定支座及水平基准线
ax.plot([0], [0], 'ks', markersize=8, zorder=5, label='支座 A/B')
ax.plot([L1], [0], 'ks', markersize=8, zorder=5)
ax.axhline(0, color='gray', lw=1, ls=':', zorder=1) 

# 绘制轨迹线
ax.plot(C_path_x, C_path_y, 'g--', alpha=0.5, lw=1.5, label='曲柄 C 点轨迹', zorder=2)
ax.plot(D_path_x, D_path_y, 'r--', alpha=0.5, lw=1.5, label='摇杆 D 点轨迹', zorder=2)

# 绘制运动过程中的“残影”（每 15 度画一次）
for state in all_states[::15]:
    A, B, C, D = state['A'], state['B'], state['C'], state['D']
    ax.plot([A[0], C[0], D[0], B[0]], [A[1], C[1], D[1], B[1]], 
            color='gray', alpha=0.15, lw=1.5, zorder=3)

# 绘制并高亮两个极限位置
# 极限位置 1 (近似 0°)
A, B, C, D = min_state['A'], min_state['B'], min_state['C'], min_state['D']
ax.plot([A[0], C[0], D[0], B[0]], [A[1], C[1], D[1], B[1]], 
        'o-', color='#2980b9', lw=3, mfc='white', mew=2, zorder=4, 
        label=f"极限位置 1 (BD={min_state['ang']:.1f}°)")

# 极限位置 2 (近似 135°)
A, B, C, D = max_state['A'], max_state['B'], max_state['C'], max_state['D']
ax.plot([A[0], C[0], D[0], B[0]], [A[1], C[1], D[1], B[1]], 
        'o-', color='#e74c3c', lw=3, mfc='white', mew=2, zorder=4, 
        label=f"极限位置 2 (BD={max_state['ang']:.1f}°)")

# 添加角度标注文本
ax.text(min_state['D'][0] + 10, min_state['D'][1] - 5, f"{min_state['ang']:.1f}°", color='#2980b9', fontweight='bold')
ax.text(max_state['D'][0] - 30, max_state['D'][1] + 10, f"{max_state['ang']:.1f}°", color='#e74c3c', fontweight='bold')

plt.legend(loc='upper right', framealpha=0.9)
plt.title("曲柄摇杆机构运动极位分析 (BD摆角 0° - 135°)", pad=15, fontsize=14, fontweight='bold')
plt.tight_layout()

# 直接显示或保存为高分辨率 PNG
plt.show()
# 如果需要保存图片，可以将上一行注释掉，使用下一行：
# plt.savefig('four_bar_kinematics_static.png', dpi=300)
