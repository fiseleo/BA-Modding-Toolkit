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

# --- 主题与颜色管理 ---

class Theme:
    """集中管理应用的所有颜色，确保UI风格统一。"""
    # 背景色
    WINDOW_BG = '#f0f2f5'
    FRAME_BG = '#ffffff'
    INPUT_BG = '#ecf0f1'
    MUTED_BG = '#e9ecef' # 用于拖放区等不活跃背景

    # 文本颜色
    TEXT_TITLE = '#080808'
    TEXT_NORMAL = '#34495e'
    TEXT_LIGHT = '#ffffff'
    
    # 按钮颜色 (背景/前景)
    BUTTON_PRIMARY_BG = '#3498db'
    BUTTON_SECONDARY_BG = '#9b59b6'
    BUTTON_ACCENT_BG = '#8e44ad'
    BUTTON_SUCCESS_BG = '#27ae60'
    BUTTON_WARNING_BG = '#f39c12'
    BUTTON_DANGER_BG = '#e74c3c'
    BUTTON_FG = TEXT_LIGHT

    # 状态颜色 (用于文本提示)
    COLOR_SUCCESS = '#27ae60'
    COLOR_WARNING = '#e67e22'
    COLOR_ERROR = '#e74c3c'

    # 特殊组件颜色
    LOG_BG = '#2c3e50'
    LOG_FG = '#ecf0f1'
    STATUS_BAR_BG = '#34495e'
    STATUS_BAR_FG = '#ecf0f1'

    # 字体
    FRAME_FONT = ("Microsoft YaHei", 11, "bold")
    INPUT_FONT = ("Microsoft YaHei", 9)
    BUTTON_FONT = ("Microsoft YaHei", 10, "bold")


# --- UI 组件工厂 ---

