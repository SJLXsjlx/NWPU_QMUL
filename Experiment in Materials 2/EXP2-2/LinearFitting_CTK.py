import customtkinter as ctk
from tkinter import messagebox
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
import matplotlib as mpl

# UI 环境配置
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class RobustPhysicsAnalyzer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("实验数据高精度分析系统 (Academic Pro V3)")
        self.geometry("980x900")
        self.setup_ui()

    def setup_ui(self):
        # 1. 原始数据与数据转换
        frame_data = ctk.CTkFrame(self)
        frame_data.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(frame_data, text="1. 实验数据与函数变换", font=("Microsoft YaHei", 15, "bold")).pack(anchor="w", padx=15, pady=5)
        
        self.entry_x = self.create_input(frame_data, "X 轴原始数据序列 (逗号/空格分隔):", "")
        self.trans_x = self.create_input(frame_data, "X 轴数据变换式 (支持 numpy, 例如: 1/x, np.log(x)):", "x")
        
        self.entry_y = self.create_input(frame_data, "Y 轴原始数据序列 (逗号/空格分隔):", "")
        self.trans_y = self.create_input(frame_data, "Y 轴数据变换式 (支持 numpy, 例如: y**2, np.sqrt(y)):", "y")

        # 2. 坐标轴参数与不确定度分量
        frame_meta = ctk.CTkFrame(self)
        frame_meta.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(frame_meta, text="2. 物理量信息与不确定度分量 (均可留空，留空视为0)", font=("Microsoft YaHei", 15, "bold")).pack(anchor="w", padx=15, pady=5)
        
        row_x = ctk.CTkFrame(frame_meta, fg_color="transparent")
        row_x.pack(fill="x", padx=15, pady=5)
        self.x_name = self.create_inline(row_x, "X轴物理符号:", "", 65)
        self.x_unit = self.create_inline(row_x, "单位:", "", 65)
        self.x_ua = self.create_inline(row_x, "u_A:", "", 70)
        self.x_ub = self.create_inline(row_x, "u_B:", "", 70)
        self.x_uc = self.create_inline(row_x, "u_C:", "", 70)

        row_y = ctk.CTkFrame(frame_meta, fg_color="transparent")
        row_y.pack(fill="x", padx=15, pady=5)
        self.y_name = self.create_inline(row_y, "Y轴物理符号:", "", 65)
        self.y_unit = self.create_inline(row_y, "单位:", "", 65)
        self.y_ua = self.create_inline(row_y, "u_A:", "", 70)
        self.y_ub = self.create_inline(row_y, "u_B:", "", 70)
        self.y_uc = self.create_inline(row_y, "u_C:", "", 70)

        # 3. 计算选项
        frame_opt = ctk.CTkFrame(self)
        frame_opt.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(frame_opt, text="3. 拟合模型设置", font=("Microsoft YaHei", 15, "bold")).pack(anchor="w", padx=15, pady=5)
        
        self.var_fit = ctk.StringVar(value="linear")
        ctk.CTkRadioButton(frame_opt, text="一般线性拟合 (y = kx + b)", variable=self.var_fit, value="linear").pack(side="left", padx=20, pady=10)
        ctk.CTkRadioButton(frame_opt, text="强制过原点拟合 (y = kx)", variable=self.var_fit, value="origin").pack(side="left", padx=15, pady=10)
        
        self.var_errorbar = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(frame_opt, text="图表绘制误差棒", variable=self.var_errorbar).pack(side="left", padx=20)

        # 4. 按钮
        ctk.CTkButton(self, text="执行学术分析并导出图表", height=45, font=("Microsoft YaHei", 14, "bold"), 
                      command=self.execute_analysis).pack(pady=10, padx=20, fill="x")

        # 5. 文本输出
        self.output_box = ctk.CTkTextbox(self, font=("Consolas", 13), height=250)
        self.output_box.pack(padx=20, pady=(0, 20), fill="both", expand=True)

    def create_input(self, master, label, default):
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=2)
        ctk.CTkLabel(row, text=label, width=300, anchor="e").pack(side="left", padx=(0, 10))
        e = ctk.CTkEntry(row)
        e.insert(0, default)
        e.pack(side="left", fill="x", expand=True)
        return e

    def create_inline(self, master, label, default, width):
        ctk.CTkLabel(master, text=label).pack(side="left", padx=5)
        e = ctk.CTkEntry(master, width=width)
        e.insert(0, default)
        e.pack(side="left", padx=10)
        return e

    def parse_list(self, raw_str):
        import re
        clean_str = re.sub(r'[，\s]+', ',', raw_str.strip())
        return np.array([float(i) for i in clean_str.split(',') if i], dtype=np.float64)

    def safe_float(self, val):
        try:
            return float(val) if val.strip() else 0.0
        except ValueError:
            return 0.0

    def execute_analysis(self):
        try:
            # 1. 解析与转换数据
            x_raw = self.parse_list(self.entry_x.get())
            y_raw = self.parse_list(self.entry_y.get())
            
            if len(x_raw) != len(y_raw) or len(x_raw) < 2:
                messagebox.showwarning("数据错误", "数据长度不一致或点数过少 (<2)。")
                return

            safe_dict = {"np": np, "x": x_raw, "y": y_raw}
            x_data = eval(self.trans_x.get(), {"__builtins__": None}, safe_dict)
            y_data = eval(self.trans_y.get(), {"__builtins__": None}, safe_dict)

            # 2. 读取并计算合成不确定度 (直接由用户输入)
            ua_x = self.safe_float(self.x_ua.get())
            ub_x = self.safe_float(self.x_ub.get())
            uc_x = self.safe_float(self.x_uc.get())
            u_x = np.sqrt(ua_x**2 + ub_x**2 + uc_x**2)

            ua_y = self.safe_float(self.y_ua.get())
            ub_y = self.safe_float(self.y_ub.get())
            uc_y = self.safe_float(self.y_uc.get())
            u_y = np.sqrt(ua_y**2 + ub_y**2 + uc_y**2)

            # 3. 严谨的曲线拟合 (基于 scipy.optimize)
            def model_linear(x, k, b): return k * x + b
            def model_origin(x, k): return k * x

            if self.var_fit.get() == "linear":
                popt, pcov = curve_fit(model_linear, x_data, y_data)
                k, b = popt
                u_k, u_b = np.sqrt(np.diag(pcov)) 
                y_fit = model_linear(x_data, k, b)
                eq_str = f"y = {k:.4e}x {'+' if b>=0 else '-'} {abs(b):.4e}"
            else:
                popt, pcov = curve_fit(model_origin, x_data, y_data)
                k = popt[0]
                b = 0.0
                u_k = np.sqrt(pcov[0][0])
                u_b = 0.0
                y_fit = model_origin(x_data, k)
                eq_str = f"y = {k:.4e}x"

            # 计算 R² (判定系数)
            ss_res = np.sum((y_data - y_fit)**2)
            ss_tot = np.sum((y_data - np.mean(y_data))**2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 1

            # 4. 报告生成
            rep = "【学术实验严谨分析报告】\n" + "="*65 + "\n"
            rep += f"数学变换: X -> {self.trans_x.get()} | Y -> {self.trans_y.get()}\n"
            rep += "-"*65 + "\n"
            rep += f"拟合方程: {eq_str}\n"
            rep += f"判定系数 (R²): {r2:.8f}\n\n"
            rep += "[拟合参数不确定度 (基于协方差矩阵)]\n"
            rep += f"斜率 k = {k:.6e} ± {u_k:.6e}\n"
            if self.var_fit.get() == "linear":
                rep += f"截距 b = {b:.6e} ± {u_b:.6e}\n"
            rep += "\n[合成标准不确定度分析 (直接输入合成)]\n"
            rep += f"X轴 ({self.x_name.get() or 'X'}): u_A={ua_x:.4e}, u_B={ub_x:.4e}, u_C={uc_x:.4e} => 合成U={u_x:.4e}\n"
            rep += f"Y轴 ({self.y_name.get() or 'Y'}): u_A={ua_y:.4e}, u_B={ub_y:.4e}, u_C={uc_y:.4e} => 合成U={u_y:.4e}\n"
            rep += "="*65 + "\n"
            
            self.output_box.delete("1.0", "end")
            self.output_box.insert("end", rep)

            # --- 5. 学术级绘图配置 (最终稳健版) ---
            # 设置全局字体，解决中文乱码
            mpl.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
            mpl.rcParams['axes.unicode_minus'] = False 
            mpl.rcParams.update({
                'mathtext.fontset': 'stix', # 使用学术期刊常用的 STIX 字体渲染数学公式
                'xtick.direction': 'in', 'ytick.direction': 'in',
                'xtick.top': True, 'ytick.right': True,
                'axes.linewidth': 1.2
            })

            fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=120)
            
            # --- 核心：定义科学计数法转 LaTeX 的稳健函数 ---
            def to_tex(num):
                # 强制转换为 4 位精度的科学计数法字符串，如 "4.7196e-02"
                s = "{:.4e}".format(num)
                if "e" in s:
                    base, exp = s.split("e")
                    # int(exp) 会去掉 -02 里的 0 变成 -2
                    return f"{base} \\times 10^{{{int(exp)}}}"
                return s

            # 绘制数据点
            if self.var_errorbar.get() and (u_x > 0 or u_y > 0):
                ax.errorbar(x_data, y_data, xerr=u_x, yerr=u_y, fmt='o', 
                            color='black', ecolor='gray', elinewidth=1, capsize=3, 
                            markerfacecolor='none', markersize=6, label='实验点 (带误差棒)', zorder=3)
            else:
                ax.scatter(x_data, y_data, facecolors='none', edgecolors='black', s=50, label='实验点', zorder=3)
            
            # 拟合直线计算
            x_line = np.linspace(min(x_data) - abs(min(x_data)*0.05), max(x_data) * 1.05, 200)
            y_line = k * x_line + b
            
            # --- 核心：构造图例标签，不使用 .replace() ---
            # 将斜率 k 和截距 b 分别转换，然后手动拼接
            k_tex = to_tex(k)
            b_tex = to_tex(abs(b))
            sign = "+" if b >= 0 else "-"
            
            # 拼接完整的 LaTeX 表达式
            fit_label = f'$y = ({k_tex})x {sign} ({b_tex})$'
            
            ax.plot(x_line, y_line, 'r-', linewidth=1.5, 
                    label=f'拟合: {fit_label}\n$R^2 = {r2:.4f}$')

            # 坐标轴标签处理
            def get_axis_label(name_ent, unit_ent, trans_str):
                name = name_ent.get() or "Axis"
                unit = unit_ent.get() or ""
                # 如果做了变换，在标签上显示
                if trans_str != "x" and trans_str != "y":
                    label = f"${trans_str.replace('np.', '')}$"
                else:
                    label = f"${name}$"
                return f"{label} / {unit}" if unit else label

            ax.set_xlabel(get_axis_label(self.x_name, self.x_unit, self.trans_x.get()), fontsize=13)
            ax.set_ylabel(get_axis_label(self.y_name, self.y_unit, self.trans_y.get()), fontsize=13)
            
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.legend(frameon=True, edgecolor='black')
            plt.tight_layout()
            plt.show()

        except Exception as e:
            messagebox.showerror("运行错误", f"计算或绘图时发生异常:\n{str(e)}")
            
            # 绘制误差棒与数据点
            if self.var_errorbar.get() and (u_x > 0 or u_y > 0):
                ax.errorbar(x_data, y_data, xerr=u_x, yerr=u_y, fmt='o', 
                            color='black', ecolor='gray', elinewidth=1, capsize=3, 
                            markerfacecolor='none', markersize=6, label='实验点 (带误差棒)', zorder=3)
            else:
                ax.scatter(x_data, y_data, facecolors='none', edgecolors='black', s=50, label='实验点', zorder=3)
            
            # 绘制拟合直线
            x_line = np.linspace(min(x_data) - abs(min(x_data)*0.05), max(x_data) * 1.05, 200)
            y_line = model_linear(x_line, k, b) if self.var_fit.get() == "linear" else model_origin(x_line, k)
            
            ax.plot(x_line, y_line, 'r-', linewidth=1.5, 
                    label=f'拟合: ${eq_str.replace("e", "\\times 10^{").replace("+", "} +").replace("-", "} -")}$ \n$R^2 = {r2:.4f}$')

            def format_label(name, unit, trans):
                base = f"{name}" if name else ""
                u_str = f" / {unit}" if unit else ""
                if trans not in ['x', 'y'] and base:
                    if trans == '1/x' or trans == '1/y': base = f"1/{base}"
                    elif 'np.log' in trans: base = f"\\ln({base})"
                    elif '**2' in trans: base = f"{base}^2"
                return f"${base}{u_str}$" if base or u_str else ""

            ax.set_xlabel(format_label(self.x_name.get(), self.x_unit.get(), self.trans_x.get()), fontsize=13)
            ax.set_ylabel(format_label(self.y_name.get(), self.y_unit.get(), self.trans_y.get()), fontsize=13)
            
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.legend(frameon=True, edgecolor='black')
            plt.tight_layout()
            plt.show()

        except Exception as e:
            messagebox.showerror("运行错误", f"计算或绘图时发生异常:\n{str(e)}")

if __name__ == "__main__":
    RobustPhysicsAnalyzer().mainloop()
