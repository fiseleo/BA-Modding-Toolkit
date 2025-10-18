# ui.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinterdnd2 import DND_FILES
from pathlib import Path
import shutil
import threading
import os
import configparser

# 导入自定义模块
import processing
from utils import CRCUtils, get_environment_info, no_log

def _is_multiple_files_drop(data: str) -> bool:
    """
    检查拖放事件的数据是否包含多个文件路径。
    多个文件的 event.data 通常是 '{path1} {path2}' 的形式。
    """
    return '} {' in data


# --- 日志管理类 ---
class Logger:
    def __init__(self, master, log_widget: tk.Text, status_widget: tk.Label):
        self.master = master
        self.log_widget = log_widget
        self.status_widget = status_widget

    def log(self, message):
        """线程安全地向日志区域添加消息"""
        def _update_log():
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.insert(tk.END, message + "\n")
            self.log_widget.see(tk.END)
            self.log_widget.config(state=tk.DISABLED)
        
        self.master.after(0, _update_log)

    def status(self, message):
        """线程安全地更新状态栏消息"""
        def _update_status():
            self.status_widget.config(text=f"状态：{message}")
        
        self.master.after(0, _update_status)

    def clear(self):
        """清空日志区域"""
        def _clear_log():
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.delete('1.0', tk.END)
            self.log_widget.config(state=tk.DISABLED)
        
        self.master.after(0, _clear_log)

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
    LOG_FONT = ("SimSun", 9)


# --- UI 组件工厂 ---

