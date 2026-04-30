import numpy as np
import matplotlib.pyplot as plt

# 解决图表中的中文显示问题 (兼容 Windows 和 macOS)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

def simulate_crank_slider():
    # ================= 1. 机构参数设置 =================
    r = 2.0       # 曲柄长度
    l = 6.0       # 连杆长度 (要求 l > r)
    omega = 2.0   # 曲柄角速度 (rad/s)
    
    # 定义连杆上任意一点 P 的局部位置 (以曲柄销 A 为原点，AB方向为x轴)
    d1 = 3.0      # 点P沿连杆AB方向的距离
    d2 = 1.5      # 点P垂直于连杆AB方向的偏移量
    
    # 模拟时间：旋转两圈
    t = np.linspace(0, 4 * np.pi / omega, 500)
    
    # ================= 2. 运动学位置计算 =================
    # 曲柄销A的坐标
    Ax = r * np.cos(omega * t)
    Ay = r * np.sin(omega * t)
    
    # 滑块B的坐标 (假设滑块在 y=0 的X轴上运动)
    # 根据几何关系：(Bx - Ax)^2 + (By - Ay)^2 = l^2, By = 0
    Bx = Ax + np.sqrt(l**2 - Ay**2)
    By = np.zeros_like(t)
    
    # 计算连杆AB的角度方向 (单位向量)
    cos_phi = (Bx - Ax) / l
    sin_phi = (By - Ay) / l
    
    # 计算连杆上任一点 P 的绝对坐标
    Px = Ax + d1 * cos_phi - d2 * sin_phi
    Py = Ay + d1 * sin_phi + d2 * cos_phi
    
    # ================= 3. 速度计算 =================
    # 采用数值求导计算 P 点的 X 和 Y 方向速度
    Vx = np.gradient(Px, t)
    Vy = np.gradient(Py, t)
    V_mag = np.sqrt(Vx**2 + Vy**2) # 速度总大小
    
    # ================= 4. 可视化绘图 =================
    fig = plt.figure(figsize=(16, 5))
    
    # --- 子图 1: 机构示意与二维轨迹 ---
    ax1 = fig.add_subplot(131)
    idx = 40  # 选取一个特定时刻展示机构姿态
    ax1.plot(Px, Py, 'g--', alpha=0.7, label='点P二维轨迹')
    ax1.plot([0, Ax[idx]], [0, Ay[idx]], 'b-', linewidth=4, label='曲柄')
    ax1.plot([Ax[idx], Bx[idx]], [Ay[idx], By[idx]], 'r-', linewidth=4, label='连杆')
    ax1.plot(Bx[idx], By[idx], 'ks', markersize=12, label='滑块')
    ax1.plot(Px[idx], Py[idx], 'mo', markersize=8, label='目标点P')
    
    ax1.set_aspect('equal')
    ax1.set_title('曲柄滑块机构瞬时状态')
    ax1.set_xlabel('X位置')
    ax1.set_ylabel('Y位置')
    ax1.grid(True)
    ax1.legend()

    # --- 子图 2: 点P的 三维位置轨迹 (X-Y-Time) ---
    ax2 = fig.add_subplot(132, projection='3d')
    ax2.plot(Px, Py, t, 'm-', linewidth=2)
    ax2.set_title('连杆点P 三维位置轨迹')
    ax2.set_xlabel('X位置')
    ax2.set_ylabel('Y位置')
    ax2.set_zlabel('时间 t (s)')
    
    # --- 子图 3: 点P的 三维速度轨迹 (Vx-Vy-Time) ---
    ax3 = fig.add_subplot(133, projection='3d')
    # 使用散点映射颜色来反映速度大小
    sc = ax3.scatter(Vx, Vy, t, c=V_mag, cmap='jet', s=15, alpha=0.8)
    ax3.plot(Vx, Vy, t, color='gray', alpha=0.3) # 添加辅助连线
    ax3.set_title('连杆点P 三维速度轨迹')
    ax3.set_xlabel('X方向速度 Vx')
    ax3.set_ylabel('Y方向速度 Vy')
    ax3.set_zlabel('时间 t (s)')
    fig.colorbar(sc, ax=ax3, label='速度幅值 |V|', pad=0.1)
    
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    simulate_crank_slider()