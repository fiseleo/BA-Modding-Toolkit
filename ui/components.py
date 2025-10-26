# ui/components.py

import tkinter as tk
from tkinterdnd2 import DND_FILES

# --- 日志管理类 ---
class Logger:
    def __init__(self, master, log_widget: tk.Text, status_widget: tk.Label):
        self.master = master
        self.log_widget = log_widget
        self.status_widget = status_widget

    def log(self, message: str) -> None:
        """线程安全地向日志区域添加消息"""
        def _update_log() -> None:
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.insert(tk.END, message + "\n")
            self.log_widget.see(tk.END)
            self.log_widget.config(state=tk.DISABLED)
        
        self.master.after(0, _update_log)

    def status(self, message: str) -> None:
        """线程安全地更新状态栏消息"""
        def _update_status() -> None:
            self.status_widget.config(text=f"状态：{message}")
        
        self.master.after(0, _update_status)

    def clear(self) -> None:
        """清空日志区域"""
        def _clear_log() -> None:
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
    def _debounce_wraplength(event: tk.Event) -> None:
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
        frame = tk.LabelFrame(parent, text=title, font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=15, pady=8)
        frame.pack(fill=tk.X, pady=5)

        entry = tk.Entry(frame, textvariable=textvariable, font=Theme.INPUT_FONT, bg=Theme.INPUT_BG, fg=Theme.TEXT_NORMAL, relief=tk.SUNKEN, bd=1)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)

        select_btn = tk.Button(frame, text="选", command=select_cmd, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_PRIMARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=3)
        select_btn.pack(side=tk.LEFT, padx=(0, 5))
        open_btn = tk.Button(frame, text="开", command=open_cmd, font=Theme.BUTTON_FONT, bg=Theme.BUTTON_SECONDARY_BG, fg=Theme.BUTTON_FG, relief=tk.FLAT, width=3)
        open_btn.pack(side=tk.LEFT)
        return frame