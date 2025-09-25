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
from utils import Logger, CRCUtils

# --- UI 组件工厂 ---

class UIComponents:
    """一个辅助类，用于创建通用的UI组件，以减少重复代码。"""

    @staticmethod
    def create_file_drop_zone(parent, title, drop_cmd, browse_cmd):
        frame = tk.LabelFrame(parent, text=title, font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(0, 10))

        label = tk.Label(frame, text="将文件拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=4, bg="#ecf0f1", fg="#34495e", font=("Microsoft YaHei", 9))
        label.pack(fill=tk.X, pady=(0, 8))
        label.drop_target_register(DND_FILES)
        label.dnd_bind('<<Drop>>', drop_cmd)

        button = tk.Button(frame, text="浏览文件...", command=browse_cmd, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack()
        return frame, label

    @staticmethod
    def create_folder_drop_zone(parent, title, drop_cmd, browse_cmd):
        frame = tk.LabelFrame(parent, text=title, font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(0, 10))

        label = tk.Label(frame, text="将文件夹拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=4, bg="#ecf0f1", fg="#34495e", font=("Microsoft YaHei", 9))
        label.pack(fill=tk.X, pady=(0, 8))
        label.drop_target_register(DND_FILES)
        label.dnd_bind('<<Drop>>', drop_cmd)

        button = tk.Button(frame, text="浏览文件夹...", command=browse_cmd, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack()
        return frame, label

    @staticmethod
    def create_output_path_entry(parent, title, textvariable, save_cmd):
        frame = tk.LabelFrame(parent, text=title, font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(10, 15))

        entry = tk.Entry(frame, textvariable=textvariable, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)

        button = tk.Button(frame, text="另存为...", command=save_cmd, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT)
        button.pack(side=tk.RIGHT)
        return frame

    @staticmethod
    def create_directory_path_entry(parent, title, textvariable, select_cmd, open_cmd):
        frame = tk.LabelFrame(parent, text=title, font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        entry = tk.Entry(frame, textvariable=textvariable, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)

        select_btn = tk.Button(frame, text="📂", command=select_cmd, font=("Microsoft YaHei", 10), bg="#3498db", fg="white", relief=tk.FLAT, width=3)
        select_btn.pack(side=tk.LEFT, padx=(0, 5))
        open_btn = tk.Button(frame, text="📁", command=open_cmd, font=("Microsoft YaHei", 10), bg="#9b59b6", fg="white", relief=tk.FLAT, width=3)
        open_btn.pack(side=tk.LEFT)
        return frame
    
# --- 基础 Tab 类 ---

class TabFrame(ttk.Frame):
    """所有Tab页面的基类，提供通用功能和结构。"""
    def __init__(self, parent, logger, **kwargs):
        super().__init__(parent, padding=10)
        self.logger = logger
        self.create_widgets(**kwargs)

    def create_widgets(self, **kwargs):
        raise NotImplementedError("子类必须实现 create_widgets 方法")

    def run_in_thread(self, target, *args):
        thread = threading.Thread(target=target, args=args)
        thread.daemon = True
        thread.start()

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


# --- 具体 Tab 实现 ---

class ModUpdateTab(TabFrame):
    def create_widgets(self, game_resource_dir_var, output_dir_var):
        self.old_mod_path = None
        self.new_mod_path = None 
        self.enable_padding = tk.BooleanVar(value=False)
        self.enable_crc_correction = tk.BooleanVar(value=True)

        # 接收共享的变量
        self.game_resource_dir_var = game_resource_dir_var
        self.work_dir_var = output_dir_var

        # 1. 旧版 Mod 文件
        _, self.old_mod_label = UIComponents.create_file_drop_zone(
            self, "拖入旧版 Mod Bundle", self.drop_old_mod, self.browse_old_mod
        )
        
        # 2. 新版游戏资源文件
        new_mod_frame = tk.LabelFrame(self, text="新版游戏资源 Bundle", font=("Microsoft YaHei", 11, "bold"), fg="#2c3050", bg='#ffffff', padx=15, pady=12)
        new_mod_frame.pack(fill=tk.X, pady=(0, 10))

        # 显示游戏资源目录路径
        auto_find_frame = tk.Frame(new_mod_frame, bg='#ffffff')
        auto_find_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(auto_find_frame, text="游戏资源目录:", bg='#ffffff').pack(side=tk.LEFT, padx=(0,5))
        tk.Entry(auto_find_frame, textvariable=self.game_resource_dir_var, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 新版文件的拖放区 (修改提示文本)
        self.new_mod_label = tk.Label(new_mod_frame, text="拖入旧版Mod后将自动查找新版资源\n或手动拖放/浏览文件", relief=tk.GROOVE, height=4, bg="#ecf0f1", fg="#34495e", font=("Microsoft YaHei", 9))
        self.new_mod_label.pack(fill=tk.X, pady=(4, 8))
        self.new_mod_label.drop_target_register(DND_FILES)
        self.new_mod_label.dnd_bind('<<Drop>>', self.drop_new_mod)
        
        # 功能按钮 (移除自动查找按钮)
        button_container = tk.Frame(new_mod_frame, bg='#ffffff')
        button_container.pack()
        tk.Button(button_container, text="手动浏览...", command=self.browse_new_mod, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        # 3. 选项和操作
        options_frame = tk.LabelFrame(self, text="选项与操作", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        options_frame.pack(fill=tk.X, pady=(10, 15))
        
        checkbox_frame = tk.Frame(options_frame, bg='#ffffff')
        checkbox_frame.pack(pady=5)
        
        padding_checkbox = tk.Checkbutton(checkbox_frame, text="添加私货", variable=self.enable_padding, font=("Microsoft YaHei", 9), bg='#ffffff', fg="#34495e", selectcolor="#ecf0f1")
        
        def toggle_padding_checkbox_state():
            state = tk.NORMAL if self.enable_crc_correction.get() else tk.DISABLED
            padding_checkbox.config(state=state)

        crc_checkbox = tk.Checkbutton(checkbox_frame, text="CRC修正", variable=self.enable_crc_correction, font=("Microsoft YaHei", 9), bg='#ffffff', fg="#34495e", selectcolor="#ecf0f1", command=toggle_padding_checkbox_state)
        
        crc_checkbox.pack(side=tk.LEFT, padx=10)
        padding_checkbox.pack(side=tk.LEFT, padx=10)

        run_button = tk.Button(self, text="🚀 开始一键更新", command=self.run_update_thread, font=("Microsoft YaHei", 12, "bold"), bg="#8e44ad", fg="white", relief=tk.FLAT, padx=20, pady=10)
        run_button.pack(pady=20)

    # --- 修改: 旧版 Mod 的处理方法，增加自动查找回调 ---
    def drop_old_mod(self, event):
        path = Path(event.data.strip('{}'))
        self.set_file_path('old_mod_path', self.old_mod_label, path, "旧版 Mod", self.auto_find_new_bundle)

    def browse_old_mod(self):
        p = filedialog.askopenfilename(title="选择旧版 Mod Bundle")
        if p:
            self.set_file_path('old_mod_path', self.old_mod_label, Path(p), "旧版 Mod", self.auto_find_new_bundle)

    # --- 新版 Mod 的处理方法 (保持不变) ---
    def drop_new_mod(self, event):
        path = Path(event.data.strip('{}'))
        self.set_new_mod_file(path)

    def browse_new_mod(self):
        p = filedialog.askopenfilename(title="选择新版游戏资源 Bundle")
        if p:
            self.set_new_mod_file(Path(p))
            
    def set_new_mod_file(self, path: Path):
        """统一设置新版Mod文件的路径和UI显示"""
        self.new_mod_path = path
        self.new_mod_label.config(text=f"已选择新版资源:\n{path.name}", fg="#27ae60")
        self.logger.log(f"已加载新版资源: {path.name}")
        self.logger.status("已加载新版资源")
    # --------------------------------

    # --- 自动查找相关方法 (保持不变，现在由选择旧版Mod时触发) ---
    def auto_find_new_bundle(self):
        """触发后台线程以查找匹配的新版Bundle文件。"""
        if not all([self.old_mod_path, self.game_resource_dir_var.get()]):
            self.new_mod_label.config(text="⚠️ 请先选择旧版Mod并设置游戏资源目录", fg="#e67e22")
            messagebox.showwarning("提示", "请先选择旧版Mod文件，并设置游戏资源目录，才能进行自动查找。")
            return
        self.run_in_thread(self._find_new_bundle_worker)
        
    def _find_new_bundle_worker(self):
        """在后台线程中执行查找操作并更新UI。"""
        self.new_mod_label.config(text="正在搜索新版资源...", fg="#e67e22")
        self.logger.status("正在搜索新版资源...")
        
        found_path, message = processing.find_new_bundle_path(
            str(self.old_mod_path),
            self.game_resource_dir_var.get(),
            self.logger.log
        )
        
        if found_path:
            self.master.after(0, self.set_new_mod_file, found_path)
        else:
            short_message = message.split('。')[0]
            ui_message = f"❌ 未找到资源: {short_message}"
            self.new_mod_label.config(text=ui_message, fg="#e74c3c")
            self.logger.status("未找到匹配的新版资源")
    # ---------------------------

    def run_update_thread(self):
        if not all([self.old_mod_path, self.new_mod_path, self.game_resource_dir_var.get(), self.work_dir_var.get()]):
            messagebox.showerror("错误", "请确保已分别指定旧版Mod、新版游戏资源，并设置了游戏资源目录和工作目录。")
            return
        self.run_in_thread(self.run_update)

    def run_update(self):
        work_dir = self.work_dir_var.get()

        try:
            Path(work_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建工作目录:\n{work_dir}\n\n错误详情: {e}")
            return

        self.logger.log("\n" + "="*50)
        self.logger.log("模式：开始一键更新 Mod...")
        self.logger.status("正在处理中，请稍候...")
        
        success, message = processing.process_mod_update(
            str(self.old_mod_path), 
            str(self.new_mod_path),
            work_dir, 
            self.enable_padding.get(), 
            self.logger.log,
            self.enable_crc_correction.get()
        )

        if success: messagebox.showinfo("成功", message)
        else: messagebox.showerror("失败", message)
        self.logger.status("处理完成")

class PngReplacementTab(TabFrame):
    def create_widgets(self, output_dir_var):
        self.bundle_path = None
        self.folder_path = None
        self.output_path = tk.StringVar()
        # 接收共享的输出目录变量
        self.output_dir_var = output_dir_var

        _, self.bundle_label = UIComponents.create_file_drop_zone(
            self, "目标 Bundle 文件", self.drop_bundle, self.browse_bundle
        )
        _, self.folder_label = UIComponents.create_folder_drop_zone(
            self, "PNG 图片文件夹", self.drop_folder, self.browse_folder
        )
        # 输出路径输入框已被移除，路径将自动生成到主界面的输出目录中
        
        run_button = tk.Button(self, text="开始替换", command=self.run_replacement_thread, font=("Microsoft YaHei", 12, "bold"), bg="#27ae60", fg="white", relief=tk.FLAT, padx=20, pady=10)
        run_button.pack(pady=20)

    def drop_bundle(self, event): self.set_file_path('bundle_path', self.bundle_label, Path(event.data.strip('{}')), "目标 Bundle", self.auto_set_output)
    def browse_bundle(self):
        p = filedialog.askopenfilename(title="选择目标 Bundle 文件");
        if p: self.set_file_path('bundle_path', self.bundle_label, Path(p), "目标 Bundle", self.auto_set_output)
    
    def drop_folder(self, event): self.set_folder_path('folder_path', self.folder_label, Path(event.data.strip('{}')), "PNG 文件夹")
    def browse_folder(self):
        p = filedialog.askdirectory(title="选择 PNG 图片文件夹");
        if p: self.set_folder_path('folder_path', self.folder_label, Path(p), "PNG 文件夹")

    def auto_set_output(self):
        if self.bundle_path and self.output_dir_var.get():
            p = self.bundle_path
            output_dir = Path(self.output_dir_var.get())
            new_name = f"{p.stem}_modified{p.suffix}"
            self.output_path.set(str(output_dir / new_name))
            self.logger.log(f"输出路径已自动设置为: {self.output_path.get()}")

    def run_replacement_thread(self):
        if not all([self.bundle_path, self.folder_path, self.output_path.get()]):
            messagebox.showerror("错误", "请确保已选择目标 Bundle、PNG 文件夹，并在主界面设置了输出目录。")
            return
        
        # 确保输出目录存在
        try:
            Path(self.output_path.get()).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建输出目录:\n{e}")
            return
            
        self.run_in_thread(self.run_replacement)

    def run_replacement(self):
        self.logger.log("\n" + "="*50)
        self.logger.log("模式：开始从 PNG 文件夹替换...")
        self.logger.status("正在处理中，请稍候...")
        
        success, message = processing.process_bundle_replacement(
            str(self.bundle_path), str(self.folder_path), self.output_path.get(), self.logger.log
        )
        
        if success: messagebox.showinfo("成功", message)
        else: messagebox.showwarning("警告", message)
        self.logger.status("处理完成")


class CrcToolTab(TabFrame):
    def create_widgets(self, game_resource_dir_var):
        self.original_path = None
        self.modified_path = None
        self.enable_padding = tk.BooleanVar(value=False)
        # 接收共享的游戏资源目录变量
        self.game_resource_dir_var = game_resource_dir_var

        # 2. 修改后文件
        _, self.modified_label = UIComponents.create_file_drop_zone(
            self, "修改后文件 (待修正)", self.drop_modified, self.browse_modified
        )

        # 1. 原始文件
        orig_frame = tk.LabelFrame(self, text="原始文件 (用于CRC校验)", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=10)
        orig_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 显示共享的自动寻找路径
        auto_find_frame = tk.Frame(orig_frame, bg='#ffffff')
        auto_find_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(auto_find_frame, text="自动寻找路径:", bg='#ffffff').pack(side=tk.LEFT, padx=(0,5))
        tk.Entry(auto_find_frame, textvariable=self.game_resource_dir_var, font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#34495e", relief=tk.SUNKEN, bd=1, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.original_label = tk.Label(orig_frame, text="将原始文件拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=3, bg="#ecf0f1", fg="#34495e", font=("Microsoft YaHei", 9))
        self.original_label.pack(fill=tk.X, pady=(8, 8))
        self.original_label.drop_target_register(DND_FILES)
        self.original_label.dnd_bind('<<Drop>>', self.drop_original)
        tk.Button(orig_frame, text="浏览原始文件...", command=self.browse_original, font=("Microsoft YaHei", 9), bg="#3498db", fg="white", relief=tk.FLAT).pack()

        # 3. 选项与操作
        options_frame = tk.LabelFrame(self, text="选项与操作", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Checkbutton(options_frame, text="添加私货", variable=self.enable_padding, font=("Microsoft YaHei", 9), bg='#ffffff', fg="#34495e", selectcolor="#ecf0f1").pack(pady=5)
        
        button_frame = tk.Frame(options_frame, bg='#ffffff')
        button_frame.pack(fill=tk.X, pady=10)
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        tk.Button(button_frame, text="运行CRC修正", command=self.run_correction_thread, font=("Microsoft YaHei", 10, "bold"), bg="#27ae60", fg="white", relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=0, sticky="ew", padx=5)
        tk.Button(button_frame, text="计算CRC值", command=self.calculate_values_thread, font=("Microsoft YaHei", 10, "bold"), bg="#e67e22", fg="white", relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(button_frame, text="替换原始文件", command=self.replace_original_thread, font=("Microsoft YaHei", 10, "bold"), bg="#e74c3c", fg="white", relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=2, sticky="ew", padx=5)

    def drop_original(self, event): self.set_original_file(Path(event.data.strip('{}')))
    def browse_original(self):
        p = filedialog.askopenfilename(title="请选择原始文件");
        if p: self.set_original_file(Path(p))
    
    def drop_modified(self, event): self.set_modified_file(Path(event.data.strip('{}')))
    def browse_modified(self):
        p = filedialog.askopenfilename(title="请选择修改后文件");
        if p: self.set_modified_file(Path(p))

    def set_original_file(self, path: Path):
        self.original_path = path
        self.original_label.config(text=f"原始文件:\n{path.name}", fg="#27ae60")
        self.logger.log(f"已加载CRC原始文件: {path.name}")
        self.logger.status("已加载CRC原始文件")

    def set_modified_file(self, path: Path):
        self.modified_path = path
        self.modified_label.config(text=f"已选择: {path.name}", fg="#27ae60")
        self.logger.log(f"已加载CRC修改后文件: {path.name}")
        
        game_dir_str = self.game_resource_dir_var.get()
        if game_dir_str:
            game_dir = Path(game_dir_str)
            if game_dir.is_dir():
                candidate = game_dir / path.name
                if candidate.exists():
                    self.set_original_file(candidate)
                    self.logger.log(f"已自动找到并加载原始文件: {candidate.name}")
                else:
                    self.logger.log(f"⚠️ 警告: 未能在 '{game_dir.name}' 中找到对应的原始文件。")
        else:
            self.logger.log("⚠️ 警告: 未设置游戏资源目录，无法自动寻找原始文件。")


    def _validate_paths(self):
        if not self.original_path or not self.modified_path:
            messagebox.showerror("错误", "请同时提供原始文件和修改后文件。")
            return False
        return True

    def run_correction_thread(self):
        if self._validate_paths(): self.run_in_thread(self.run_correction)

    def calculate_values_thread(self):
        if self._validate_paths(): self.run_in_thread(self.calculate_values)

    def replace_original_thread(self):
        if self._validate_paths(): self.run_in_thread(self.replace_original)

    def run_correction(self):
        self.logger.log("\n" + "="*50); self.logger.log("模式：开始CRC修正过程...")
        self.logger.status("正在进行CRC修正...")
        try:
            backup_path = self.modified_path.with_suffix(self.modified_path.suffix + '.bak')
            shutil.copy2(self.modified_path, backup_path)
            self.logger.log(f"已创建备份文件: {backup_path.name}")
            
            success = CRCUtils.manipulate_crc(str(self.original_path), str(self.modified_path), self.enable_padding.get())
            
            if success:
                self.logger.log("✅ CRC修正成功！")
                messagebox.showinfo("成功", f"CRC 修正成功！\n修改后的文件已更新。\n\n原始版本已备份至:\n{backup_path.name}")
            else:
                self.logger.log("❌ CRC修正失败")
                messagebox.showerror("失败", "CRC 修正失败。")
            self.logger.status("CRC修正完成")
                
        except Exception as e:
            self.logger.log(f"❌ 错误：{e}")
            messagebox.showerror("错误", f"执行过程中发生错误:\n{e}")

    def calculate_values(self):
        self.logger.log("\n" + "="*50); self.logger.log("模式：开始计算CRC值...")
        self.logger.status("正在计算CRC...")
        try:
            with open(self.original_path, "rb") as f: original_data = f.read()
            with open(self.modified_path, "rb") as f: modified_data = f.read()

            original_crc_hex = f"{CRCUtils.compute_crc32(original_data):08X}"
            modified_crc_hex = f"{CRCUtils.compute_crc32(modified_data):08X}"
            
            self.logger.log(f"原始文件 CRC32: {original_crc_hex}")
            self.logger.log(f"修改后文件 CRC32: {modified_crc_hex}")
            
            if original_crc_hex == modified_crc_hex:
                self.logger.log("CRC值匹配: 是")
                messagebox.showinfo("CRC计算结果", f"原始文件 CRC32: {original_crc_hex}\n修改后文件 CRC32: {modified_crc_hex}\n\n✅ CRC值匹配: 是")
            else:
                self.logger.log("CRC值匹配: 否")
                messagebox.showwarning("CRC计算结果", f"原始文件 CRC32: {original_crc_hex}\n修改后文件 CRC32: {modified_crc_hex}\n\n❌ CRC值匹配: 否")
        except Exception as e:
            self.logger.log(f"❌ 计算CRC时发生错误: {e}")
            messagebox.showerror("错误", f"计算CRC时发生错误:\n{e}")

    def replace_original(self):
        if not messagebox.askyesno("警告", "确定要用修改后的文件替换原始文件吗？\n\n此操作不可逆，建议先备份原始文件！"):
            return

        self.logger.log("\n" + "="*50); self.logger.log("模式：开始替换原始文件...")
        self.logger.status("正在替换文件...")
        try:
            backup = self.original_path.with_suffix(self.original_path.suffix + '.backup')
            shutil.copy2(self.original_path, backup)
            self.logger.log(f"已创建原始文件备份: {backup.name}")
            shutil.copy2(self.modified_path, self.original_path)
            self.logger.log("✅ 原始文件已成功替换！")
            messagebox.showinfo("成功", f"原始文件已成功替换！\n\n原始文件备份: {backup.name}")
        except Exception as e:
            self.logger.log(f"❌ 文件替换失败: {e}")
            messagebox.showerror("错误", f"文件替换过程中发生错误:\n{e}")


# --- 主应用 ---

class App(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.setup_main_window()
        self.init_shared_variables()
        self.create_widgets()
        self.logger.status("准备就绪")

    def setup_main_window(self):
        self.master.title("Unity Modding 工具集")
        self.master.geometry("1200x900")
        self.master.configure(bg='#f5f5f5')

    def init_shared_variables(self):
        """初始化所有Tabs共享的变量。"""
        # 尝试定位游戏资源目录
        game_dir = Path(r"D:\SteamLibrary\steamapps\common\BlueArchive\BlueArchive_Data\StreamingAssets\PUB\Resource\GameData\Windows")
        if not game_dir.is_dir():
            game_dir = Path.home()
        self.game_resource_dir_var = tk.StringVar(value=str(game_dir))
        
        # 新增共享的输出/工作目录
        self.output_dir_var = tk.StringVar(value=str(Path.cwd() / "output"))

    def create_widgets(self):
        main_frame = tk.Frame(self.master, bg='#f5f5f5', padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1); main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # 左侧控制面板
        left_frame = tk.Frame(main_frame, bg='#f5f5f5')
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # --- 新增：共享设置区域 ---
        shared_settings_frame = tk.LabelFrame(left_frame, text="全局设置", font=("Microsoft YaHei", 12, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        shared_settings_frame.pack(fill=tk.X, pady=(0, 15))

        UIComponents.create_directory_path_entry(
            shared_settings_frame, "游戏资源目录", self.game_resource_dir_var,
            self.select_game_resource_directory, self.open_game_resource_in_explorer
        )
        UIComponents.create_directory_path_entry(
            shared_settings_frame, "输出/工作目录", self.output_dir_var,
            self.select_output_directory, self.open_output_dir_in_explorer
        )
        # --- 共享设置区域结束 ---

        self.notebook = self.create_notebook(left_frame)
        
        # 右侧日志区域
        right_frame = tk.Frame(main_frame, bg='#ffffff', relief=tk.RAISED, bd=2)
        right_frame.grid(row=0, column=1, sticky="nsew")
        self.log_text = self.create_log_area(right_frame)

        # 底部状态栏
        self.status_label = tk.Label(self.master, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                     font=("Microsoft YaHei", 9), bg="#34495e", fg="#ecf0f1", padx=10)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.logger = Logger(self.master, self.log_text, self.status_label)
        
        # 将 logger 和共享变量传递给 Tabs
        self.populate_notebook()

    # --- 新增：共享目录选择和打开的方法 ---
    def _select_directory(self, var, title):
        try:
            current_path = Path(var.get())
            if not current_path.is_dir(): current_path = Path.home()
            selected_dir = filedialog.askdirectory(title=title, initialdir=str(current_path))
            if selected_dir:
                var.set(str(Path(selected_dir)))
                self.logger.log(f"已更新目录: {selected_dir}")
        except Exception as e:
            messagebox.showerror("错误", f"选择目录时发生错误:\n{e}")
            
    def _open_directory_in_explorer(self, path_str, create_if_not_exist=False):
        try:
            path = Path(path_str)
            if not path.is_dir():
                if create_if_not_exist:
                    if messagebox.askyesno("提示", f"目录不存在:\n{path}\n\n是否要创建它？"):
                        path.mkdir(parents=True, exist_ok=True)
                    else: return
                else:
                    messagebox.showwarning("警告", f"路径不存在或不是一个文件夹:\n{path}")
                    return
            os.startfile(str(path))
            self.logger.log(f"已在资源管理器中打开目录: {path}")
        except Exception as e:
            messagebox.showerror("错误", f"打开资源管理器时发生错误:\n{e}")

    def select_game_resource_directory(self):
        self._select_directory(self.game_resource_dir_var, "选择游戏资源目录")
        
    def open_game_resource_in_explorer(self):
        self._open_directory_in_explorer(self.game_resource_dir_var.get())

    def select_output_directory(self):
        self._select_directory(self.output_dir_var, "选择输出/工作目录")

    def open_output_dir_in_explorer(self):
        self._open_directory_in_explorer(self.output_dir_var.get(), create_if_not_exist=True)
    # --- 方法结束 ---
    
    def create_notebook(self, parent):
        style = ttk.Style()
        style.configure("TNotebook.Tab", font=("Microsoft YaHei", 10, "bold"), padding=[10, 5])
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        return notebook

    def create_log_area(self, parent):
        log_frame = tk.LabelFrame(parent, text="Log", font=("Microsoft YaHei", 11, "bold"), fg="#2c3e50", bg='#ffffff', padx=15, pady=12)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        log_text = tk.Text(log_frame, wrap=tk.WORD, bg="#2c3e50", fg="#ecf0f1", font=("宋体", 9), relief=tk.FLAT, bd=2, padx=10, pady=10)
        scrollbar = tk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview, bg="#34495e")
        log_text.configure(yscrollcommand=scrollbar.set)
        
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.config(state=tk.DISABLED)
        return log_text

    def populate_notebook(self):
        """创建并添加所有的Tab页面到Notebook。"""
        # Tab 1: 一键更新
        update_tab = ModUpdateTab(self.notebook, self.logger, 
                                  game_resource_dir_var=self.game_resource_dir_var, 
                                  output_dir_var=self.output_dir_var)
        self.notebook.add(update_tab, text="  一键更新 Mod  ")

        # Tab 2: PNG 替换
        png_tab = PngReplacementTab(self.notebook, self.logger, 
                                    output_dir_var=self.output_dir_var)
        self.notebook.add(png_tab, text="  PNG 文件夹替换  ")

        # Tab 3: CRC 工具
        crc_tab = CrcToolTab(self.notebook, self.logger, 
                             game_resource_dir_var=self.game_resource_dir_var)
        self.notebook.add(crc_tab, text="  CRC 修正工具  ")