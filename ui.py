# ui.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinterdnd2 import DND_FILES
from pathlib import Path
import shutil
import threading
import os # 新增导入

# 导入自定义模块
import processing
from utils import Logger

class App(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.master.title("Unity Modding 工具集") # 更改标题
        self.master.geometry("900x700") # 稍微调大窗口
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
        # 您可以根据需要修改这个默认路径
        self.crc_default_original_dir = Path(r"D:\SteamLibrary\steamapps\common\BlueArchive\BlueArchive_Data\StreamingAssets\PUB\Resource\GameData\Windows")
        if not self.crc_default_original_dir.exists():
             self.crc_default_original_dir = Path.home() # 如果默认路径不存在，则使用用户主目录
        self.crc_default_path_var = tk.StringVar(value=str(self.crc_default_original_dir))


        self.create_widgets()
        
        # 初始化 Logger
        self.logger = Logger(self.master, self.log_text, self.status_label)
        self.logger.update_status("准备就绪")

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

        self.create_tab1()
        self.create_tab2()
        self.create_tab3() # 新增CRC工具标签页

        right_frame = tk.Frame(main_frame, bg='#ffffff', relief=tk.RAISED, bd=2)
        right_frame.grid(row=0, column=1, sticky="nsew")
        self.create_log_area(right_frame)

        self.status_label = tk.Label(self.master, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                     font=("Microsoft YaHei", 9), bg="#34495e", fg="#ecf0f1", padx=10)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    # --- Tab 1 和 Tab 2 的创建函数 (无变化) ---
    def create_tab1(self):
        tab1 = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab1, text="  PNG 文件夹替换  ")

        bundle_frame = self.create_file_drop_zone(tab1, "1. 目标 Bundle 文件", self.drop_png_bundle, self.browse_png_bundle)
        self.png_bundle_label = bundle_frame.winfo_children()[0]

        folder_frame = self.create_folder_drop_zone(tab1, "2. PNG 图片文件夹", self.drop_png_folder, self.browse_png_folder)
        self.png_folder_label = folder_frame.winfo_children()[0]

        output_frame = tk.LabelFrame(tab1, text="3. 输出文件路径", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        output_frame.pack(fill=tk.X, pady=(10, 15))
        
        entry = tk.Entry(output_frame, textvariable=self.png_output_path, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)
        
        button = tk.Button(output_frame, text="另存为...", command=self.save_as_png_output, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack(side=tk.RIGHT)

        run_button = tk.Button(tab1, text="开始替换", command=self.run_png_replacement_thread, font=("Microsoft YaHei", 12, "bold"), bg="#27ae60", fg="white", relief=tk.FLAT, padx=20, pady=10)
        run_button.pack(pady=20)

    def create_tab2(self):
        tab2 = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab2, text="  Bundle 到 Bundle 恢复  ")

        new_bundle_frame = self.create_file_drop_zone(tab2, "1. 新版 Bundle (待修改)", self.drop_b2b_new, self.browse_b2b_new)
        self.b2b_new_label = new_bundle_frame.winfo_children()[0]

        old_bundle_frame = self.create_file_drop_zone(tab2, "2. 旧版 Bundle (源文件)", self.drop_b2b_old, self.browse_b2b_old)
        self.b2b_old_label = old_bundle_frame.winfo_children()[0]

        output_frame = tk.LabelFrame(tab2, text="3. 输出文件路径", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        output_frame.pack(fill=tk.X, pady=(10, 15))
        
        entry = tk.Entry(output_frame, textvariable=self.b2b_output_path, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)
        
        button = tk.Button(output_frame, text="另存为...", command=self.save_as_b2b_output, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack(side=tk.RIGHT)

        run_button = tk.Button(tab2, text="开始恢复/替换", command=self.run_b2b_replacement_thread, font=("Microsoft YaHei", 12, "bold"), bg="#e67e22", fg="white", relief=tk.FLAT, padx=20, pady=10)
        run_button.pack(pady=20)
    
    # --- 新增 Tab 3 (CRC工具) 的创建函数 ---
    def create_tab3(self):
        tab3 = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab3, text="  CRC 修正工具  ")

        # 默认路径和原始文件区域
        path_frame = tk.LabelFrame(tab3, text="1. 原始文件 (用于CRC校验)", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=10)
        path_frame.pack(fill=tk.X, pady=(0, 10))

        path_entry_frame = tk.Frame(path_frame, bg='#ffffff')
        path_entry_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(path_entry_frame, text="自动寻找路径:", bg='#ffffff').pack(side=tk.LEFT)
        path_entry = tk.Entry(path_entry_frame, textvariable=self.crc_default_path_var, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        open_dir_button = tk.Button(path_entry_frame, text="📂", command=self.crc_open_default_directory, font=("Microsoft YaHei", 10), bg="#3498db", fg="white", relief=tk.FLAT, width=3)
        open_dir_button.pack(side=tk.LEFT, padx=(0, 5))
        open_explorer_button = tk.Button(path_entry_frame, text="📁", command=self.crc_open_in_explorer, font=("Microsoft YaHei", 10), bg="#9b59b6", fg="white", relief=tk.FLAT, width=3)
        open_explorer_button.pack(side=tk.LEFT)

        self.crc_original_label = tk.Label(path_frame, text="将原始文件拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=3, bg="#ecf0f1", fg="#34495e", font=("Microsoft YaHei", 9))
        self.crc_original_label.pack(fill=tk.X, pady=(8, 8))
        self.crc_original_label.drop_target_register(DND_FILES)
        self.crc_original_label.dnd_bind('<<Drop>>', self.drop_crc_original)
        
        browse_orig_btn = tk.Button(path_frame, text="浏览原始文件...", command=self.browse_crc_original, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        browse_orig_btn.pack()

        # 修改后文件区域
        modified_frame = self.create_file_drop_zone(tab3, "2. 修改后文件 (待修正)", self.drop_crc_modified, self.browse_crc_modified)
        self.crc_modified_label = modified_frame.winfo_children()[0]

        # 选项和操作区域
        options_frame = tk.LabelFrame(tab3, text="3. 选项与操作", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        options_frame.pack(fill=tk.X, pady=(0, 10))

        padding_checkbox = tk.Checkbutton(options_frame, text="添加私货 (Enable Padding)", variable=self.crc_enable_padding, font=("Microsoft YaHei", 9), bg='#ffffff', fg="#34495e", selectcolor="#ecf0f1")
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

    # --- 通用UI组件创建函数 (无变化) ---
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
        self.logger.update_status(f"已加载 {file_type_name}")
        if auto_output_func:
            auto_output_func()

    def set_folder_path(self, path_var_name, label_widget, path: Path, folder_type_name):
        setattr(self, path_var_name, path)
        label_widget.config(text=f"已选择: {path.name}", fg="#27ae60")
        self.logger.log(f"已加载 {folder_type_name}: {path.name}")
        self.logger.update_status(f"已加载 {folder_type_name}")
    
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
            new_name = f"{p.stem}_restored{p.suffix}"
            self.b2b_output_path.set(str(p.with_name(new_name)))

    def save_as_b2b_output(self):
        p = filedialog.asksaveasfilename(title="保存修改后的 Bundle", initialfile=self.b2b_output_path.get(), defaultextension=".bundle", filetypes=[("Bundle files", "*.bundle"), ("All files", "*.*")])
        if p: self.b2b_output_path.set(p)

    # --- 新增 Tab 3 (CRC) 事件处理 ---
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
        self.logger.update_status("已加载CRC原始文件")

    def set_crc_modified_file(self, path: Path):
        self.crc_modified_path = path
        self.crc_modified_label.config(text=f"已选择: {path.name}", fg="#27ae60")
        self.logger.log(f"已加载CRC修改后文件: {path.name}")
        
        try:
            custom_dir = Path(self.crc_default_path_var.get())
            if custom_dir.exists() and custom_dir.is_dir():
                self.crc_default_original_dir = custom_dir
        except:
            pass
        
        original_candidate = self.crc_default_original_dir / path.name
        if original_candidate.exists():
            self.set_crc_original_file(original_candidate)
            self.logger.log(f"已自动找到并加载原始文件: {original_candidate.name}")
            self.logger.update_status("已自动找到原始文件")
        else:
            self.logger.log(f"⚠️ 警告: 未能在 '{self.crc_default_original_dir}' 中找到对应的原始文件。")
            self.logger.update_status("未找到对应的原始文件")

    def crc_open_default_directory(self):
        try:
            current_path = Path(self.crc_default_path_var.get())
            if not current_path.is_dir():
                current_path = Path.home()
            
            selected_dir = filedialog.askdirectory(title="选择默认寻找目录", initialdir=str(current_path))
            
            if selected_dir:
                new_path = Path(selected_dir)
                self.crc_default_path_var.set(str(new_path))
                self.crc_default_original_dir = new_path
                self.logger.log(f"已更新CRC原始文件默认寻找路径: {new_path}")
        except Exception as e:
            messagebox.showerror("错误", f"打开目录时发生错误:\n{e}")
            self.logger.log(f"❌ 错误：打开目录失败 - {e}")

    def crc_open_in_explorer(self):
        try:
            current_path = Path(self.crc_default_path_var.get())
            if not current_path.is_dir():
                messagebox.showwarning("警告", f"路径不存在或不是一个文件夹:\n{current_path}")
                return
            os.startfile(str(current_path))
            self.logger.log(f"已在资源管理器中打开目录: {current_path}")
        except Exception as e:
            messagebox.showerror("错误", f"打开资源管理器时发生错误:\n{e}")
            self.logger.log(f"❌ 错误：打开资源管理器失败 - {e}")

    # --- 线程管理与执行 ---
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
        self.logger.update_status("正在处理中，请稍候...")
        
        success, message = processing.process_bundle_replacement(bundle_path, folder_path, output_path, self.logger.log)
        
        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showwarning("警告", message)
        self.logger.update_status("处理完成")

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
        self.logger.update_status("正在处理中，请稍候...")

        success, message = processing.process_bundle_to_bundle_replacement(new_path, old_path, output_path, self.logger.log)

        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showwarning("警告", message)
        self.logger.update_status("处理完成")

    # --- 新增 CRC 操作的线程启动函数 ---
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

    # --- 新增 CRC 操作的执行函数 ---
    def run_crc_correction(self):
        self.logger.log("\n" + "="*50)
        self.logger.log("模式3：开始CRC修正过程...")
        self.logger.update_status("正在进行CRC修正...")
        try:
            source_path = self.crc_modified_path
            backup_path = source_path.with_suffix(source_path.suffix + '.bak')
            shutil.copy2(source_path, backup_path)
            self.logger.log(f"已创建备份文件: {backup_path.name}")
            
            self.logger.log("正在计算CRC修正值...")
            success = processing.manipulate_crc(self.crc_original_path, self.crc_modified_path, self.crc_enable_padding.get())
            
            if success:
                self.logger.update_status("CRC 修正成功！")
                self.logger.log("✅ CRC修正成功！")
                self.logger.log(f"修改后的文件已更新，原始版本备份至: {backup_path.name}")
                messagebox.showinfo("成功", f"CRC 修正成功！\n修改后的文件已更新。\n\n原始版本已备份至:\n{backup_path.name}")
            else:
                self.logger.update_status("CRC 修正失败。")
                self.logger.log("❌ CRC修正失败")
                messagebox.showerror("失败", "CRC 修正失败。")
                
        except Exception as e:
            self.logger.update_status(f"发生错误: {e}")
            self.logger.log(f"❌ 错误：{e}")
            messagebox.showerror("错误", f"执行过程中发生错误:\n{e}")

    def calculate_crc_values(self):
        self.logger.log("\n" + "="*50)
        self.logger.log("模式3：开始计算CRC值...")
        self.logger.update_status("正在计算CRC...")
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
                self.logger.update_status("CRC值匹配！")
                messagebox.showinfo("CRC计算结果", f"原始文件 CRC32: {original_crc_hex}\n修改后文件 CRC32: {modified_crc_hex}\n\nCRC值匹配: 是")
            else:
                self.logger.update_status("CRC值不匹配")
                messagebox.showwarning("CRC计算结果", f"原始文件 CRC32: {original_crc_hex}\n修改后文件 CRC32: {modified_crc_hex}\n\nCRC值匹配: 否")
                
        except Exception as e:
            self.logger.update_status(f"计算CRC时发生错误: {e}")
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
        self.logger.update_status("正在替换文件...")
        try:
            original_backup = self.crc_original_path.with_suffix(self.crc_original_path.suffix + '.backup')
            shutil.copy2(self.crc_original_path, original_backup)
            self.logger.log(f"已创建原始文件备份: {original_backup.name}")
            
            shutil.copy2(self.crc_modified_path, self.crc_original_path)
            
            self.logger.update_status("原始文件已成功替换！")
            self.logger.log(f"✅ 原始文件已成功替换！备份保存在: {original_backup.name}")
            messagebox.showinfo("成功", f"原始文件已成功替换！\n\n原始文件备份: {original_backup.name}")
            
        except Exception as e:
            self.logger.update_status(f"文件替换失败: {e}")
            self.logger.log(f"❌ 文件替换失败: {e}")
            messagebox.showerror("错误", f"文件替换过程中发生错误:\n{e}")