class UIComponents:
    """一个辅助类，用于创建通用的UI组件，以减少重复代码。"""

    @staticmethod
    def _debounce_wraplength(event):
        """
        防抖处理函数，用于更新标签的 wraplength。
        只在窗口大小调整停止后执行。
        """
        widget = event.widget
        # 如果之前已经设置了定时器，先取消它
        if hasattr(widget, "_debounce_timer"):
            widget.after_cancel(widget._debounce_timer)
        
        # 设置一个新的定时器，在指定时间后执行更新操作
        widget._debounce_timer = widget.after(500, lambda: widget.config(wraplength=widget.winfo_width() - 10))

    @staticmethod
    def create_drop_zone(parent, title, drop_cmd, browse_cmd, label_text, button_text):
        """创建通用的拖放区域组件"""
        frame = tk.LabelFrame(parent, text=title, font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        frame.pack(fill=tk.X, pady=(0, 10))

        label = tk.Label(frame, text=label_text, relief=tk.GROOVE, height=4, bg=Theme.MUTED_BG, fg=Theme.TEXT_NORMAL, font=Theme.INPUT_FONT, justify=tk.LEFT)
        label.pack(fill=tk.X, pady=(0, 8))
        label.drop_target_register(DND_FILES)
        label.dnd_bind('<<Drop>>', drop_cmd)
        label.bind('<Configure>', UIComponents._debounce_wraplength)

        button = tk.Button(frame, text=button_text, command=browse_cmd, font=Theme.INPUT_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT)
        button.pack()
        return frame, label

    @staticmethod
    def create_file_drop_zone(parent, title, drop_cmd, browse_cmd):
        """创建文件拖放区域"""
        return UIComponents.create_drop_zone(
            parent, title, drop_cmd, browse_cmd, 
            "将文件拖放到此处\n或点击下方按钮选择", 
            "浏览文件..."
        )

    @staticmethod
    def create_folder_drop_zone(parent, title, drop_cmd, browse_cmd):
        """创建文件夹拖放区域"""
        return UIComponents.create_drop_zone(
            parent, title, drop_cmd, browse_cmd,
            "将文件夹拖放到此处\n或点击下方按钮选择",
            "浏览文件夹..."
        )

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

        select_btn = tk.Button(frame, text="选", command=select_cmd, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=3)
        select_btn.pack(side=tk.LEFT, padx=(0, 5))
        open_btn = tk.Button(frame, text="开", command=open_cmd, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SECONDARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=3)
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

    def get_game_search_dirs(self, base_game_dir: Path, auto_detect_subdirs: bool) -> list[Path]:
        if auto_detect_subdirs:
            return [
                base_game_dir / "BlueArchive_Data/StreamingAssets/PUB/Resource/GameData/Windows",
                base_game_dir / "BlueArchive_Data/StreamingAssets/PUB/Resource/Preload/Windows"
            ]
        else:
            return [base_game_dir]


def replace_file(source_path: Path, 
                    dest_path: Path, 
                    create_backup: bool = True, 
                    ask_confirm: bool = True,
                    confirm_message: str = "",
                    log = no_log, 
                ) -> bool: 
    """ 
    安全地替换文件，包含确认、备份和日志记录功能。 
    返回操作是否成功。 
    """ 
    if not source_path or not source_path.exists(): 
        messagebox.showerror("错误", f"源文件不存在:\n{source_path}") 
        return False 
    if not dest_path or not dest_path.exists(): 
        messagebox.showerror("错误", f"目标文件不存在:\n{dest_path}") 
        return False 
    if source_path == dest_path: 
        messagebox.showerror("错误", "源文件和目标文件不能相同！") 
        return False

    if ask_confirm and not messagebox.askyesno("警告", confirm_message): 
        return False 

    try: 
        backup_message = "" 
        if create_backup: 
            backup_path = dest_path.with_suffix(dest_path.suffix + '.backup') 
            log(f"  > 正在备份原始文件到: {backup_path.name}") 
            shutil.copy2(dest_path, backup_path) 
            backup_message = f"\n\n原始文件备份至:\n{backup_path.name}" 
        
        log(f"  > 正在用 '{source_path.name}' 覆盖 '{dest_path.name}'...") 
        shutil.copy2(source_path, dest_path) 
        
        log("✅ 文件已成功覆盖！") 
        messagebox.showinfo("成功", f"文件已成功覆盖！{backup_message}") 
        return True 

    except Exception as e: 
        log(f"❌ 文件覆盖失败: {e}") 

        messagebox.showerror("错误", f"文件覆盖过程中发生错误:\n{e}") 
        return False 


# --- 具体 Tab 实现 ---

class ModUpdateTab(TabFrame):
    def create_widgets(self, game_resource_dir_var, output_dir_var, enable_padding_var, enable_crc_correction_var, create_backup_var, replace_texture2d_var, replace_textasset_var, replace_mesh_var, replace_all_var, compression_method_var, auto_detect_subdirs_var, enable_spine_conversion_var, spine_converter_path_var, target_spine_version_var):
        self.old_mod_path: Path = None
        self.new_mod_path: Path = None 
        self.final_output_path: Path = None
        self.enable_padding: bool = enable_padding_var
        self.enable_crc_correction: bool = enable_crc_correction_var
        self.create_backup: bool = create_backup_var
        self.compression_method = compression_method_var
        
        # 接收新的资源类型变量
        self.replace_texture2d: bool = replace_texture2d_var
        self.replace_textasset: bool = replace_textasset_var
        self.replace_mesh: bool = replace_mesh_var
        self.replace_all: bool = replace_all_var

        # 接收共享的变量
        self.game_resource_dir_var: Path = game_resource_dir_var
        self.output_dir_var: Path = output_dir_var
        self.auto_detect_subdirs = auto_detect_subdirs_var
        
        # 接收Spine相关的配置变量
        self.enable_spine_conversion_var = enable_spine_conversion_var
        self.spine_converter_path_var = spine_converter_path_var
        self.target_spine_version_var = target_spine_version_var

        # 1. 旧版 Mod 文件
        _, self.old_mod_label = UIComponents.create_file_drop_zone(
            self, "旧版 Mod Bundle", self.drop_old_mod, self.browse_old_mod
        )
        
        # 2. 新版游戏资源文件
        new_mod_frame, self.new_mod_label = UIComponents.create_file_drop_zone(
            self, "目标 Bundle 文件", self.drop_new_mod, self.browse_new_mod
        )
        # 自定义拖放区的提示文本，使其更具指导性
        self.new_mod_label.config(text="拖入旧版Mod后将自动查找目标资源\n或手动拖放/浏览文件")

        # 创建并插入用于显示游戏资源目录的额外组件
        auto_find_frame = tk.Frame(new_mod_frame, bg=Theme.FRAME_BG)
        # 使用 pack 的 before 参数，将此组件插入到拖放区标签(self.new_mod_label)的上方
        auto_find_frame.pack(fill=tk.X, pady=(0, 8), before=self.new_mod_label)
        tk.Label(auto_find_frame, text="查找路径:", bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL).pack(side=tk.LEFT, padx=(0,5))
        tk.Entry(auto_find_frame, textvariable=self.game_resource_dir_var, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 3. 选项和操作
        
        # --- 资源替换类型选项 ---
        replace_options_frame = tk.LabelFrame(self, text="替换资源类型", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        replace_options_frame.pack(fill=tk.X, pady=(0, 10))
        
        checkbox_container = tk.Frame(replace_options_frame, bg=Theme.FRAME_BG)
        checkbox_container.pack(fill=tk.X)
        
        tk.Checkbutton(checkbox_container, text="ALL", variable=self.replace_all, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG).pack(side=tk.LEFT)
        tk.Checkbutton(checkbox_container, text="Texture2D", variable=self.replace_texture2d, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG).pack(side=tk.LEFT, padx=(0, 20))
        tk.Checkbutton(checkbox_container, text="TextAsset", variable=self.replace_textasset, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG).pack(side=tk.LEFT, padx=(0, 20))
        tk.Checkbutton(checkbox_container, text="Mesh", variable=self.replace_mesh, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG).pack(side=tk.LEFT, padx=(0, 20))

        # --- 选项结束 ---

        # 操作按钮区域
        action_button_frame = tk.Frame(self) # 使用与父框架相同的背景色
        action_button_frame.pack(fill=tk.X, pady=10)
        action_button_frame.grid_columnconfigure((0, 1), weight=1)

        run_button = tk.Button(action_button_frame, text="开始一键更新", command=self.run_update_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SUCCESS_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=15, pady=8)
        run_button.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=2)
        
        self.replace_button = tk.Button(action_button_frame, text="覆盖原文件", command=self.replace_original_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_DANGER_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=15, pady=8, state=tk.DISABLED)
        self.replace_button.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=2)

    # 旧版 Mod 的处理方法，增加自动查找回调
    def drop_old_mod(self, event):
        if _is_multiple_files_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
        path = Path(event.data.strip('{}'))
        self.set_file_path('old_mod_path', self.old_mod_label, path, "旧版 Mod", self.auto_find_new_bundle)

    def browse_old_mod(self):
        p = filedialog.askopenfilename(title="选择旧版 Mod Bundle")
        if p:
            self.set_file_path('old_mod_path', self.old_mod_label, Path(p), "旧版 Mod", self.auto_find_new_bundle)

    def drop_new_mod(self, event):
        if _is_multiple_files_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
        path = Path(event.data.strip('{}'))
        self.set_new_mod_file(path)

    def browse_new_mod(self):
        p = filedialog.askopenfilename(title="选择目标资源 Bundle")
        if p:
            self.set_new_mod_file(Path(p))
            
    def set_new_mod_file(self, path: Path):
        """统一设置目标资源文件的路径和UI显示"""
        self.new_mod_path = path
        self.new_mod_label.config(text=f"已选择目标资源:{path.name}", fg=Theme.COLOR_SUCCESS)
        self.logger.log(f"已加载目标资源: {path}")
        self.logger.status("已加载目标资源")

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
        
        # 使用通用函数构造搜索路径
        base_game_dir = Path(self.game_resource_dir_var.get())
        search_paths = self.get_game_search_dirs(base_game_dir, self.auto_detect_subdirs.get())

        found_path, message = processing.find_new_bundle_path(
            self.old_mod_path,
            search_paths,
            self.logger.log
        )
        
        if found_path:
            self.master.after(0, self.set_new_mod_file, found_path)
        else:
            short_message = message.split('。')[0]
            ui_message = f"❌ 未找到资源: {short_message}"
            self.new_mod_label.config(text=ui_message, fg=Theme.COLOR_ERROR)
            self.logger.status("未找到匹配的目标资源")

    def run_update_thread(self):
        if not all([self.old_mod_path, self.new_mod_path, self.game_resource_dir_var.get(), self.output_dir_var.get()]):
            messagebox.showerror("错误", "请确保已分别指定旧版Mod、目标资源 Bundle，并设置了游戏资源目录和输出目录。")
            return
        
        # 检查是否至少选择了一种资源类型
        if not any([self.replace_texture2d.get(), self.replace_textasset.get(), self.replace_mesh.get(), self.replace_all.get()]):
            messagebox.showerror("错误", "请至少选择一种要替换的资源类型（如 Texture2D）。")
            return

        self.run_in_thread(self.run_update)

    def run_update(self):
        # --- 修改: 增加按钮状态管理和路径记录 ---
        # 每次开始更新时，先禁用替换按钮
        self.final_output_path = None
        self.master.after(0, lambda: self.replace_button.config(state=tk.DISABLED))

        output_dir_base = Path(self.output_dir_var.get())
        # 直接将基础输出目录传递给 processing 函数，它会创建子目录
        output_dir = output_dir_base 

        try:
            # 确保基础输出目录存在
            output_dir.mkdir(parents=True, exist_ok=True) 
        except Exception as e:
            messagebox.showerror("错误", f"无法创建输出目录:\n{output_dir}\n\n错误详情: {e}")
            return

        self.logger.log("\n" + "="*50)
        self.logger.log("开始一键更新 Mod...")
        self.logger.status("正在处理中，请稍候...")
        
        # 构建要替换的资源类型集合
        asset_types_to_replace = set()
        if self.replace_all.get():
            # 如果选择了ALL，则替换所有类型的资源
            asset_types_to_replace = {"ALL"}
        else:
            # 否则根据具体选择的类型来设置
            if self.replace_texture2d.get():
                asset_types_to_replace.add("Texture2D")
            if self.replace_textasset.get():
                asset_types_to_replace.add("TextAsset")
            if self.replace_mesh.get():
                asset_types_to_replace.add("Mesh")
        
        # 传递 output_dir (基础输出目录) 和资源类型集合
        # 根据设置决定是否传入spine_converter_path
        spine_converter_path = None
        if self.enable_spine_conversion_var.get():
            spine_converter_path = Path(self.spine_converter_path_var.get())
        
        success, message = processing.process_mod_update(
            old_mod_path = self.old_mod_path,
            new_bundle_path = self.new_mod_path,
            output_dir = output_dir,
            enable_padding = self.enable_padding.get(), 
            perform_crc = self.enable_crc_correction.get(),
            asset_types_to_replace = asset_types_to_replace,
            compression = self.compression_method.get(),
            spine_converter_path = spine_converter_path,
            target_spine_version = self.target_spine_version_var.get(),
            log = self.logger.log
        )
        
        if not success:
            messagebox.showerror("失败", message)
            return

        # 成功后，记录最终文件路径并启用按钮
        generated_bundle_filename = self.new_mod_path.name
        self.final_output_path = output_dir / generated_bundle_filename
        
        # 检查文件是否存在
        if self.final_output_path.exists():
            self.logger.log(f"✅ 更新成功。最终文件路径: {self.final_output_path}")
            self.logger.log(f"现在可以点击 '覆盖游戏原文件' 按钮来应用 Mod。")
            self.master.after(0, lambda: self.replace_button.config(state=tk.NORMAL))
            messagebox.showinfo("成功", message)
        else:
            # 如果文件不存在，但process_mod_update返回成功，仍需显示消息
            self.logger.log(f"⚠️ 警告: 更新成功，但无法找到生成的 Mod 文件。请在 '{output_dir}' 目录中查找。")
            self.master.after(0, lambda: self.replace_button.config(state=tk.DISABLED)) # 禁用替换按钮，因为路径未知
            messagebox.showinfo("成功 (路径未知)", message + "\n\n⚠️ 警告：无法自动找到生成的 Mod 文件，请在输出目录中手动查找。")
        
        self.logger.status("处理完成")

    # 替换原始文件相关方法
    def replace_original_thread(self):
        """启动替换原始游戏文件的线程"""
        if not self.final_output_path or not self.final_output_path.exists():
            messagebox.showerror("错误", "找不到已生成的 Mod 文件。\n请先成功执行一次'一键更新'。")
            return
        if not self.new_mod_path or not self.new_mod_path.exists():
            messagebox.showerror("错误", "找不到原始游戏资源文件路径。\n请确保在更新前已正确指定目标资源 Bundle。")
            return
        
        self.run_in_thread(self.replace_original)

    def replace_original(self):
        """执行实际的文件替换操作（在线程中）"""
        target_file = self.new_mod_path
        source_file = self.final_output_path
        
        success = replace_file(
            source_path=source_file,
            dest_path=target_file,
            create_backup=self.create_backup.get(),
            ask_confirm=True,
            confirm_message=f"此操作将覆盖资源目录中的原始文件:\n\n{self.new_mod_path}\n\n"
                            "如果要继续，请确保已备份原始文件，或是在全局设置中开启备份功能。\n\n确定要继续吗？",
            log=self.logger.log,
        )


class AssetReplacementTab(TabFrame):
    def create_widgets(self, output_dir_var, enable_padding_var, enable_crc_correction_var, create_backup_var, compression_method_var, enable_spine_conversion_var, spine_converter_path_var, target_spine_version_var):
        self.bundle_path: Path = None
        self.folder_path: Path = None
        self.final_output_path: Path = None
        
        # 接收共享变量
        self.output_dir_var = output_dir_var
        self.enable_padding = enable_padding_var
        self.enable_crc_correction = enable_crc_correction_var
        self.create_backup = create_backup_var
        self.compression_method = compression_method_var
        
        # 接收Spine相关的配置变量
        self.enable_spine_conversion_var = enable_spine_conversion_var
        self.spine_converter_path_var = spine_converter_path_var
        self.target_spine_version_var = target_spine_version_var

        # 1. 资源文件夹
        _, self.folder_label = UIComponents.create_folder_drop_zone(
            self, "替换资源文件夹", self.drop_folder, self.browse_folder
        )

        # 2. 目标 Bundle 文件
        _, self.bundle_label = UIComponents.create_file_drop_zone(
            self, "目标 Bundle 文件", self.drop_bundle, self.browse_bundle
        )
        
        # Spine转换器选项（使用Settings窗口的全局设置）
        # 这里不显示UI控件，直接使用从Settings传入的共享变量
        
        # 4. 操作按钮区域
        action_button_frame = tk.Frame(self)
        action_button_frame.pack(fill=tk.X, pady=10)
        action_button_frame.grid_columnconfigure((0, 1), weight=1)

        run_button = tk.Button(action_button_frame, text="生成替换文件", command=self.run_replacement_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SUCCESS_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=15, pady=8)
        run_button.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=10)
        
        self.replace_button = tk.Button(action_button_frame, text="覆盖原文件", command=self.replace_original_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_DANGER_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=15, pady=8, state=tk.DISABLED)
        self.replace_button.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=10)

    def drop_bundle(self, event):
        if _is_multiple_files_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
        self.set_file_path('bundle_path', self.bundle_label, Path(event.data.strip('{}')), "目标 Bundle")
    def browse_bundle(self):
        p = filedialog.askopenfilename(title="选择目标 Bundle 文件")
        if p: self.set_file_path('bundle_path', self.bundle_label, Path(p), "目标 Bundle")
    
    def drop_folder(self, event):
        if _is_multiple_files_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件夹。")
            return
        
        # 获取拖放的文件路径并转换为Path对象
        dropped_path = Path(event.data.strip('{}'))
        
        # 检查是否是文件夹
        if not dropped_path.is_dir():
            messagebox.showwarning("操作无效", "请输入包含了要替换文件的文件夹。")
            return
            
        self.set_folder_path('folder_path', self.folder_label, dropped_path, "替换资源文件夹")
    def browse_folder(self):
        p = filedialog.askdirectory(title="选择替换资源文件夹")
        if p: self.set_folder_path('folder_path', self.folder_label, Path(p), "替换资源文件夹")

    def run_replacement_thread(self):
        if not all([self.bundle_path, self.folder_path, self.output_dir_var.get()]):
            messagebox.showerror("错误", "请确保已选择目标 Bundle、替换资源文件夹，并在全局设置中指定了输出目录。")
            return
        self.run_in_thread(self.run_replacement)

    def run_replacement(self):
        self.final_output_path = None
        self.master.after(0, lambda: self.replace_button.config(state=tk.DISABLED))

        output_dir = Path(self.output_dir_var.get())
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建输出目录:\n{output_dir}\n\n错误详情: {e}")
            return

        self.logger.log("\n" + "="*50)
        self.logger.log("开始从资源文件夹替换...")
        self.logger.status("正在处理中，请稍候...")
        
        # 根据设置决定是否传入spine_converter_path
        spine_converter_path = None
        if self.enable_spine_conversion_var.get():
            spine_converter_path = Path(self.spine_converter_path_var.get())
        
        success, message = processing.process_asset_replacement(
            target_bundle_path = self.bundle_path,
            asset_folder = self.folder_path,
            output_dir = output_dir,
            perform_crc = self.enable_crc_correction.get(),
            enable_padding = self.enable_padding.get(),
            compression = self.compression_method.get(),
            spine_converter_path = spine_converter_path,
            target_spine_version = self.target_spine_version_var.get(),
            log = self.logger.log
        )
        
        if success:
            generated_bundle_filename = self.bundle_path.name
            self.final_output_path = output_dir / generated_bundle_filename
            
            if self.final_output_path.exists():
                self.logger.log(f"✅ 替换成功。最终文件路径: {self.final_output_path}")
                self.logger.log(f"现在可以点击 '覆盖原文件' 按钮来应用更改。")
                self.master.after(0, lambda: self.replace_button.config(state=tk.NORMAL))
                messagebox.showinfo("成功", message)
            else:
                self.logger.log(f"⚠️ 警告: 替换成功，但无法找到生成的 Mod 文件。请在 '{output_dir}' 目录中查找。")
                self.master.after(0, lambda: self.replace_button.config(state=tk.DISABLED))
                messagebox.showinfo("成功 (路径未知)", message + "\n\n⚠️ 警告：无法自动找到生成的文件，请在输出目录中手动查找。")
        else:
            messagebox.showerror("失败", message)
        
        self.logger.status("处理完成")

    def replace_original_thread(self):
        """启动替换原始游戏文件的线程"""
        if not self.final_output_path or not self.final_output_path.exists():
            messagebox.showerror("错误", "找不到已生成的替换文件。\n请先成功执行一次'生成替换文件'。")
            return
        if not self.bundle_path or not self.bundle_path.exists():
            messagebox.showerror("错误", "找不到原始目标文件路径。\n请确保在开始前已正确指定目标文件。")
            return
        
        self.run_in_thread(self.replace_original)



    def replace_original(self):
        """执行实际的文件替换操作（在线程中）"""
        target_file = self.bundle_path
        source_file = self.final_output_path
        
        success = replace_file(
            source_path=source_file,
            dest_path=target_file,
            create_backup=self.create_backup.get(),
            ask_confirm=True,
            confirm_message=f"此操作将覆盖原始文件:\n\n{self.bundle_path.name}\n\n"
                            "如果要继续，请确保已备份原始文件，或是在全局设置中开启备份功能。\n\n确定要继续吗？",
            log=self.logger.log,
        )