class UIComponents:
    """一个辅助类，用于创建通用的UI组件，以减少重复代码。"""

    @staticmethod
    def create_file_drop_zone(parent, title, drop_cmd, browse_cmd):
        frame = tk.LabelFrame(parent, text=title, font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(0, 10))

        label = tk.Label(frame, text="将文件拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=4, bg=Theme.MUTED_BG, fg=Theme.TEXT_NORMAL, font=Theme.INPUT_FONT, justify=tk.LEFT)
        label.pack(fill=tk.X, pady=(0, 8))
        label.drop_target_register(DND_FILES)
        label.dnd_bind('<<Drop>>', drop_cmd)
        label.bind('<Configure>', lambda e: e.widget.config(wraplength=e.width - 10))

        button = tk.Button(frame, text="浏览文件...", command=browse_cmd, font=Theme.INPUT_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT)
        button.pack()
        return frame, label

    @staticmethod
    def create_folder_drop_zone(parent, title, drop_cmd, browse_cmd):
        frame = tk.LabelFrame(parent, text=title, font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(0, 10))

        label = tk.Label(frame, text="将文件夹拖放到此处\n或点击下方按钮选择", relief=tk.GROOVE, height=4, bg=Theme.MUTED_BG, fg=Theme.TEXT_NORMAL, font=Theme.INPUT_FONT, justify=tk.LEFT)
        label.pack(fill=tk.X, pady=(0, 8))
        label.drop_target_register(DND_FILES)
        label.dnd_bind('<<Drop>>', drop_cmd)
        label.bind('<Configure>', lambda e: e.widget.config(wraplength=e.width - 10))

        button = tk.Button(frame, text="浏览文件夹...", command=browse_cmd, font=Theme.INPUT_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT)
        button.pack()
        return frame, label

    @staticmethod
    def create_output_path_entry(parent, title, textvariable, save_cmd):
        frame = tk.LabelFrame(parent, text=title, font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(10, 15))

        entry = tk.Entry(frame, textvariable=textvariable, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)

        button = tk.Button(frame, text="另存为...", command=save_cmd, font=Theme.INPUT_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT)
        button.pack(side=tk.RIGHT)
        return frame

    @staticmethod
    def create_directory_path_entry(parent, title, textvariable, select_cmd, open_cmd):
        frame = tk.LabelFrame(parent, text=title, font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        entry = tk.Entry(frame, textvariable=textvariable, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)

        select_btn = tk.Button(frame, text="📂", command=select_cmd, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=3)
        select_btn.pack(side=tk.LEFT, padx=(0, 5))
        open_btn = tk.Button(frame, text="📁", command=open_cmd, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SECONDARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=3)
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
        label_widget.config(text=f"已选择: {path.name}", fg=Theme.COLOR_SUCCESS)
        self.logger.log(f"已加载 {file_type_name}: {path.name}")
        self.logger.status(f"已加载 {file_type_name}")
        if auto_output_func:
            auto_output_func()

    def set_folder_path(self, path_var_name, label_widget, path: Path, folder_type_name):
        setattr(self, path_var_name, path)
        label_widget.config(text=f"已选择: {path.name}", fg=Theme.COLOR_SUCCESS)
        self.logger.log(f"已加载 {folder_type_name}: {path.name}")
        self.logger.status(f"已加载 {folder_type_name}")


# --- 具体 Tab 实现 ---

class ModUpdateTab(TabFrame):
    def create_widgets(self, game_resource_dir_var, output_dir_var, enable_padding_var, enable_crc_correction_var, create_backup_var):
        self.old_mod_path = None
        self.new_mod_path = None 
        self.final_output_path = None # 新增：用于存储成功生成的文件路径
        self.enable_padding = enable_padding_var
        self.enable_crc_correction = enable_crc_correction_var
        self.create_backup = create_backup_var

        # 接收共享的变量
        self.game_resource_dir_var = game_resource_dir_var
        self.work_dir_var = output_dir_var

        # 1. 旧版 Mod 文件
        _, self.old_mod_label = UIComponents.create_file_drop_zone(
            self, "拖入旧版 Mod Bundle", self.drop_old_mod, self.browse_old_mod
        )
        
        # 2. 新版游戏资源文件
        new_mod_frame, self.new_mod_label = UIComponents.create_file_drop_zone(
            self, "新版游戏资源 Bundle", self.drop_new_mod, self.browse_new_mod
        )
        # 自定义拖放区的提示文本，使其更具指导性
        self.new_mod_label.config(text="拖入旧版Mod后将自动查找新版资源\n或手动拖放/浏览文件")

        # 创建并插入用于显示游戏资源目录的额外组件
        auto_find_frame = tk.Frame(new_mod_frame, bg=Theme.FRAME_BG)
        # 使用 pack 的 before 参数，将此组件插入到拖放区标签(self.new_mod_label)的上方
        auto_find_frame.pack(fill=tk.X, pady=(0, 8), before=self.new_mod_label)
        tk.Label(auto_find_frame, text="游戏资源目录:", bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL).pack(side=tk.LEFT, padx=(0,5))
        tk.Entry(auto_find_frame, textvariable=self.game_resource_dir_var, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 3. 选项和操作

        # 操作按钮区域
        action_button_frame = tk.Frame(self) # 使用与父框架相同的背景色
        action_button_frame.pack(fill=tk.X, pady=10)
        action_button_frame.grid_columnconfigure((0, 1), weight=1)

        run_button = tk.Button(action_button_frame, text="🚀 开始一键更新", command=self.run_update_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_ACCENT_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=15, pady=8)
        run_button.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=10)
        
        self.replace_button = tk.Button(action_button_frame, text="🔥 覆盖游戏原文件", command=self.replace_original_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_DANGER_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=15, pady=8, state=tk.DISABLED)
        self.replace_button.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=10)

    # 旧版 Mod 的处理方法，增加自动查找回调
    def drop_old_mod(self, event):
        path = Path(event.data.strip('{}'))
        self.set_file_path('old_mod_path', self.old_mod_label, path, "旧版 Mod", self.auto_find_new_bundle)

    def browse_old_mod(self):
        p = filedialog.askopenfilename(title="选择旧版 Mod Bundle")
        if p:
            self.set_file_path('old_mod_path', self.old_mod_label, Path(p), "旧版 Mod", self.auto_find_new_bundle)

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
        self.new_mod_label.config(text=f"已选择新版资源:{path.name}", fg=Theme.COLOR_SUCCESS)
        self.logger.log(f"已加载新版资源: {path.name}")
        self.logger.status("已加载新版资源")

    # 自动查找相关方法
    def auto_find_new_bundle(self):
        """触发后台线程以查找匹配的新版Bundle文件。"""
        if not all([self.old_mod_path, self.game_resource_dir_var.get()]):
            self.new_mod_label.config(text="⚠️ 请先选择旧版Mod并设置游戏资源目录", fg=Theme.COLOR_WARNING)
            messagebox.showwarning("提示", "请先选择旧版Mod文件，并设置游戏资源目录，才能进行自动查找。")
            return
        self.run_in_thread(self._find_new_bundle_worker)
        
    def _find_new_bundle_worker(self):
        """在后台线程中执行查找操作并更新UI。"""
        self.new_mod_label.config(text="正在搜索新版资源...", fg=Theme.COLOR_WARNING)
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
            self.new_mod_label.config(text=ui_message, fg=Theme.COLOR_ERROR)
            self.logger.status("未找到匹配的新版资源")

    def run_update_thread(self):
        if not all([self.old_mod_path, self.new_mod_path, self.game_resource_dir_var.get(), self.work_dir_var.get()]):
            messagebox.showerror("错误", "请确保已分别指定旧版Mod、新版游戏资源，并设置了游戏资源目录和工作目录。")
            return
        self.run_in_thread(self.run_update)

    def run_update(self):
        # --- 修改: 增加按钮状态管理和路径记录 ---
        # 每次开始更新时，先禁用替换按钮
        self.final_output_path = None
        self.master.after(0, lambda: self.replace_button.config(state=tk.DISABLED))

        work_dir_base = Path(self.work_dir_var.get())
        # 直接将基础输出目录传递给 processing 函数，它会创建子目录
        work_dir = work_dir_base 

        try:
            # 确保基础输出目录存在
            work_dir.mkdir(parents=True, exist_ok=True) 
        except Exception as e:
            messagebox.showerror("错误", f"无法创建工作目录:\n{work_dir}\n\n错误详情: {e}")
            return

        self.logger.log("\n" + "="*50)
        self.logger.log("模式：开始一键更新 Mod...")
        self.logger.status("正在处理中，请稍候...")
        
        # 传递 work_dir (基础输出目录)
        success, message = processing.process_mod_update(
            str(self.old_mod_path), 
            str(self.new_mod_path),
            str(work_dir), # <-- 传递的是基础输出目录
            self.enable_padding.get(), 
            self.logger.log,
            self.enable_crc_correction.get()
        )
        
        if success:
            # 成功后，记录最终文件路径并启用按钮
            # processing.py 内部会创建带更新信息的子目录，所以我们需要找到它
            # 查找方式：在 work_dir 中寻找以 "update_" 开头，并且包含新bundle文件名的目录
            generated_bundle_filename = self.new_mod_path.name
            update_subdir = None
            for item in work_dir.iterdir():
                if item.is_dir() and item.name.startswith("update_") and generated_bundle_filename in str(item):
                    update_subdir = item
                    break
            
            if update_subdir:
                self.final_output_path = update_subdir / generated_bundle_filename
            else:
                # 如果找不到预期的子目录，尝试直接在 work_dir 中查找 (作为后备)
                potential_path = work_dir / generated_bundle_filename
                if potential_path.exists():
                    self.final_output_path = potential_path
                else:
                    self.logger.log(f"⚠️ 警告: 无法确定生成的 Mod 文件路径。请手动查找。")
                    self.final_output_path = None # 确保路径为空

            if self.final_output_path and self.final_output_path.exists():
                self.logger.log(f"✅ 更新成功。最终文件路径: {self.final_output_path}")
                self.logger.log(f"现在可以点击 '覆盖游戏原文件' 按钮来应用 Mod。")
                self.master.after(0, lambda: self.replace_button.config(state=tk.NORMAL))
                messagebox.showinfo("成功", message)
            else:
                # 如果路径查找失败，但process_mod_update返回成功，仍需显示消息
                self.logger.log(f"⚠️ 警告: 更新成功，但无法自动确定最终文件路径。请在 '{work_dir}' 目录中查找。")
                self.master.after(0, lambda: self.replace_button.config(state=tk.DISABLED)) # 禁用替换按钮，因为路径未知
                messagebox.showinfo("成功 (路径未知)", message + "\n\n⚠️ 警告：无法自动确定最终文件路径，请在输出目录中手动查找。")
        else:
            messagebox.showerror("失败", message)
        
        self.logger.status("处理完成")

    # 替换原始文件相关方法
    def replace_original_thread(self):
        """启动替换原始游戏文件的线程"""
        if not self.final_output_path or not self.final_output_path.exists():
            messagebox.showerror("错误", "找不到已生成的 Mod 文件。\n请先成功执行一次'一键更新'。")
            return
        if not self.new_mod_path or not self.new_mod_path.exists():
            messagebox.showerror("错误", "找不到原始游戏资源文件路径。\n请确保在更新前已正确指定新版游戏资源。")
            return
        
        self.run_in_thread(self.replace_original)

    def replace_original(self):
        """执行实际的文件替换操作（在线程中）"""
        if not messagebox.askyesno("警告", 
                                   f"此操作将覆盖游戏目录中的原始文件:\n\n{self.new_mod_path.name}\n\n"
                                   "如果要继续，请确保已备份原始文件，或是在全局设置中开启备份功能。\n\n确定要继续吗？"):
            return

        self.logger.log("\n" + "="*50)
        self.logger.log(f"模式：开始覆盖游戏原文件 '{self.new_mod_path.name}'...")
        self.logger.status("正在覆盖文件...")
        try:
            # 目标文件就是新版游戏资源文件
            target_file = self.new_mod_path
            # 源文件是刚刚生成的新Mod
            source_file = self.final_output_path
            
            backup_message = ""
            if self.create_backup.get():
                backup_path = target_file.with_suffix(target_file.suffix + '.backup')
                self.logger.log(f"  > 正在备份原始文件到: {backup_path.name}")
                shutil.copy2(target_file, backup_path)
                backup_message = f"\n\n原始文件备份至:\n{backup_path.name}"
            else:
                self.logger.log("  > 已根据设置跳过创建备份文件。")
                backup_message = "\n\n(已跳过创建备份)"
            
            self.logger.log(f"  > 正在用 '{source_file.name}' 覆盖 '{target_file.name}'...")
            shutil.copy2(source_file, target_file)
            
            self.logger.log("✅ 原始文件已成功覆盖！")
            self.logger.status("文件覆盖完成")
            messagebox.showinfo("成功", f"游戏原始文件已成功覆盖！{backup_message}")

        except Exception as e:
            self.logger.log(f"❌ 文件覆盖失败: {e}")
            self.logger.status("文件覆盖失败")
            messagebox.showerror("错误", f"文件覆盖过程中发生错误:\n{e}")


class PngReplacementTab(TabFrame):
    def create_widgets(self, output_dir_var, create_backup_var):
        self.bundle_path = None
        self.folder_path = None
        self.output_path = tk.StringVar()
        self.create_backup = create_backup_var
        # 接收共享的输出目录变量
        self.output_dir_var = output_dir_var

        _, self.folder_label = UIComponents.create_folder_drop_zone(
            self, "PNG 图片文件夹", self.drop_folder, self.browse_folder
        )

        _, self.bundle_label = UIComponents.create_file_drop_zone(
            self, "目标 Bundle 文件", self.drop_bundle, self.browse_bundle
        )
        
        run_button = tk.Button(self, text="开始替换", command=self.run_replacement_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SUCCESS_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=20, pady=10)
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
            str(self.bundle_path), 
            str(self.folder_path), 
            self.output_path.get(), 
            self.logger.log,
            create_backup_file=self.create_backup.get()
        )
        
        if success: messagebox.showinfo("成功", message)
        else: messagebox.showwarning("警告", message)
        self.logger.status("处理完成")


