# ui.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinterdnd2 import DND_FILES
from pathlib import Path
import shutil
import threading
import os 

# 导入自定义模块
import processing
from utils import Logger

class App(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.master.title("Unity Modding 工具集")
        self.master.geometry("1200x900") # 稍微调大窗口高度
        self.master.configure(bg='#f5f5f5')
        
        # --- Tab 1 & 2 变量 ---
        self.png_bundle_path = None
        self.png_folder_path = None
        self.png_output_path = tk.StringVar()
        self.b2b_new_bundle_path = None
        self.b2b_old_bundle_path = None
        self.b2b_output_path = tk.StringVar()

        # --- Tab 3 (CRC) 变量 ---
        self.crc_original_path = None
        self.crc_modified_path = None
        self.crc_enable_padding = tk.BooleanVar(value=False)
        
        # --- 共享变量 (CRC 和 一键更新 Tab) ---
        self.game_resource_dir = Path(r"D:\SteamLibrary\steamapps\common\BlueArchive\BlueArchive_Data\StreamingAssets\PUB\Resource\GameData\Windows")
        if not self.game_resource_dir.exists():
             self.game_resource_dir = Path.home()
        self.game_resource_dir_var = tk.StringVar(value=str(self.game_resource_dir))

        # --- Tab 4 (一键更新) 变量 ---
        self.mod_update_old_mod_path = None
        default_work_dir = Path.cwd() / "output"
        self.mod_update_work_dir_var = tk.StringVar(value=str(default_work_dir))
        self.mod_update_enable_padding = tk.BooleanVar(value=False)


        self.create_widgets()
        
        # 初始化 Logger
        self.logger = Logger(self.master, self.log_text, self.status_label)
        self.logger.status("准备就绪")

    def create_widgets(self):
        main_frame = tk.Frame(self.master, bg='#f5f5f5', padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        left_frame = tk.Frame(main_frame, bg='#f5f5f5')
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        style = ttk.Style()
        style.configure("TNotebook.Tab", font=("Microsoft YaHei", 10, "bold"), padding=[10, 5])
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.create_tab_update()
        self.create_tab_png()
        # self.create_tab_restore()
        self.create_tab_crc()


        right_frame = tk.Frame(main_frame, bg='#ffffff', relief=tk.RAISED, bd=2)
        right_frame.grid(row=0, column=1, sticky="nsew")
        self.create_log_area(right_frame)

        self.status_label = tk.Label(self.master, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                     font=("Microsoft YaHei", 9), bg="#34495e", fg="#ecf0f1", padx=10)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    # Tab 1 和 Tab 2 的创建函数
    def create_tab_png(self):
        png_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(png_tab, text="  PNG 文件夹替换  ")

        bundle_frame = self.create_file_drop_zone(png_tab, "1. 目标 Bundle 文件", self.drop_png_bundle, self.browse_png_bundle)
        self.png_bundle_label = bundle_frame.winfo_children()[0]

        folder_frame = self.create_folder_drop_zone(png_tab, "2. PNG 图片文件夹", self.drop_png_folder, self.browse_png_folder)
        self.png_folder_label = folder_frame.winfo_children()[0]

        output_frame = tk.LabelFrame(png_tab, text="3. 输出文件路径", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        output_frame.pack(fill=tk.X, pady=(10, 15))
        
        entry = tk.Entry(output_frame, textvariable=self.png_output_path, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)
        
        button = tk.Button(output_frame, text="另存为...", command=self.save_as_png_output, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack(side=tk.RIGHT)

        run_button = tk.Button(png_tab, text="开始替换", command=self.run_png_replacement_thread, font=("Microsoft YaHei", 12, "bold"), bg="#27ae60", fg="white", relief=tk.FLAT, padx=20, pady=10)
        run_button.pack(pady=20)

    def create_tab_restore(self):
        bundle_restore_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(bundle_restore_tab, text="  Bundle 到 Bundle 恢复  ")

        new_bundle_frame = self.create_file_drop_zone(bundle_restore_tab, "1. 新版 Bundle (待修改)", self.drop_b2b_new, self.browse_b2b_new)
        self.b2b_new_label = new_bundle_frame.winfo_children()[0]

        old_bundle_frame = self.create_file_drop_zone(bundle_restore_tab, "2. 旧版 Bundle (源文件)", self.drop_b2b_old, self.browse_b2b_old)
        self.b2b_old_label = old_bundle_frame.winfo_children()[0]

        output_frame = tk.LabelFrame(bundle_restore_tab, text="3. 输出文件路径", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        output_frame.pack(fill=tk.X, pady=(10, 15))
        
        entry = tk.Entry(output_frame, textvariable=self.b2b_output_path, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)
        
        button = tk.Button(output_frame, text="另存为...", command=self.save_as_b2b_output, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack(side=tk.RIGHT)

        run_button = tk.Button(bundle_restore_tab, text="开始恢复/替换", command=self.run_b2b_replacement_thread, font=("Microsoft YaHei", 12, "bold"), bg="#e67e22", fg="white", relief=tk.FLAT, padx=20, pady=10)
        run_button.pack(pady=20)
    
    # Tab 3 (CRC工具) 的创建函数
    def create_tab_crc(self):
        crc_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(crc_tab, text="  CRC 修正工具  ")

        path_frame = tk.LabelFrame(crc_tab, text="1. 原始文件 (用于CRC校验)", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=10)
        path_frame.pack(fill=tk.X, pady=(0, 10))

        path_entry_frame = tk.Frame(path_frame, bg='#ffffff')
        path_entry_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(path_entry_frame, text="自动寻找路径:", bg='#ffffff').pack(side=tk.LEFT)
        # 修改: 使用共享的变量 self.game_resource_dir_var
        path_entry = tk.Entry(path_entry_frame, textvariable=self.game_resource_dir_var, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        open_dir_button = tk.Button(path_entry_frame, text="📂", command=self.select_game_resource_directory, font=("Microsoft YaHei", 10), bg="#3498db", fg="white", relief=tk.FLAT, width=3)
        open_dir_button.pack(side=tk.LEFT, padx=(0, 5))
        open_explorer_button = tk.Button(path_entry_frame, text="📁", command=self.open_game_resource_in_explorer, font=("Microsoft YaHei", 10), bg="#9b59b6", fg="white", relief=tk.FLAT, width=3)
        open_explorer_button.pack(side=tk.LEFT)

        self.crc_original_label = tk.Label(path_frame, text="将原始文件拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=3, bg="#ecf0f1", fg="#34495e", font=("Microsoft YaHei", 9))
        self.crc_original_label.pack(fill=tk.X, pady=(8, 8))
        self.crc_original_label.drop_target_register(DND_FILES)
        self.crc_original_label.dnd_bind('<<Drop>>', self.drop_crc_original)
        
        browse_orig_btn = tk.Button(path_frame, text="浏览原始文件...", command=self.browse_crc_original, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        browse_orig_btn.pack()

        modified_frame = self.create_file_drop_zone(crc_tab, "2. 修改后文件 (待修正)", self.drop_crc_modified, self.browse_crc_modified)
        self.crc_modified_label = modified_frame.winfo_children()[0]

        options_frame = tk.LabelFrame(crc_tab, text="3. 选项与操作", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        options_frame.pack(fill=tk.X, pady=(0, 10))

        padding_checkbox = tk.Checkbutton(options_frame, text="添加私货", variable=self.crc_enable_padding, font=("Microsoft YaHei", 9), bg='#ffffff', fg="#34495e", selectcolor="#ecf0f1")
        padding_checkbox.pack(pady=5)

        button_frame = tk.Frame(options_frame, bg='#ffffff')
        button_frame.pack(fill=tk.X, pady=10)
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)

        run_button = tk.Button(button_frame, text="运行CRC修正", command=self.run_crc_correction_thread, font=("Microsoft YaHei", 10, "bold"), bg="#27ae60", fg="white", relief=tk.FLAT, padx=10, pady=5)
        run_button.grid(row=0, column=0, sticky="ew", padx=5)

        calc_button = tk.Button(button_frame, text="计算CRC值", command=self.calculate_crc_values_thread, font=("Microsoft YaHei", 10, "bold"), bg="#e67e22", fg="white", relief=tk.FLAT, padx=10, pady=5)
        calc_button.grid(row=0, column=1, sticky="ew", padx=5)

        replace_button = tk.Button(button_frame, text="替换原始文件", command=self.replace_original_file_thread, font=("Microsoft YaHei", 10, "bold"), bg="#e74c3c", fg="white", relief=tk.FLAT, padx=10, pady=5)
        replace_button.grid(row=0, column=2, sticky="ew", padx=5)

    # Tab 4 (一键更新) 的创建函数
    def create_tab_update(self):
        mod_update_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(mod_update_tab, text="  一键更新 Mod  ")

        # 1. 旧版 Mod 文件
        old_mod_frame = self.create_file_drop_zone(mod_update_tab, "1. 拖入旧版 Mod Bundle", self.drop_mod_update_old_mod, self.browse_mod_update_old_mod)
        self.mod_update_old_mod_label = old_mod_frame.winfo_children()[0]

        # 2. 游戏资源目录 (与CRC Tab共享)
        game_dir_frame = tk.LabelFrame(mod_update_tab, text="2. 游戏资源目录 (新版文件所在位置)", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=10)
        game_dir_frame.pack(fill=tk.X, pady=(0, 10))
        
        path_entry = tk.Entry(game_dir_frame, textvariable=self.game_resource_dir_var, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)
        
        open_dir_button = tk.Button(game_dir_frame, text="📂", command=self.select_game_resource_directory, font=("Microsoft YaHei", 10), bg="#3498db", fg="white", relief=tk.FLAT, width=3)
        open_dir_button.pack(side=tk.LEFT, padx=(0, 5))
        open_explorer_button = tk.Button(game_dir_frame, text="📁", command=self.open_game_resource_in_explorer, font=("Microsoft YaHei", 10), bg="#9b59b6", fg="white", relief=tk.FLAT, width=3)
        open_explorer_button.pack(side=tk.LEFT)

        work_dir_frame = tk.LabelFrame(mod_update_tab, text="3. 工作目录 (用于存放输出文件)", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=10)
        work_dir_frame.pack(fill=tk.X, pady=(0, 10))
        
        work_path_entry = tk.Entry(work_dir_frame, textvariable=self.mod_update_work_dir_var, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        work_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)
        
        work_open_dir_button = tk.Button(work_dir_frame, text="📂", command=self.select_mod_update_work_dir, font=("Microsoft YaHei", 10), bg="#3498db", fg="white", relief=tk.FLAT, width=3)
        work_open_dir_button.pack(side=tk.LEFT, padx=(0, 5))
        work_open_explorer_button = tk.Button(work_dir_frame, text="📁", command=self.open_mod_update_work_dir_in_explorer, font=("Microsoft YaHei", 10), bg="#9b59b6", fg="white", relief=tk.FLAT, width=3)
        work_open_explorer_button.pack(side=tk.LEFT)
        
        # 选项和操作
        options_frame = tk.LabelFrame(mod_update_tab, text="4. 选项与操作", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        options_frame.pack(fill=tk.X, pady=(10, 15))
        
        padding_checkbox = tk.Checkbutton(options_frame, text="添加私货 (CRC修正时)", variable=self.mod_update_enable_padding, font=("Microsoft YaHei", 9), bg='#ffffff', fg="#34495e", selectcolor="#ecf0f1")
        padding_checkbox.pack(pady=5)

        run_button = tk.Button(mod_update_tab, text="🚀 开始一键更新", command=self.run_mod_update_thread, font=("Microsoft YaHei", 12, "bold"), bg="#8e44ad", fg="white", relief=tk.FLAT, padx=20, pady=10)
        run_button.pack(pady=20)

    # --- 通用UI组件创建函数 ---
    def create_file_drop_zone(self, parent, title, drop_cmd, browse_cmd):
        frame = tk.LabelFrame(parent, text=title, font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        label = tk.Label(frame, text="将文件拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=4, bg="#ecf0f1", fg="#34495e", font=("Microsoft YaHei", 9))
        label.pack(fill=tk.X, pady=(0, 8))
        label.drop_target_register(DND_FILES)
        label.dnd_bind('<<Drop>>', drop_cmd)
        
        button = tk.Button(frame, text="浏览文件...", command=browse_cmd, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack()
        return frame

    def create_folder_drop_zone(self, parent, title, drop_cmd, browse_cmd):
        frame = tk.LabelFrame(parent, text=title, font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        label = tk.Label(frame, text="将文件夹拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=4, bg="#ecf0f1", fg="#34495e", font=("Microsoft YaHei", 9))
        label.pack(fill=tk.X, pady=(0, 8))
        label.drop_target_register(DND_FILES)
        label.dnd_bind('<<Drop>>', drop_cmd)
        
        button = tk.Button(frame, text="浏览文件夹...", command=browse_cmd, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack()
        return frame

    def create_log_area(self, parent):
        log_frame = tk.LabelFrame(parent, text="Log", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, bg="#2c3e50", fg="#ecf0f1", font=("宋体", 9), relief=tk.FLAT, bd=2, padx=10, pady=10)
        scrollbar = tk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview, bg="#34495e")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(state=tk.DISABLED)

    # --- 通用文件/文件夹设置函数 (无变化) ---
    def set_file_path(self, path_var_name, label_widget, path: Path, file_type_name, auto_output_func=None):
        setattr(self, path_var_name, path)
        label_widget.config(text=f"已选择: {path.name}", fg="#27ae60")
        self.logger.log(f"已加载 {file_type_name}: {path.name}")
        self.logger.status(f"已加载 {file_type_name}")
        if auto_output_func:
            auto_output_func()

    def set_folder_path(self, path_var_name, label_widget, path: Path, folder_type_name):
        setattr(self, path_var_name, path)
        label_widget.config(text=f"已选择: {path.name}", fg="#27ae60")
        self.logger.log(f"已加载 {folder_type_name}: {path.name}")
        self.logger.status(f"已加载 {folder_type_name}")
    
    # --- Tab 1 & 2 事件处理 (无变化) ---
    def drop_png_bundle(self, event): self.set_file_path('png_bundle_path', self.png_bundle_label, Path(event.data.strip('{}')), "目标 Bundle", self.auto_set_png_output)
    def browse_png_bundle(self):
        p = filedialog.askopenfilename(title="选择目标 Bundle 文件");
        if p: self.set_file_path('png_bundle_path', self.png_bundle_label, Path(p), "目标 Bundle", self.auto_set_png_output)
    
    def drop_png_folder(self, event): self.set_folder_path('png_folder_path', self.png_folder_label, Path(event.data.strip('{}')), "PNG 文件夹")
    def browse_png_folder(self):
        p = filedialog.askdirectory(title="选择 PNG 图片文件夹");
        if p: self.set_folder_path('png_folder_path', self.png_folder_label, Path(p), "PNG 文件夹")

    def auto_set_png_output(self):
        if self.png_bundle_path:
            p = self.png_bundle_path
            new_name = f"{p.stem}_modified{p.suffix}"
            self.png_output_path.set(str(p.with_name(new_name)))

    def save_as_png_output(self):
        p = filedialog.asksaveasfilename(title="保存修改后的 Bundle", initialfile=self.png_output_path.get(), defaultextension=".bundle", filetypes=[("Bundle files", "*.bundle"), ("All files", "*.*")])
        if p: self.png_output_path.set(p)

    def drop_b2b_new(self, event): self.set_file_path('b2b_new_bundle_path', self.b2b_new_label, Path(event.data.strip('{}')), "新版 Bundle", self.auto_set_b2b_output)
    def browse_b2b_new(self):
        p = filedialog.askopenfilename(title="选择新版 Bundle (待修改)");
        if p: self.set_file_path('b2b_new_bundle_path', self.b2b_new_label, Path(p), "新版 Bundle", self.auto_set_b2b_output)

    def drop_b2b_old(self, event): self.set_file_path('b2b_old_bundle_path', self.b2b_old_label, Path(event.data.strip('{}')), "旧版 Bundle")
    def browse_b2b_old(self):
        p = filedialog.askopenfilename(title="选择旧版 Bundle (源文件)");
        if p: self.set_file_path('b2b_old_bundle_path', self.b2b_old_label, Path(p), "旧版 Bundle")
    
    def auto_set_b2b_output(self):
        if self.b2b_new_bundle_path:
            p = self.b2b_new_bundle_path
            # 使用原名作为输出文件名
            self.b2b_output_path.set(str(p))

    def save_as_b2b_output(self):
        p = filedialog.asksaveasfilename(title="保存修改后的 Bundle", initialfile=self.b2b_output_path.get(), defaultextension=".bundle", filetypes=[("Bundle files", "*.bundle"), ("All files", "*.*")])
        if p: self.b2b_output_path.set(p)

    # --- 修改: Tab 3 (CRC) 事件处理 ---
    def drop_crc_original(self, event): self.set_crc_original_file(Path(event.data.strip('{}')))
    def browse_crc_original(self):
        p = filedialog.askopenfilename(title="请选择原始文件");
        if p: self.set_crc_original_file(Path(p))

    def drop_crc_modified(self, event): self.set_crc_modified_file(Path(event.data.strip('{}')))
    def browse_crc_modified(self):
        p = filedialog.askopenfilename(title="请选择修改后文件");
        if p: self.set_crc_modified_file(Path(p))

    def set_crc_original_file(self, path: Path):
        self.crc_original_path = path
        self.crc_original_label.config(text=f"原始文件:\n{path.name}", fg="#27ae60")
        self.logger.log(f"已加载CRC原始文件: {path.name}")
        self.logger.status("已加载CRC原始文件")

    def set_crc_modified_file(self, path: Path):
        self.crc_modified_path = path
        self.crc_modified_label.config(text=f"已选择: {path.name}", fg="#27ae60")
        self.logger.log(f"已加载CRC修改后文件: {path.name}")
        
        try:
            custom_dir = Path(self.game_resource_dir_var.get())
            if custom_dir.exists() and custom_dir.is_dir():
                self.game_resource_dir = custom_dir
        except:
            pass
        
        original_candidate = self.game_resource_dir / path.name
        if original_candidate.exists():
            self.set_crc_original_file(original_candidate)
            self.logger.log(f"已自动找到并加载原始文件: {original_candidate.name}")
            self.logger.status("已自动找到原始文件")
        else:
            self.logger.log(f"⚠️ 警告: 未能在 '{self.game_resource_dir}' 中找到对应的原始文件。")
            self.logger.status("未找到对应的原始文件")

    # 将CRC Tab的目录选择/打开功能变为通用函数
    def select_game_resource_directory(self):
        try:
            current_path = Path(self.game_resource_dir_var.get())
            if not current_path.is_dir():
                current_path = Path.home()
            
            selected_dir = filedialog.askdirectory(title="选择游戏资源目录", initialdir=str(current_path))
            
            if selected_dir:
                new_path = Path(selected_dir)
                self.game_resource_dir_var.set(str(new_path))
                self.game_resource_dir = new_path
                self.logger.log(f"已更新游戏资源目录: {new_path}")
        except Exception as e:
            messagebox.showerror("错误", f"打开目录时发生错误:\n{e}")
            self.logger.log(f"❌ 错误：打开目录失败 - {e}")

    def open_game_resource_in_explorer(self):
        try:
            current_path = Path(self.game_resource_dir_var.get())
            if not current_path.is_dir():
                messagebox.showwarning("警告", f"路径不存在或不是一个文件夹:\n{current_path}")
                return
            os.startfile(str(current_path))
            self.logger.log(f"已在资源管理器中打开目录: {current_path}")
        except Exception as e:
            messagebox.showerror("错误", f"打开资源管理器时发生错误:\n{e}")
            self.logger.log(f"❌ 错误：打开资源管理器失败 - {e}")

    # Tab 4 (一键更新) 事件处理
    def drop_mod_update_old_mod(self, event): self.set_file_path('mod_update_old_mod_path', self.mod_update_old_mod_label, Path(event.data.strip('{}')), "旧版 Mod")
    def browse_mod_update_old_mod(self):
        p = filedialog.askopenfilename(title="选择旧版 Mod Bundle");
        if p: self.set_file_path('mod_update_old_mod_path', self.mod_update_old_mod_label, Path(p), "旧版 Mod")

    def select_mod_update_work_dir(self):
        try:
            current_path = Path(self.mod_update_work_dir_var.get())
            if not current_path.is_dir():
                current_path = Path.home()
            
            selected_dir = filedialog.askdirectory(title="选择工作目录", initialdir=str(current_path))
            
            if selected_dir:
                new_path = Path(selected_dir)
                self.mod_update_work_dir_var.set(str(new_path))
                self.logger.log(f"已更新工作目录: {new_path}")
        except Exception as e:
            messagebox.showerror("错误", f"选择工作目录时发生错误:\n{e}")
            self.logger.log(f"❌ 错误：选择工作目录失败 - {e}")

    def open_mod_update_work_dir_in_explorer(self):
        try:
            current_path = Path(self.mod_update_work_dir_var.get())
            if not current_path.is_dir():
                # 如果目录不存在，尝试创建它
                result = messagebox.askyesno("提示", f"目录不存在:\n{current_path}\n\n是否要创建它？")
                if result:
                    current_path.mkdir(parents=True, exist_ok=True)
                else:
                    return
            
            os.startfile(str(current_path))
            self.logger.log(f"已在资源管理器中打开工作目录: {current_path}")
        except Exception as e:
            messagebox.showerror("错误", f"打开工作目录时发生错误:\n{e}")
            self.logger.log(f"❌ 错误：打开工作目录失败 - {e}")

    # 线程管理与执行
    def run_in_thread(self, target, *args):
        thread = threading.Thread(target=target, args=args)
        thread.daemon = True
        thread.start()

    def run_png_replacement_thread(self):
        if not all([self.png_bundle_path, self.png_folder_path, self.png_output_path.get()]):
            messagebox.showerror("错误", "请确保已选择目标 Bundle、PNG 文件夹，并指定了输出路径。")
            return
        self.run_in_thread(self.run_png_replacement)

    def run_png_replacement(self):
        bundle_path = str(self.png_bundle_path)
        folder_path = str(self.png_folder_path)
        output_path = self.png_output_path.get()

        self.logger.log("\n" + "="*50)
        self.logger.log("模式1：开始从 PNG 文件夹替换...")
        self.logger.status("正在处理中，请稍候...")
        
        success, message = processing.process_bundle_replacement(bundle_path, folder_path, output_path, self.logger.log)
        
        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showwarning("警告", message)
        self.logger.status("处理完成")

    def run_b2b_replacement_thread(self):
        if not all([self.b2b_new_bundle_path, self.b2b_old_bundle_path, self.b2b_output_path.get()]):
            messagebox.showerror("错误", "请确保已选择新版和旧版 Bundle，并指定了输出路径。")
            return
        self.run_in_thread(self.run_b2b_replacement)

    def run_b2b_replacement(self):
        new_path = str(self.b2b_new_bundle_path)
        old_path = str(self.b2b_old_bundle_path)
        output_path = self.b2b_output_path.get()

        self.logger.log("\n" + "="*50)
        self.logger.log("模式2：开始从 Bundle 恢复/替换...")
        self.logger.status("正在处理中，请稍候...")

        success, message = processing.process_bundle_to_bundle_replacement(new_path, old_path, output_path, self.logger.log)

        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showwarning("警告", message)
        self.logger.status("处理完成")

    # 一键更新的线程启动函数
    def run_mod_update_thread(self):
        # 更新验证逻辑
        if not all([self.mod_update_old_mod_path, self.game_resource_dir_var.get(), self.mod_update_work_dir_var.get()]):
            messagebox.showerror("错误", "请确保已选择旧版 Mod、游戏资源目录并指定了工作目录。")
            return
        self.run_in_thread(self.run_mod_update)

    def run_mod_update(self):
        # 更新获取路径的方式，并自动创建目录
        old_mod_path = str(self.mod_update_old_mod_path)
        game_dir = self.game_resource_dir_var.get()
        work_dir = self.mod_update_work_dir_var.get()
        padding = self.mod_update_enable_padding.get()

        try:
            Path(work_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.log(f"❌ 严重错误: 无法创建工作目录 '{work_dir}': {e}")
            messagebox.showerror("错误", f"无法创建工作目录:\n{work_dir}\n\n错误详情: {e}")
            self.logger.status("处理失败")
            return

        self.logger.log("\n" + "="*50)
        self.logger.log("模式4：开始一键更新 Mod...")
        self.logger.status("正在处理中，请稍候...")

        success, message = processing.process_mod_update(old_mod_path, game_dir, work_dir, padding, self.logger.log)

        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("失败", message) # 使用 Error 弹窗以示区别
        self.logger.status("处理完成")

    # CRC 操作的线程启动函数
    def run_crc_correction_thread(self):
        if not self.crc_original_path or not self.crc_modified_path:
            messagebox.showerror("错误", "请同时提供原始文件和修改后文件。")
            return
        self.run_in_thread(self.run_crc_correction)

    def calculate_crc_values_thread(self):
        if not self.crc_original_path or not self.crc_modified_path:
            messagebox.showerror("错误", "请同时提供原始文件和修改后文件。")
            return
        self.run_in_thread(self.calculate_crc_values)

    def replace_original_file_thread(self):
        if not self.crc_original_path or not self.crc_modified_path:
            messagebox.showerror("错误", "请同时提供原始文件和修改后文件。")
            return
        self.run_in_thread(self.replace_original_file)

    # CRC 操作的执行函数
    def run_crc_correction(self):
        self.logger.log("\n" + "="*50)
        self.logger.log("模式3：开始CRC修正过程...")
        self.logger.status("正在进行CRC修正...")
        try:
            source_path = self.crc_modified_path
            backup_path = source_path.with_suffix(source_path.suffix + '.bak')
            shutil.copy2(source_path, backup_path)
            self.logger.log(f"已创建备份文件: {backup_path.name}")
            
            self.logger.log("正在计算CRC修正值...")
            success = processing.manipulate_crc(self.crc_original_path, self.crc_modified_path, self.crc_enable_padding.get())
            
            if success:
                self.logger.status("CRC 修正成功！")
                self.logger.log("✅ CRC修正成功！")
                self.logger.log(f"修改后的文件已更新，原始版本备份至: {backup_path.name}")
                messagebox.showinfo("成功", f"CRC 修正成功！\n修改后的文件已更新。\n\n原始版本已备份至:\n{backup_path.name}")
            else:
                self.logger.status("CRC 修正失败。")
                self.logger.log("❌ CRC修正失败")
                messagebox.showerror("失败", "CRC 修正失败。")
                
        except Exception as e:
            self.logger.status(f"发生错误: {e}")
            self.logger.log(f"❌ 错误：{e}")
            messagebox.showerror("错误", f"执行过程中发生错误:\n{e}")

    def calculate_crc_values(self):
        self.logger.log("\n" + "="*50)
        self.logger.log("模式3：开始计算CRC值...")
        self.logger.status("正在计算CRC...")
        try:
            with open(self.crc_original_path, "rb") as f: original_data = f.read()
            with open(self.crc_modified_path, "rb") as f: modified_data = f.read()

            original_crc = processing.compute_crc32(original_data)
            modified_crc = processing.compute_crc32(modified_data)
            
            original_crc_hex = f"{original_crc:08X}"
            modified_crc_hex = f"{modified_crc:08X}"
            is_match = original_crc == modified_crc
            
            self.logger.log(f"原始文件 CRC32: {original_crc_hex}")
            self.logger.log(f"修改后文件 CRC32: {modified_crc_hex}")
            self.logger.log(f"CRC值匹配: {'是' if is_match else '否'}")
            
            if is_match:
                self.logger.status("CRC值匹配！")
                messagebox.showinfo("CRC计算结果", f"原始文件 CRC32: {original_crc_hex}\n修改后文件 CRC32: {modified_crc_hex}\n\nCRC值匹配: 是")
            else:
                self.logger.status("CRC值不匹配")
                messagebox.showwarning("CRC计算结果", f"原始文件 CRC32: {original_crc_hex}\n修改后文件 CRC32: {modified_crc_hex}\n\nCRC值匹配: 否")
                
        except Exception as e:
            self.logger.status(f"计算CRC时发生错误: {e}")
            self.logger.log(f"❌ 计算CRC时发生错误: {e}")
            messagebox.showerror("错误", f"计算CRC时发生错误:\n{e}")

    def replace_original_file(self):
        result = messagebox.askyesno("警告", 
                                   f"确定要用修改后的文件替换原始文件吗？\n\n"
                                   f"原始文件: {self.crc_original_path.name}\n"
                                   f"修改后文件: {self.crc_modified_path.name}\n\n"
                                   f"此操作不可逆，建议先备份原始文件！")
        if not result:
            self.logger.log("用户取消了文件替换操作")
            return

        self.logger.log("\n" + "="*50)
        self.logger.log("模式3：开始替换原始文件...")
        self.logger.status("正在替换文件...")
        try:
            original_backup = self.crc_original_path.with_suffix(self.crc_original_path.suffix + '.backup')
            shutil.copy2(self.crc_original_path, original_backup)
            self.logger.log(f"已创建原始文件备份: {original_backup.name}")
            
            shutil.copy2(self.crc_modified_path, self.crc_original_path)
            
            self.logger.status("原始文件已成功替换！")
            self.logger.log(f"✅ 原始文件已成功替换！备份保存在: {original_backup.name}")
            messagebox.showinfo("成功", f"原始文件已成功替换！\n\n原始文件备份: {original_backup.name}")
            
        except Exception as e:
            self.logger.status(f"文件替换失败: {e}")
            self.logger.log(f"❌ 文件替换失败: {e}")
            messagebox.showerror("错误", f"文件替换过程中发生错误:\n{e}")