class CrcToolTab(TabFrame):
    def create_widgets(self, game_resource_dir_var, enable_padding_var, create_backup_var, auto_detect_subdirs_var):
        self.original_path = None
        self.modified_path = None
        self.enable_padding = enable_padding_var
        self.create_backup = create_backup_var
        # 接收共享的游戏资源目录变量
        self.game_resource_dir_var = game_resource_dir_var
        self.auto_detect_subdirs = auto_detect_subdirs_var

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
        tk.Label(auto_find_frame, text="查找路径:", bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL).pack(side=tk.LEFT, padx=(0,5))
        tk.Entry(auto_find_frame, textvariable=self.game_resource_dir_var, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 3. 选项与操作
        options_frame = tk.LabelFrame(self, text="选项与操作", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        button_frame = tk.Frame(options_frame, bg=Theme.FRAME_BG)
        button_frame.pack(fill=tk.X, pady=10)
        button_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        tk.Button(button_frame, text="运行CRC修正", command=self.run_correction_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SUCCESS_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=0, sticky="ew", padx=5)
        tk.Button(button_frame, text="计算CRC值", command=self.calculate_values_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(button_frame, text="替换原始文件", command=self.replace_original_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_DANGER_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=10, pady=5).grid(row=0, column=2, sticky="ew", padx=5)

    def drop_original(self, event): 
        if _is_multiple_files_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
        self.set_original_file(Path(event.data.strip('{}')))
    def browse_original(self):
        p = filedialog.askopenfilename(title="请选择原始文件")
        if p: 
            self.set_original_file(Path(p))
    
    def drop_modified(self, event): 
        if _is_multiple_files_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
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
        if not game_dir_str:
            self.logger.log("⚠️ 警告: 未设置游戏资源目录，无法自动寻找原始文件。")
            return

        base_game_dir = Path(game_dir_str)
        if not base_game_dir.is_dir():
            self.logger.log(f"⚠️ 警告: 游戏资源目录 '{game_dir_str}' 不存在。")
            return
        
        # 使用通用函数构造搜索目录列表
        search_dirs = self.get_game_search_dirs(base_game_dir, self.auto_detect_subdirs.get())

        found = False
        for directory in search_dirs:
            if not directory.is_dir():
                continue # 跳过不存在的子目录
            
            candidate = directory / path.name
            if candidate.exists():
                self.set_original_file(candidate)
                self.logger.log(f"已在 '{directory.name}' 中自动找到并加载原始文件: {candidate.name}")
                found = True
                break # 找到后即停止搜索
        
        if not found:
            self.logger.log(f"⚠️ 警告: 未能在指定的资源目录中找到对应的原始文件 '{path.name}'。")

    def _validate_paths(self):
        if not self.original_path or not self.modified_path:
            messagebox.showerror("错误", "请同时提供原始文件和修改后文件。")
            return False
        return True

    def run_correction_thread(self):
        if self._validate_paths(): self.run_in_thread(self.run_correction)

    def calculate_values_thread(self):
        # 检查路径情况
        if not self.modified_path:
            messagebox.showerror("错误", "请至少提供一个文件路径。")
            return
        
        # 如果只有修改后文件，计算其CRC32值
        if not self.original_path:
            self.run_in_thread(self.calculate_single_value)
        # 如果两个文件都有，保持原有行为
        else:
            self.run_in_thread(self.calculate_values)

    def replace_original_thread(self):
        if self._validate_paths(): self.run_in_thread(self.replace_original)

    def run_correction(self):
        self.logger.log("\n" + "="*50)
        self.logger.log("开始CRC修正过程...")
        self.logger.status("正在进行CRC修正...")
        try:
            # 先检测CRC是否一致
            self.logger.log("正在检测CRC值是否匹配...")
            try:
                is_crc_match = CRCUtils.check_crc_match(self.original_path, self.modified_path)
            except Exception as e:
                self.logger.log(f"⚠️ 警告: 检测CRC值时发生错误: {e}")
                messagebox.showerror("错误", "检测CRC值时发生错误。请检查原始文件和修改后文件是否正确。")
                self.logger.status("CRC检测失败")
                return False
            
            
            if is_crc_match:
                self.logger.log("✅ CRC值已匹配，无需修正")
                messagebox.showinfo("CRC检测结果", "CRC值已匹配，无需进行修正操作。")
                self.logger.status("CRC检测完成")
                return True
            
            self.logger.log("❌ CRC值不匹配，开始进行CRC修正...")
            
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
            success = CRCUtils.manipulate_crc(self.original_path, self.modified_path, self.enable_padding.get())
            
            if success:
                self.logger.log("✅ CRC修正成功！")
                messagebox.showinfo("成功", f"CRC 修正成功！\n修改后的文件已更新。{backup_message}")
            else:
                self.logger.log("❌ CRC修正失败")
                messagebox.showerror("失败", "CRC 修正失败。")
            self.logger.status("CRC修正完成")
            return success
                
        except Exception as e:
            self.logger.log(f"❌ 错误：{e}")
            messagebox.showerror("错误", f"执行过程中发生错误:\n{e}")
            self.logger.status("CRC修正失败")
            return False
        
    def calculate_single_value(self):
        """计算单个文件的CRC32值"""
        self.logger.status("正在计算CRC...")
        try:
            with open(self.modified_path, "rb") as f: file_data = f.read()

            crc_hex = f"{CRCUtils.compute_crc32(file_data):08X}"
            
            self.logger.log(f"文件 CRC32: {crc_hex}")
            messagebox.showinfo("CRC计算结果", f"文件 CRC32: {crc_hex}")
            
        except Exception as e:
            self.logger.log(f"❌ 计算CRC时发生错误: {e}")
            messagebox.showerror("错误", f"计算CRC时发生错误:\n{e}")

    def calculate_values(self):
        """计算两个文件的CRC32值，并判断是否匹配"""
        self.logger.status("正在计算CRC...")
        try:
            with open(self.original_path, "rb") as f: original_data = f.read()
            with open(self.modified_path, "rb") as f: modified_data = f.read()

            original_crc_hex = f"{CRCUtils.compute_crc32(original_data):08X}"
            modified_crc_hex = f"{CRCUtils.compute_crc32(modified_data):08X}"
            
            self.logger.log(f"修改后文件 CRC32: {modified_crc_hex}")
            self.logger.log(f"原始文件 CRC32: {original_crc_hex}")

            msg = f"修改后文件 CRC32: {modified_crc_hex}\n原始文件 CRC32: {original_crc_hex}\n"

            if original_crc_hex == modified_crc_hex:
                self.logger.log("    CRC值匹配: ✅是")
                messagebox.showinfo("CRC计算结果", f"{msg}\n✅ CRC值匹配: 是")
            else:
                self.logger.log("    CRC值匹配: ❌否")
                messagebox.showwarning("CRC计算结果", f"{msg}\n❌ CRC值匹配: 否")
        except Exception as e:
            self.logger.log(f"❌ 计算CRC时发生错误: {e}")
            messagebox.showerror("错误", f"计算CRC时发生错误:\n{e}")

    def replace_original(self):
        success = replace_file(
            source_path=self.modified_path,
            dest_path=self.original_path,
            create_backup=self.create_backup.get(),
            ask_confirm=True,
            confirm_message="确定要用修改后的文件替换原始文件吗？\n\n此操作不可逆，建议先备份原始文件！",
            log=self.logger.log,
        )


class BatchModUpdateTab(TabFrame):
    def create_widgets(self, game_resource_dir_var, output_dir_var, enable_padding_var, enable_crc_correction_var, create_backup_var, replace_texture2d_var, replace_textasset_var, replace_mesh_var, replace_all_var, compression_method_var, auto_detect_subdirs_var):
        self.mod_file_list: list[Path] = []
        
        # 接收共享变量
        self.game_resource_dir_var = game_resource_dir_var
        self.output_dir_var = output_dir_var
        self.enable_padding = enable_padding_var
        self.enable_crc_correction = enable_crc_correction_var
        self.create_backup = create_backup_var
        self.replace_texture2d = replace_texture2d_var
        self.replace_textasset = replace_textasset_var
        self.replace_mesh = replace_mesh_var
        self.replace_all = replace_all_var
        self.compression_method = compression_method_var
        self.auto_detect_subdirs = auto_detect_subdirs_var

        # --- 1. 输入区域 ---
        input_frame = tk.LabelFrame(self, text="输入 Mod 文件/文件夹", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # 配置input_frame的网格，让列表框区域(row 1)可以垂直扩展
        input_frame.rowconfigure(1, weight=1)
        input_frame.columnconfigure(0, weight=1)


        # 拖放区
        drop_label = tk.Label(input_frame, text="将文件或文件夹拖放到此处\n支持多选文件和文件夹", relief=tk.GROOVE, height=3, bg=Theme.MUTED_BG, fg=Theme.TEXT_NORMAL, font=Theme.INPUT_FONT, justify=tk.LEFT)
        drop_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind('<<Drop>>', self.drop_mods)
        drop_label.bind('<Configure>', lambda e: e.widget.config(wraplength=e.width - 10))

        # 文件列表显示区
        list_frame = tk.Frame(input_frame, bg=Theme.FRAME_BG)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 10))
        # 配置list_frame的网格，让Listbox本身(0,0)可以双向扩展
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        self.file_listbox = tk.Listbox(list_frame, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, selectmode=tk.EXTENDED)
        
        # 创建并配置垂直和水平滚动条
        v_scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        h_scrollbar = tk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.file_listbox.xview)
        self.file_listbox.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 使用grid布局Listbox和滚动条
        self.file_listbox.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        # 按钮区
        button_frame = tk.Frame(input_frame, bg=Theme.FRAME_BG)
        button_frame.grid(row=2, column=0, sticky="ew")
        # 配置按钮区的网格列，使按钮均匀分布
        button_frame.columnconfigure((0, 1, 2, 3), weight=1)

        tk.Button(button_frame, text="添加文件", command=self.browse_add_files, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        tk.Button(button_frame, text="添加文件夹", command=self.browse_add_folder, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT).grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(button_frame, text="移除选中", command=self.remove_selected_files, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_WARNING_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT).grid(row=0, column=2, sticky="ew", padx=5)
        tk.Button(button_frame, text="清空列表", command=self.clear_list, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_DANGER_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT).grid(row=0, column=3, sticky="ew", padx=(5, 0))

        # --- 2. 资源替换类型选项 ---
        replace_options_frame = tk.LabelFrame(self, text="替换资源类型", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        replace_options_frame.pack(fill=tk.X, pady=(0, 10))
        
        checkbox_container = tk.Frame(replace_options_frame, bg=Theme.FRAME_BG)
        checkbox_container.pack(fill=tk.X)
        
        tk.Checkbutton(checkbox_container, text="ALL", variable=self.replace_all, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG).pack(side=tk.LEFT)
        tk.Checkbutton(checkbox_container, text="Texture2D", variable=self.replace_texture2d, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG).pack(side=tk.LEFT, padx=(0, 20))
        tk.Checkbutton(checkbox_container, text="TextAsset", variable=self.replace_textasset, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG).pack(side=tk.LEFT, padx=(0, 20))
        tk.Checkbutton(checkbox_container, text="Mesh", variable=self.replace_mesh, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG).pack(side=tk.LEFT, padx=(0, 20))

        # --- 3. 操作按钮 ---
        run_button = tk.Button(self, text="开始批量更新", command=self.run_batch_update_thread, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SUCCESS_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, padx=15, pady=8)
        run_button.pack(fill=tk.X, pady=10)

    def _add_files_to_list(self, file_paths: list[Path]):
        """辅助函数，用于向列表和Listbox添加文件，避免重复。"""
        added_count = 0
        for path in file_paths:
            if path not in self.mod_file_list:
                self.mod_file_list.append(path)
                # 插入完整路径，但显示时只显示文件名，这样更清晰
                self.file_listbox.insert(tk.END, f"{path.parent.name} / {path.name}")
                added_count += 1
        if added_count > 0:
            self.logger.log(f"已向处理列表添加 {added_count} 个文件。")
            self.logger.status(f"当前列表有 {len(self.mod_file_list)} 个文件待处理。")

    def drop_mods(self, event):
        # TkinterDnD 对多个文件的处理方式是返回一个包含花括号和空格的字符串
        # e.g., '{path/to/file1} {path/to/file2}'
        raw_paths = event.data.strip('{}').split('} {')
        
        paths_to_add = []
        for p_str in raw_paths:
            path = Path(p_str)
            if path.is_dir():
                # 如果是文件夹，则查找所有 .bundle 文件
                paths_to_add.extend(sorted(path.glob('*.bundle')))
            elif path.is_file():
                paths_to_add.append(path)
        
        if paths_to_add:
            self._add_files_to_list(paths_to_add)

    def browse_add_files(self):
        # askopenfilenames 支持多选
        filepaths = filedialog.askopenfilenames(title="选择一个或多个 Mod Bundle 文件")
        if filepaths:
            self._add_files_to_list([Path(p) for p in filepaths])

    def browse_add_folder(self):
        folder_path = filedialog.askdirectory(title="选择包含 Mod Bundle 文件的文件夹")
        if folder_path:
            path = Path(folder_path)
            bundle_files = sorted(path.glob('*.bundle'))
            if bundle_files:
                self._add_files_to_list(bundle_files)
            else:
                messagebox.showinfo("提示", "在该文件夹中没有找到任何 .bundle 文件。")

    def remove_selected_files(self):
        """移除在Listbox中选中的文件。"""
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "没有选中任何文件。")
            return

        # 从后往前删除，以避免索引变化导致错误
        for index in sorted(selected_indices, reverse=True):
            self.file_listbox.delete(index)
            del self.mod_file_list[index]
        
        removed_count = len(selected_indices)
        self.logger.log(f"已从处理列表移除 {removed_count} 个文件。")
        self.logger.status(f"当前列表有 {len(self.mod_file_list)} 个文件待处理。")

    def clear_list(self):
        self.mod_file_list.clear()
        self.file_listbox.delete(0, tk.END)
        self.logger.log("已清空处理列表。")
        self.logger.status("准备就绪")

    def run_batch_update_thread(self):
        if not self.mod_file_list:
            messagebox.showerror("错误", "处理列表为空，请先添加 Mod 文件。")
            return
        if not all([self.game_resource_dir_var.get(), self.output_dir_var.get()]):
            messagebox.showerror("错误", "请确保在全局设置中已指定游戏资源目录和输出目录。")
            return
        if not any([self.replace_texture2d.get(), self.replace_textasset.get(), self.replace_mesh.get(), self.replace_all.get()]):
            messagebox.showerror("错误", "请至少选择一种要替换的资源类型（如 Texture2D）。")
            return
        
        self.run_in_thread(self._batch_update_worker)

    def _batch_update_worker(self):
        self.logger.log("\n" + "#"*50)
        self.logger.log("🚀 开始批量更新 Mod...")
        self.logger.status("正在批量处理中...")

        output_dir = Path(self.output_dir_var.get())
        
        # 使用通用函数构造搜索路径
        base_game_dir = Path(self.game_resource_dir_var.get())
        search_paths = self.get_game_search_dirs(base_game_dir, self.auto_detect_subdirs.get())
        
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建输出目录:\n{output_dir}\n\n错误详情: {e}")
            self.logger.status("处理失败")
            return

        # 获取一次性设置
        asset_types_to_replace = set()
        if self.replace_all.get():
            # 如果选择了ALL，则替换所有类型的资源
            asset_types_to_replace = {"ALL"}
        else:
            # 否则根据具体选择的类型来设置
            if self.replace_texture2d.get():
                asset_types_to_replace.add("Texture2D")
            if self.replace_textasset.get():
                asset_types_to_replace.add("TextAsset")
            if self.replace_mesh.get():
                asset_types_to_replace.add("Mesh")
        
        enable_padding = self.enable_padding.get()
        perform_crc = self.enable_crc_correction.get()
        compression_method = self.compression_method.get()

        total_files = len(self.mod_file_list)
        success_count = 0
        fail_count = 0
        failed_tasks = []  # 记录失败的任务

        for i, old_mod_path in enumerate(self.mod_file_list):
            self.logger.log("\n" + "="*50)
            self.logger.log(f"({i+1}/{total_files}) 正在处理: {old_mod_path.name}")
            self.logger.status(f"正在处理 ({i+1}/{total_files}): {old_mod_path.name}")

            # 1. 查找对应的新版资源文件
            new_bundle_path, find_message = processing.find_new_bundle_path(
                old_mod_path, search_paths, self.logger.log
            )

            if not new_bundle_path:
                self.logger.log(f"❌ 查找失败: {find_message}")
                fail_count += 1
                failed_tasks.append(f"{old_mod_path.name} - 查找失败: {find_message}")
                continue

            # 2. 执行更新
            success, process_message = processing.process_mod_update(
                old_mod_path=old_mod_path,
                new_bundle_path=new_bundle_path,
                output_dir=output_dir,
                enable_padding=enable_padding,
                perform_crc=perform_crc,
                asset_types_to_replace=asset_types_to_replace,
                compression=compression_method,
                log=self.logger.log
            )

            if success:
                self.logger.log(f"✅ 处理成功: {old_mod_path.name}")
                success_count += 1
            else:
                self.logger.log(f"❌ 处理失败: {old_mod_path.name} - {process_message}")
                fail_count += 1
                failed_tasks.append(f"{old_mod_path.name} - {process_message}")
        
        # 批量处理结束
        summary_message = f"批量处理完成！\n\n总计: {total_files} 个文件\n成功: {success_count} 个\n失败: {fail_count} 个"
        
        self.logger.log("\n" + "#"*50)
        self.logger.log(summary_message)
        # 如果有失败的任务，在日志中详细列出
        if failed_tasks:
            self.logger.log(f"\n\n失败的更新任务:")
            for task in failed_tasks:
                self.logger.log(f"- {task}")
        self.logger.log("\n" + "#"*50)
        self.logger.status("批量处理完成")
        messagebox.showinfo("批量处理完成", summary_message)

# --- 配置管理类 ---

class ConfigManager:
    """配置管理类，负责保存和读取应用设置到config.ini文件"""
    
    def __init__(self, config_file="config.ini"):
        self.config_file = Path(config_file)
        self.config = configparser.ConfigParser()
        
    def save_config(self, app_instance):
        """保存当前应用配置到文件"""
        try:
            # 清空现有配置
            self.config.clear()
            
            # 添加目录设置
            self.config['Directories'] = {
                'game_resource_dir': app_instance.game_resource_dir_var.get(),
                'output_dir': app_instance.output_dir_var.get(),
                'auto_detect_subdirs': str(app_instance.auto_detect_subdirs_var.get())
            }
            
            # 添加全局选项
            self.config['GlobalOptions'] = {
                'enable_padding': str(app_instance.enable_padding_var.get()),
                'enable_crc_correction': str(app_instance.enable_crc_correction_var.get()),
                'create_backup': str(app_instance.create_backup_var.get()),
                'compression_method': app_instance.compression_method_var.get()
            }
            
            # 添加资源类型选项
            self.config['ResourceTypes'] = {
                'replace_texture2d': str(app_instance.replace_texture2d_var.get()),
                'replace_textasset': str(app_instance.replace_textasset_var.get()),
                'replace_mesh': str(app_instance.replace_mesh_var.get()),
                'replace_all': str(app_instance.replace_all_var.get())
            }
            
            # 添加Spine转换器选项
            self.config['SpineConverter'] = {
                'spine_converter_path': app_instance.spine_converter_path_var.get(),
                'enable_spine_conversion': str(app_instance.enable_spine_conversion_var.get()),
                'target_spine_version': app_instance.target_spine_version_var.get()
            }
            
            # 写入文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
                
            return True
        except Exception as e:
            print(f"保存配置时出错: {e}")
            return False
    
    def load_config(self, app_instance):
        """从文件加载配置到应用实例"""
        try:
            if not self.config_file.exists():
                return False
                
            self.config.read(self.config_file, encoding='utf-8')
            
            # 加载目录设置
            if 'Directories' in self.config:
                if 'game_resource_dir' in self.config['Directories']:
                    app_instance.game_resource_dir_var.set(self.config['Directories']['game_resource_dir'])
                if 'output_dir' in self.config['Directories']:
                    app_instance.output_dir_var.set(self.config['Directories']['output_dir'])
                if 'auto_detect_subdirs' in self.config['Directories']:
                    app_instance.auto_detect_subdirs_var.set(self.config['Directories']['auto_detect_subdirs'].lower() == 'true')
            
            # 加载全局选项
            if 'GlobalOptions' in self.config:
                if 'enable_padding' in self.config['GlobalOptions']:
                    app_instance.enable_padding_var.set(self.config['GlobalOptions']['enable_padding'].lower() == 'true')
                if 'enable_crc_correction' in self.config['GlobalOptions']:
                    app_instance.enable_crc_correction_var.set(self.config['GlobalOptions']['enable_crc_correction'].lower() == 'true')
                if 'create_backup' in self.config['GlobalOptions']:
                    app_instance.create_backup_var.set(self.config['GlobalOptions']['create_backup'].lower() == 'true')
                if 'compression_method' in self.config['GlobalOptions']:
                    app_instance.compression_method_var.set(self.config['GlobalOptions']['compression_method'])
            
            # 加载资源类型选项
            if 'ResourceTypes' in self.config:
                if 'replace_texture2d' in self.config['ResourceTypes']:
                    app_instance.replace_texture2d_var.set(self.config['ResourceTypes']['replace_texture2d'].lower() == 'true')
                if 'replace_textasset' in self.config['ResourceTypes']:
                    app_instance.replace_textasset_var.set(self.config['ResourceTypes']['replace_textasset'].lower() == 'true')
                if 'replace_mesh' in self.config['ResourceTypes']:
                    app_instance.replace_mesh_var.set(self.config['ResourceTypes']['replace_mesh'].lower() == 'true')
                if 'replace_all' in self.config['ResourceTypes']:
                    app_instance.replace_all_var.set(self.config['ResourceTypes']['replace_all'].lower() == 'true')
            
            # 加载Spine转换器选项
            if 'SpineConverter' in self.config:
                if 'spine_converter_path' in self.config['SpineConverter']:
                    app_instance.spine_converter_path_var.set(self.config['SpineConverter']['spine_converter_path'])
                if 'enable_spine_conversion' in self.config['SpineConverter']:
                    app_instance.enable_spine_conversion_var.set(self.config['SpineConverter']['enable_spine_conversion'].lower() == 'true')
                if 'target_spine_version' in self.config['SpineConverter']:
                    app_instance.target_spine_version_var.set(self.config['SpineConverter']['target_spine_version'])
            
            return True
        except Exception as e:
            print(f"加载配置时出错: {e}")
            return False

# --- 新增：高级设置弹窗 ---
class SettingsDialog(tk.Toplevel):
    def __init__(self, master, app_instance):
        super().__init__(master)
        self.app = app_instance # 保存主应用的引用

        self.title("高级设置")
        self.geometry("550x550")
        self.configure(bg=Theme.WINDOW_BG)
        self.transient(master) # 绑定到主窗口
        self.grab_set() # 模态化，阻止操作主窗口

        # --- 将原有的全局设置UI搬到这里 ---
        container = tk.Frame(self, bg=Theme.WINDOW_BG, padx=15, pady=15)
        container.pack(fill=tk.BOTH, expand=True)

        # --- 手动创建游戏资源目录UI，以实现动态标题 ---
        self.game_dir_frame = tk.LabelFrame(container, text="", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=10)
        self.game_dir_frame.pack(fill=tk.X, pady=(0, 10))

        # 内部容器，用于放置输入框和按钮
        entry_button_container = tk.Frame(self.game_dir_frame, bg=Theme.FRAME_BG)
        entry_button_container.pack(fill=tk.X)

        entry = tk.Entry(entry_button_container, textvariable=self.app.game_resource_dir_var, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)

        select_btn = tk.Button(entry_button_container, text="选", command=self.app.select_game_resource_directory, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=3)
        select_btn.pack(side=tk.LEFT, padx=(0, 5))
        open_btn = tk.Button(entry_button_container, text="开", command=self.app.open_game_resource_in_explorer, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SECONDARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=3)
        open_btn.pack(side=tk.LEFT)

        self.auto_detect_checkbox = tk.Checkbutton(
            self.game_dir_frame, 
            text="自动检测标准子目录 (GameData/Preload)",
            variable=self.app.auto_detect_subdirs_var,
            command=self._on_auto_detect_toggle,
            font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG
        )
        self.auto_detect_checkbox.pack(anchor='w', pady=(5, 0))
        # --- 游戏资源目录UI结束 ---

        UIComponents.create_directory_path_entry(
            container, "输出目录", self.app.output_dir_var,
            self.app.select_output_directory, self.app.open_output_dir_in_explorer
        )
        
        # 选项设置
        global_options_frame = tk.LabelFrame(container, text="全局选项", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        global_options_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.padding_checkbox = tk.Checkbutton(global_options_frame, text="添加私货", variable=self.app.enable_padding_var, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG)
        crc_checkbox = tk.Checkbutton(global_options_frame, text="CRC修正", variable=self.app.enable_crc_correction_var, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG, command=self.toggle_padding_checkbox_state)
        backup_checkbox = tk.Checkbutton(global_options_frame, text="创建备份", variable=self.app.create_backup_var, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG)

        # 压缩方式下拉框
        compression_frame = tk.Frame(global_options_frame, bg=Theme.FRAME_BG)
        compression_label = tk.Label(compression_frame, text="压缩方式", font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL)
        compression_combo = ttk.Combobox(compression_frame, textvariable=self.app.compression_method_var, values=["lzma", "lz4", "original", "none"], state="readonly", font=Theme.INPUT_FONT, width=10)

        # 布局 - 使用统一的grid布局确保高度对齐
        crc_checkbox.grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.padding_checkbox.grid(row=0, column=1, sticky="w", padx=(0, 5))
        backup_checkbox.grid(row=0, column=2, sticky="w", padx=(0, 5))
        
        compression_frame.grid(row=0, column=3, sticky="w", padx=(0, 5))
        compression_label.pack(side=tk.LEFT)
        compression_combo.pack(side=tk.LEFT)
        
        # 设置行权重确保垂直对齐
        global_options_frame.rowconfigure(0, weight=1)
        
        # Spine 转换器设置
        spine_frame = tk.LabelFrame(container, text="Spine 转换器设置", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=12)
        spine_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Spine 转换选项
        spine_options_frame = tk.Frame(spine_frame, bg=Theme.FRAME_BG)
        spine_options_frame.pack(fill=tk.X)
        
        spine_conversion_checkbox = tk.Checkbutton(spine_options_frame, text="启用 Spine 转换", variable=self.app.enable_spine_conversion_var, font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL, selectcolor=Theme.INPUT_BG)
        spine_conversion_checkbox.pack(side=tk.LEFT, padx=(0, 10))
        
        # 目标版本输入框
        spine_version_label = tk.Label(spine_options_frame, text="目标版本:", font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL)
        spine_version_label.pack(side=tk.LEFT, padx=(0, 5))
        
        spine_version_entry = tk.Entry(spine_options_frame, textvariable=self.app.target_spine_version_var, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1, width=10)
        spine_version_entry.pack(side=tk.LEFT)

        # Spine 转换器路径设置
        spine_path_frame = tk.Frame(spine_frame, bg=Theme.FRAME_BG)
        spine_path_frame.pack(fill=tk.X, pady=(0, 8))
        
        spine_path_label = tk.Label(spine_path_frame, text="Spine 转换器路径:", font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL)
        spine_path_label.pack(side=tk.LEFT, padx=(0, 5))
        
        spine_path_entry = tk.Entry(spine_path_frame, textvariable=self.app.spine_converter_path_var, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1)
        spine_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)
        
        spine_path_browse_btn = tk.Button(spine_path_frame, text="浏览", command=self.select_spine_converter_path, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=5)
        spine_path_browse_btn.pack(side=tk.LEFT, padx=(0, 5))

        # 初始化所有动态UI的状态
        self.toggle_padding_checkbox_state()
        self._on_auto_detect_toggle()
        
        # 添加配置操作按钮
        config_buttons_frame = tk.Frame(container, bg=Theme.WINDOW_BG)
        config_buttons_frame.pack(fill=tk.X, pady=(15, 0))
        
        # 配置网格布局，让三个按钮均匀分布
        config_buttons_frame.columnconfigure(0, weight=1)
        config_buttons_frame.columnconfigure(1, weight=1)
        config_buttons_frame.columnconfigure(2, weight=1)
        
        save_button = tk.Button(config_buttons_frame, text="Save", command=self.app.save_current_config,
                               font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SUCCESS_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT)
        save_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        load_button = tk.Button(config_buttons_frame, text="Load", command=self.load_config,
                               font=Theme.BUTTON_FONT, bg=Theme.BUTTON_WARNING_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT)
        load_button.grid(row=0, column=1, sticky="ew", padx=5)
        
        reset_button = tk.Button(config_buttons_frame, text="Default", command=self.reset_to_default,
                               font=Theme.BUTTON_FONT, bg=Theme.BUTTON_DANGER_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT)
        reset_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))

    def _on_auto_detect_toggle(self):
        """当自动检测复选框状态改变时，更新UI"""
        if self.app.auto_detect_subdirs_var.get():
            self.game_dir_frame.config(text="游戏根目录")
        else:
            self.game_dir_frame.config(text="自定义资源目录")

    def toggle_padding_checkbox_state(self):
        """根据CRC修正复选框的状态，启用或禁用添加私货复选框"""
        if self.app.enable_crc_correction_var.get():
            self.padding_checkbox.config(state=tk.NORMAL)
        else:
            self.app.enable_padding_var.set(False)
            self.padding_checkbox.config(state=tk.DISABLED)
    
    def load_config(self):
        """加载配置文件并更新UI"""
        if self.app.config_manager.load_config(self.app):
            self.app.logger.log("配置加载成功")
            messagebox.showinfo("成功", "配置已从 config.ini 加载")
            # 更新UI状态
            self.toggle_padding_checkbox_state()
            self._on_auto_detect_toggle()
        else:
            self.app.logger.log("配置加载失败")
            messagebox.showerror("错误", "配置加载失败，请检查配置文件是否存在")
    
    def reset_to_default(self):
        """重置为默认设置"""
        if messagebox.askyesno("确认", "确定要重置为默认设置吗？"):
            # 使用统一的默认值设置方法
            self.app._set_default_values()
            
            # 更新UI状态
            self.toggle_padding_checkbox_state()
            self._on_auto_detect_toggle()
            
            self.app.logger.log("已重置为默认设置")
    
    def select_spine_converter_path(self):
        """选择Spine转换器路径"""
        try:
            current_path = Path(self.app.spine_converter_path_var.get())
            if not current_path.exists():
                current_path = Path.home()
            
            selected_file = filedialog.askopenfilename(
                title="选择 Spine 转换器程序",
                initialdir=str(current_path.parent) if current_path.parent.exists() else str(current_path),
                filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")]
            )
            
            if selected_file:
                self.app.spine_converter_path_var.set(str(Path(selected_file)))
                self.app.logger.log(f"已设置 Spine 转换器路径: {selected_file}")
        except Exception as e:
            messagebox.showerror("错误", f"选择 Spine 转换器路径时发生错误:\n{e}")