class CrcToolTab(TabFrame):
    def create_widgets(self, game_resource_dir_var, enable_padding_var, create_backup_var):
        self.original_path = None
        self.modified_path = None
        self.enable_padding = enable_padding_var
        self.create_backup = create_backup_var
        # 接收共享的游戏资源目录变量
        self.game_resource_dir_var = game_resource_dir_var

        # 1. 修改后文件
        _, self.modified_label = UIComponents.create_file_drop_zone(
            self, "修改后文件 (待修正)", self.drop_modified, self.browse_modified
        )

        # 2. 原始文件 - 使用与new_mod_label相同的方式
        original_frame, self.original_label = UIComponents.create_file_drop_zone(
            self, "原始文件 (用于CRC校验)", self.drop_original, self.browse_original
        )
        
        # 自定义拖放区的提示文本，使其更具指导性
        self.original_label.config(text="拖入修改后文件后将自动查找原始文件\n或手动拖放/浏览文件")
        
        # 创建并插入用于显示游戏资源目录的额外组件
        auto_find_frame = tk.Frame(original_frame, bg=Theme.FRAME_BG)
        # 使用 pack 的 before 参数，将此组件插入到拖放区标签(self.original_label)的上方
        auto_find_frame.pack(fill=tk.X, pady=(0, 8), before=self.original_label)
        tk.Label(auto_find_frame, text="自动寻找路径:", bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL).pack(side=tk.LEFT, padx=(0,5))
        tk.Entry(auto_find_frame, textvariable=self.game_resource_dir_var, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 3. 选项与操作
        options_frame = tk.LabelFrame(self, text="选项与操作", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        button_frame = tk.Frame(options_frame, bg=Theme.FRAME_BG)
        button_frame.pack(fill=tk.X, pady=10)
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        tk.Button(button_frame, text="运行CRC修正", command=self.run_correction_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SUCCESS_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=0, sticky="ew", padx=5)
        tk.Button(button_frame, text="计算CRC值", command=self.calculate_values_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_WARNING_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(button_frame, text="替换原始文件", command=self.replace_original_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_DANGER_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=2, sticky="ew", padx=5)

    def drop_original(self, event): 
        self.set_original_file(Path(event.data.strip('{}')))
    def browse_original(self):
        p = filedialog.askopenfilename(title="请选择原始文件")
        if p: 
            self.set_original_file(Path(p))
    
    def drop_modified(self, event): 
        self.set_modified_file(Path(event.data.strip('{}')))
    def browse_modified(self):
        p = filedialog.askopenfilename(title="请选择修改后文件")
        if p: 
            self.set_modified_file(Path(p))

    def set_original_file(self, path: Path):
        self.original_path = path
        self.original_label.config(text=f"原始文件: {path.name}", fg=Theme.COLOR_SUCCESS)
        self.logger.log(f"已加载CRC原始文件: {path.name}")
        self.logger.status("已加载CRC原始文件")

    def set_modified_file(self, path: Path):
        self.modified_path = path
        self.modified_label.config(text=f"已选择: {path.name}", fg=Theme.COLOR_SUCCESS)
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
            backup_message = ""
            if self.create_backup.get():
                # 创建备份文件
                backup_path = self.modified_path.with_suffix(self.modified_path.suffix + '.bak')
                shutil.copy2(self.modified_path, backup_path)
                self.logger.log(f"已创建备份文件: {backup_path.name}")
                backup_message = f"\n\n原始版本已备份至:\n{backup_path.name}"
            else:
                self.logger.log("已根据设置跳过创建备份文件。")
                backup_message = "\n\n(已跳过创建备份)"
            
            # 修正文件CRC
            success = CRCUtils.manipulate_crc(str(self.original_path), str(self.modified_path), self.enable_padding.get())
            
            if success:
                self.logger.log("✅ CRC修正成功！")
                messagebox.showinfo("成功", f"CRC 修正成功！\n修改后的文件已更新。{backup_message}")
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
            backup_message = ""
            if self.create_backup.get():
                backup = self.original_path.with_suffix(self.original_path.suffix + '.backup')
                shutil.copy2(self.original_path, backup)
                self.logger.log(f"已创建原始文件备份: {backup.name}")
                backup_message = f"\n\n原始文件备份: {backup.name}"
            else:
                self.logger.log("已根据设置跳过创建备份文件。")
                backup_message = "\n\n(已跳过创建备份)"

            shutil.copy2(self.modified_path, self.original_path)
            self.logger.log("✅ 原始文件已成功替换！")
            messagebox.showinfo("成功", f"原始文件已成功替换！{backup_message}")
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
        self.master.title("BA Modding Toolkit")
        self.master.geometry("1200x900")
        self.master.configure(bg=Theme.WINDOW_BG)

    def init_shared_variables(self):
        """初始化所有Tabs共享的变量。"""
        # 尝试定位游戏资源目录
        game_dir = Path(r"D:\SteamLibrary\steamapps\common\BlueArchive\BlueArchive_Data\StreamingAssets\PUB\Resource\GameData\Windows")
        if not game_dir.is_dir():
            game_dir = Path.home()
        self.game_resource_dir_var = tk.StringVar(value=str(game_dir))
        
        # 新增共享的输出/工作目录
        self.output_dir_var = tk.StringVar(value=str(Path.cwd() / "output"))
        
        # 新增：全局选项变量
        self.enable_padding_var = tk.BooleanVar(value=False)
        self.enable_crc_correction_var = tk.BooleanVar(value=True)
        self.create_backup_var = tk.BooleanVar(value=True)

    def create_widgets(self):
        main_frame = tk.Frame(self.master, bg=Theme.WINDOW_BG, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1); main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # 左侧控制面板
        left_frame = tk.Frame(main_frame, bg=Theme.WINDOW_BG)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # --- 新增：共享设置区域 ---
        shared_settings_frame = tk.LabelFrame(left_frame, text="全局设置", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        shared_settings_frame.pack(fill=tk.X, pady=(0, 15))

        UIComponents.create_directory_path_entry(
            shared_settings_frame, "游戏资源目录", self.game_resource_dir_var,
            self.select_game_resource_directory, self.open_game_resource_in_explorer
        )
        UIComponents.create_directory_path_entry(
            shared_settings_frame, "输出/工作目录", self.output_dir_var,
            self.select_output_directory, self.open_output_dir_in_explorer
        )
        
        # --- 全局选项 ---
        global_options_frame = tk.Frame(shared_settings_frame, bg=Theme.FRAME_BG)
        global_options_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.padding_checkbox = tk.Checkbutton(global_options_frame, text="添加私货", variable=self.enable_padding_var, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG)
        
        crc_checkbox = tk.Checkbutton(global_options_frame, text="CRC修正", variable=self.enable_crc_correction_var, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG, command=self.toggle_padding_checkbox_state)
        
        backup_checkbox = tk.Checkbutton(global_options_frame, text="创建备份", variable=self.create_backup_var, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG)

        crc_checkbox.pack(side=tk.LEFT, padx=(0, 20))
        self.padding_checkbox.pack(side=tk.LEFT, padx=(0, 20))
        backup_checkbox.pack(side=tk.LEFT)
        # --- 全局选项结束 ---
        
        # --- 共享设置区域结束 ---

        self.notebook = self.create_notebook(left_frame)
        
        # 右侧日志区域
        right_frame = tk.Frame(main_frame, bg=Theme.FRAME_BG, relief=tk.RAISED, bd=1)
        right_frame.grid(row=0, column=1, sticky="nsew")
        self.log_text = self.create_log_area(right_frame)

        # 底部状态栏
        self.status_label = tk.Label(self.master, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                     font=Theme.INPUT_FONT, bg=Theme.STATUS_BAR_BG, fg=Theme.STATUS_BAR_FG, padx=10)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.logger = Logger(self.master, self.log_text, self.status_label)
        
        # 将 logger 和共享变量传递给 Tabs
        self.populate_notebook()
        
        # 初始化 padding checkbox 状态
        self.toggle_padding_checkbox_state()

    def toggle_padding_checkbox_state(self):
        """根据CRC修正复选框的状态，启用或禁用添加私货复选框，并取消勾选"""
        if self.enable_crc_correction_var.get():
            # CRC修正启用时，添加私货框可用
            self.padding_checkbox.config(state=tk.NORMAL)
        else:
            # CRC修正禁用时，添加私货框禁用并取消勾选
            self.enable_padding_var.set(False)
            self.padding_checkbox.config(state=tk.DISABLED)

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
        # 自定义Notebook样式以匹配主题
        style.configure("TNotebook", background=Theme.WINDOW_BG, borderwidth=0)
        style.configure("TNotebook.Tab", 
                        font=Theme.BUTTON_FONT, 
                        padding=[10, 5],
                        background=Theme.MUTED_BG,
                        foreground=Theme.TEXT_NORMAL)
        style.map("TNotebook.Tab",
                  background=[("selected", Theme.FRAME_BG)],
                  foreground=[("selected", Theme.TEXT_TITLE)])

        notebook = ttk.Notebook(parent, style="TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True)
        return notebook

    def create_log_area(self, parent):
        log_frame = tk.LabelFrame(parent, text="Log", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        log_text = tk.Text(log_frame, wrap=tk.WORD, bg=Theme.LOG_BG, fg=Theme.LOG_FG, font=("SimSun", 10), relief=tk.FLAT, bd=0, padx=5, pady=5, insertbackground=Theme.LOG_FG)
        scrollbar = tk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
        log_text.configure(yscrollcommand=scrollbar.set)
        
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.config(state=tk.DISABLED)
        return log_text

    def populate_notebook(self):
        """创建并添加所有的Tab页面到Notebook。"""
        # Tab: 一键更新
        update_tab = ModUpdateTab(self.notebook, self.logger, 
                                  game_resource_dir_var=self.game_resource_dir_var, 
                                  output_dir_var=self.output_dir_var,
                                  enable_padding_var=self.enable_padding_var,
                                  enable_crc_correction_var=self.enable_crc_correction_var,
                                  create_backup_var=self.create_backup_var)
        self.notebook.add(update_tab, text="一键更新 Mod")

        # Tab: CRC 工具
        crc_tab = CrcToolTab(self.notebook, self.logger, 
                             game_resource_dir_var=self.game_resource_dir_var,
                             enable_padding_var=self.enable_padding_var,
                             create_backup_var=self.create_backup_var)
        self.notebook.add(crc_tab, text="CRC 修正工具")

        # Tab: PNG 替换
        png_tab = PngReplacementTab(self.notebook, self.logger, 
                                    output_dir_var=self.output_dir_var,
                                    create_backup_var=self.create_backup_var)
        self.notebook.add(png_tab, text="PNG 文件夹替换")