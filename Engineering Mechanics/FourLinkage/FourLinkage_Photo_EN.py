import numpy as np
import matplotlib.pyplot as plt

# --- 1. Mechanism Geometric Parameters Design ---
L1 = 100.0   # Fixed link AB (Frame)
L4 = 100.0   # Rocker BD
L2 = 61.73   # Crank AC
L3 = 138.27  # Coupler CD

def solve_kinematics(theta2):
    """
    Calculate the coordinates of each joint
    """
    Ax, Ay = 0, 0
    Bx, By = L1, 0
    
    # Coordinates of point C (Crank)
    Cx = L2 * np.cos(theta2)
    Cy = L2 * np.sin(theta2)
    
    # Calculate the distance from C to B
    dist_CB = np.sqrt((Bx - Cx)**2 + (By - Cy)**2)
    
    # Geometric interference check
    if dist_CB > (L3 + L4) or dist_CB < abs(L3 - L4):
        return None
    
    # Use the Law of Cosines to calculate angle ∠DBC
    cos_val = (L4**2 + dist_CB**2 - L3**2) / (2 * L4 * dist_CB)
    cos_val = np.clip(cos_val, -1.0, 1.0)
    angle_DBC = np.arccos(cos_val)
    
    # Base angle of vector CB
    beta = np.arctan2(Cy - By, Cx - Bx)
    
    # Coordinates of point D (Choose the upper branch to achieve 0-135 degree swing)
    theta4 = beta - angle_DBC
    Dx = Bx + L4 * np.cos(theta4)
    Dy = By + L4 * np.sin(theta4)
    
    # Calculate the actual angle of link BD (0 degrees is horizontal to the right)
    current_angle = np.degrees(np.arctan2(Dy - By, Dx - Bx))
    if current_angle < 0: current_angle += 360
    
    return (Ax, Ay), (Bx, By), (Cx, Cy), (Dx, Dy), current_angle

# --- 2. Collect motion data for the full cycle ---
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

# Find the minimum and maximum swing angles of link BD (extreme positions)
min_state = min(all_states, key=lambda s: s['ang'])
max_state = max(all_states, key=lambda s: s['ang'])

# --- 3. Static Plotting and Rendering ---
fig, ax = plt.subplots(figsize=(10, 7), dpi=150) # Increase dpi for clearer image
ax.set_aspect('equal')
ax.set_xlim(-80, 220)
ax.set_ylim(-80, 160)
ax.grid(True, linestyle='--', alpha=0.6)

# Plot fixed pivots and horizontal reference line
ax.plot([0], [0], 'ks', markersize=8, zorder=5, label='Fixed Pivot A/B')
ax.plot([L1], [0], 'ks', markersize=8, zorder=5)
ax.axhline(0, color='gray', lw=1, ls=':', zorder=1) 

# Plot trajectory lines
ax.plot(C_path_x, C_path_y, 'g--', alpha=0.5, lw=1.5, label='Crank C Trajectory', zorder=2)
ax.plot(D_path_x, D_path_y, 'r--', alpha=0.5, lw=1.5, label='Rocker D Trajectory', zorder=2)

# Plot "afterimages" during motion (draw every 15 degrees)
for state in all_states[::15]:
    A, B, C, D = state['A'], state['B'], state['C'], state['D']
    ax.plot([A[0], C[0], D[0], B[0]], [A[1], C[1], D[1], B[1]], 
            color='gray', alpha=0.15, lw=1.5, zorder=3)

# Plot and highlight the two extreme positions
# Extreme Position 1 (Approx. 0°)
A, B, C, D = min_state['A'], min_state['B'], min_state['C'], min_state['D']
ax.plot([A[0], C[0], D[0], B[0]], [A[1], C[1], D[1], B[1]], 
        'o-', color='#2980b9', lw=3, mfc='white', mew=2, zorder=4, 
        label=f"Extreme Position 1 (BD={min_state['ang']:.1f}°)")

# Extreme Position 2 (Approx. 135°)
A, B, C, D = max_state['A'], max_state['B'], max_state['C'], max_state['D']
ax.plot([A[0], C[0], D[0], B[0]], [A[1], C[1], D[1], B[1]], 
        'o-', color='#e74c3c', lw=3, mfc='white', mew=2, zorder=4, 
        label=f"Extreme Position 2 (BD={max_state['ang']:.1f}°)")

# Add angle annotation text
ax.text(min_state['D'][0] + 10, min_state['D'][1] - 5, f"{min_state['ang']:.1f}°", color='#2980b9', fontweight='bold')
ax.text(max_state['D'][0] - 30, max_state['D'][1] + 10, f"{max_state['ang']:.1f}°", color='#e74c3c', fontweight='bold')

plt.legend(loc='upper right', framealpha=0.9)
plt.title("Kinematic Extreme Position Analysis of Crank-Rocker Mechanism (BD Swing 0° - 135°)", pad=15, fontsize=14, fontweight='bold')
plt.tight_layout()

# Display directly or save as high-resolution PNG
plt.show()
# If you need to save the image, comment out the line above and use the line below:
# plt.savefig('four_bar_kinematics_static.png', dpi=300)