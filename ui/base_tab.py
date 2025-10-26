# ui/base_tab.py

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import threading

from .components import Theme

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
        label_widget.config(text=f"{path.name}", fg=Theme.COLOR_SUCCESS)
        self.logger.log(f"已加载 {file_type_name}: {path.name}")
        self.logger.status(f"已加载 {file_type_name}")
        if auto_output_func:
            auto_output_func()

    def set_folder_path(self, path_var_name, label_widget, path: Path, folder_type_name):
        setattr(self, path_var_name, path)
        label_widget.config(text=f"{path.name}", fg=Theme.COLOR_SUCCESS)
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