# --- 主应用 ---

class App(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.setup_main_window()
        self.config_manager = ConfigManager()
        self.init_shared_variables()
        self.create_widgets()
        self.load_config_on_startup()  # 启动时加载配置
        self.logger.status("准备就绪")

    def setup_main_window(self):
        self.master.title("BA Modding Toolkit")
        self.master.geometry("700x850")
        self.master.configure(bg=Theme.WINDOW_BG)

    def _set_default_values(self):
        """设置所有共享变量的默认值。"""
        # 尝试定位游戏根目录
        game_root_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\BlueArchive")
        self.game_resource_dir_var.set(str(game_root_dir))
        self.auto_detect_subdirs_var.set(True)
        
        # 共享变量
        self.output_dir_var.set(str(Path.cwd() / "output"))
        self.enable_padding_var.set(False)
        self.enable_crc_correction_var.set(True)
        self.create_backup_var.set(True)
        self.compression_method_var.set("lzma")
        
        # 一键更新的资源类型选项
        self.replace_texture2d_var.set(True)
        self.replace_textasset_var.set(True)
        self.replace_mesh_var.set(True)
        self.replace_all_var.set(False)
        
        # Spine 转换器选项
        self.spine_converter_path_var.set("")
        self.enable_spine_conversion_var.set(False)
        self.target_spine_version_var.set("4.2.33")

    def init_shared_variables(self):
        """初始化所有Tabs共享的变量。"""
        # 创建变量
        self.game_resource_dir_var = tk.StringVar()
        self.auto_detect_subdirs_var = tk.BooleanVar()
        self.output_dir_var = tk.StringVar()
        self.enable_padding_var = tk.BooleanVar()
        self.enable_crc_correction_var = tk.BooleanVar()
        self.create_backup_var = tk.BooleanVar()
        self.compression_method_var = tk.StringVar()
        self.replace_texture2d_var = tk.BooleanVar()
        self.replace_textasset_var = tk.BooleanVar()
        self.replace_mesh_var = tk.BooleanVar()
        self.replace_all_var = tk.BooleanVar()
        
        # Spine 转换器选项
        self.spine_converter_path_var = tk.StringVar()
        self.enable_spine_conversion_var = tk.BooleanVar()
        self.target_spine_version_var = tk.StringVar()  # 添加目标Spine版本变量
        
        # 设置默认值
        self._set_default_values()

    def create_widgets(self):
        # 使用可拖动的 PanedWindow 替换固定的 grid 布局
        paned_window = ttk.PanedWindow(self.master, orient=tk.VERTICAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 上方控制面板
        top_frame = tk.Frame(paned_window, bg=Theme.WINDOW_BG)
        paned_window.add(top_frame, weight=1)

        # 下方日志区域
        bottom_frame = tk.Frame(paned_window, bg=Theme.WINDOW_BG)
        paned_window.add(bottom_frame, weight=1)

        # 顶部框架，用于放置设置按钮
        top_controls_frame = tk.Frame(top_frame, bg=Theme.WINDOW_BG)
        top_controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 使用grid布局让按钮横向拉伸填满
        settings_button = tk.Button(top_controls_frame, text="Settings", command=self.open_settings_dialog,
                                    font=Theme.BUTTON_FONT, bg=Theme.BUTTON_WARNING_BG, fg=Theme.BUTTON_FG,
                                    relief=tk.FLAT)
        settings_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        environment_button = tk.Button(top_controls_frame, text="Env", command=self.show_environment_info, 
                                       font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SECONDARY_BG, fg=Theme.BUTTON_FG, 
                                       relief=tk.FLAT)
        environment_button.grid(row=0, column=1, sticky="ew")
        
        # 设置列权重，让按钮均匀拉伸
        top_controls_frame.columnconfigure(0, weight=1)
        top_controls_frame.columnconfigure(1, weight=1)

        self.notebook = self.create_notebook(top_frame)
        
        # 创建日志区域
        self.log_text = self.create_log_area(bottom_frame)

        # 底部状态栏
        self.status_label = tk.Label(self.master, text="", bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                     font=Theme.INPUT_FONT, bg=Theme.STATUS_BAR_BG, fg=Theme.STATUS_BAR_FG, padx=10)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.logger = Logger(self.master, self.log_text, self.status_label)
        
        # 将 logger 和共享变量传递给 Tabs
        self.populate_notebook()

    def open_settings_dialog(self):
        """打开高级设置对话框"""
        dialog = SettingsDialog(self.master, self)
        self.master.wait_window(dialog) # 等待对话框关闭

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

    def show_environment_info(self):
        """显示环境信息"""
        self.logger.log(get_environment_info())

    def select_game_resource_directory(self):
        # 根据复选框状态决定对话框标题
        if self.auto_detect_subdirs_var.get():
            title = "选择游戏根目录"
        else:
            title = "选择自定义资源目录"
        self._select_directory(self.game_resource_dir_var, title)
        
    def open_game_resource_in_explorer(self):
        self._open_directory_in_explorer(self.game_resource_dir_var.get())

    def select_output_directory(self):
        self._select_directory(self.output_dir_var, "选择输出目录")

    def open_output_dir_in_explorer(self):
        self._open_directory_in_explorer(self.output_dir_var.get(), create_if_not_exist=True)
    
    def load_config_on_startup(self):
        """应用启动时自动加载配置"""
        if self.config_manager.load_config(self):
            self.logger.log("配置加载成功")
        else:
            self.logger.log("未找到配置文件，使用默认设置")
    
    def save_current_config(self):
        """保存当前配置到文件"""
        if self.config_manager.save_config(self):
            self.logger.log("配置保存成功")
            messagebox.showinfo("成功", "配置已保存到 config.ini")
        else:
            self.logger.log("配置保存失败")
            messagebox.showerror("错误", "配置保存失败")
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
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=0) # 日志区不需要顶部pady

        log_text = tk.Text(log_frame, wrap=tk.WORD, bg=Theme.LOG_BG, fg=Theme.LOG_FG, font=Theme.LOG_FONT, relief=tk.FLAT, bd=0, padx=5, pady=5, insertbackground=Theme.LOG_FG, height=10) #添加 height 参数
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
                                  create_backup_var=self.create_backup_var,
                                  replace_texture2d_var=self.replace_texture2d_var,
                                  replace_textasset_var=self.replace_textasset_var,
                                  replace_mesh_var=self.replace_mesh_var,
                                  replace_all_var=self.replace_all_var,
                                  compression_method_var=self.compression_method_var,
                                  auto_detect_subdirs_var=self.auto_detect_subdirs_var,
                                  enable_spine_conversion_var=self.enable_spine_conversion_var,
                                  spine_converter_path_var=self.spine_converter_path_var,
                                  target_spine_version_var=self.target_spine_version_var)
        self.notebook.add(update_tab, text="一键更新 Mod")

        # Tab: 批量更新
        batch_update_tab = BatchModUpdateTab(self.notebook, self.logger,
                                             game_resource_dir_var=self.game_resource_dir_var,
                                             output_dir_var=self.output_dir_var,
                                             enable_padding_var=self.enable_padding_var,
                                             enable_crc_correction_var=self.enable_crc_correction_var,
                                             create_backup_var=self.create_backup_var,
                                             replace_texture2d_var=self.replace_texture2d_var,
                                             replace_textasset_var=self.replace_textasset_var,
                                             replace_mesh_var=self.replace_mesh_var,
                                             replace_all_var=self.replace_all_var,
                                             compression_method_var=self.compression_method_var,
                                             auto_detect_subdirs_var=self.auto_detect_subdirs_var)
        self.notebook.add(batch_update_tab, text="批量更新 Mod")

        # Tab: CRC 工具
        crc_tab = CrcToolTab(self.notebook, self.logger, 
                             game_resource_dir_var=self.game_resource_dir_var,
                             enable_padding_var=self.enable_padding_var,
                             create_backup_var=self.create_backup_var,
                             auto_detect_subdirs_var=self.auto_detect_subdirs_var)
        self.notebook.add(crc_tab, text="CRC 修正工具")

        # Tab: 资源文件夹替换
        asset_tab = AssetReplacementTab(self.notebook, self.logger, 
                                    output_dir_var=self.output_dir_var,
                                    enable_padding_var=self.enable_padding_var,
                                    enable_crc_correction_var=self.enable_crc_correction_var,
                                    create_backup_var=self.create_backup_var,
                                    compression_method_var=self.compression_method_var,
                                    enable_spine_conversion_var=self.enable_spine_conversion_var,
                                    spine_converter_path_var=self.spine_converter_path_var,
                                    target_spine_version_var=self.target_spine_version_var)
        self.notebook.add(asset_tab, text="资源文件夹替换")

if __name__ == "__main__":
    from tkinterdnd2 import TkinterDnD
    from ui import App

    # 使用 TkinterDnD.Tk() 作为主窗口以支持拖放
    root = TkinterDnD.Tk()
    
    # 创建并运行应用
    app = App(root)
    
    # 启动 Tkinter 事件循环
    root.mainloop()