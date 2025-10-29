# ui/tabs/asset_extractor_tab.py

import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path
import os

import processing
from ui.base_tab import TabFrame
from ui.components import Theme, UIComponents
from ui.utils import is_multiple_drop

class AssetExtractorTab(TabFrame):
    def create_widgets(self, output_dir_var, replace_texture2d_var, replace_textasset_var, replace_mesh_var, replace_all_var):
        self.bundle_path: Path | None = None
        
        # 接收共享的变量
        self.output_dir_var: tk.StringVar = output_dir_var
        self.replace_texture2d_var: tk.BooleanVar = replace_texture2d_var
        self.replace_textasset_var: tk.BooleanVar = replace_textasset_var
        self.replace_mesh_var: tk.BooleanVar = replace_mesh_var
        self.replace_all_var: tk.BooleanVar = replace_all_var
        
        # 子目录变量
        self.subdir_var: tk.StringVar = tk.StringVar()
        
        # 1. 目标 Bundle 文件
        _, self.bundle_label = UIComponents.create_file_drop_zone(
            self, "目标 Bundle 文件", self.drop_bundle, self.browse_bundle
        )
        
        # 2. 输出目录
        self.output_frame = UIComponents.create_directory_path_entry(
            self, "输出目录", self.subdir_var,
            self.select_output_dir, self.open_output_dir,
            placeholder_text="选择输出子目录"
        )

        # 3. 资源类型选项提示
        options_frame = tk.LabelFrame(self, text="提取选项", font=Theme.FRAME_FONT, fg=Theme.TEXT_TITLE, bg=Theme.FRAME_BG, padx=10, pady=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        info_label = tk.Label(options_frame, text="施工中...", font=Theme.INPUT_FONT, bg=Theme.FRAME_BG, fg=Theme.TEXT_NORMAL)
        info_label.pack(anchor="w", pady=5)

        # 4. 操作按钮
        action_frame = tk.Frame(self)
        action_frame.pack(fill=tk.X, pady=10)
        action_frame.grid_columnconfigure(0, weight=1)

        run_button = UIComponents.create_button(action_frame, "开始提取", self.run_extraction_thread, 
                                                 bg_color=Theme.BUTTON_SUCCESS_BG, padx=15, pady=8)
        run_button.grid(row=0, column=0, sticky="ew", padx=(0, 0), pady=10)

    def drop_bundle(self, event):
        if is_multiple_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
        self.set_file_path('bundle_path', self.bundle_label, Path(event.data.strip('{}')), "目标 Bundle")

    def browse_bundle(self):
        p = filedialog.askopenfilename(title="选择目标 Bundle 文件")
        if p: self.set_file_path('bundle_path', self.bundle_label, Path(p), "目标 Bundle")
    
    def select_output_dir(self):
        """选择输出子目录"""
        # 默认路径为输出目录
        default_dir = Path(self.output_dir_var.get())
        if not default_dir.exists():
            default_dir = Path.home()
            
        selected_dir = filedialog.askdirectory(
            title="选择输出子目录",
            initialdir=str(default_dir)
        )
        
        if selected_dir:
            # 计算相对于输出目录的路径
            output_dir = Path(self.output_dir_var.get())
            selected_path = Path(selected_dir)
            
            try:
                # 尝试获取相对路径
                rel_path = selected_path.relative_to(output_dir)
                self.subdir_var.set(str(rel_path))
            except ValueError:
                # 如果不是子目录，则使用绝对路径
                self.subdir_var.set(selected_dir)
    
    def open_output_dir(self):
        """打开输出子目录"""
        # 获取子目录名
        subdir_name = self.subdir_var.get().strip()
        if not subdir_name and self.bundle_path:
            subdir_name = self.bundle_path.stem
        
        if subdir_name:
            # 如果是相对路径，则与输出目录组合
            if not Path(subdir_name).is_absolute():
                output_path = Path(self.output_dir_var.get()) / subdir_name
            else:
                output_path = Path(subdir_name)
        else:
            output_path = Path(self.output_dir_var.get())
            
        if output_path.exists():
            os.startfile(output_path)
        else:
            # 如果目录不存在，询问用户是否要创建
            result = messagebox.askyesno(
                "目录不存在", 
                f"输出目录 '{output_path}' 不存在。\n是否要创建此目录？"
            )
            if result:
                try:
                    output_path.mkdir(parents=True, exist_ok=True)
                    os.startfile(output_path)
                except Exception as e:
                    messagebox.showerror("错误", f"创建目录失败: {e}")
            else:
                messagebox.showinfo("提示", "未创建目录。")

    def run_extraction_thread(self):
        if not self.bundle_path:
            messagebox.showerror("错误", "请选择一个目标 Bundle 文件。")
            return
            
        output_path = Path(self.output_dir_var.get())
        
        # 获取子目录名
        subdir_name = self.subdir_var.get().strip()
        if not subdir_name:
            subdir_name = self.bundle_path.stem
        
        # 如果是相对路径，则与输出目录组合
        if subdir_name and not Path(subdir_name).is_absolute():
            final_output_path = output_path / subdir_name
        elif subdir_name:
            final_output_path = Path(subdir_name)
        else:
            final_output_path = output_path
            
        asset_types = set()
        if self.replace_all_var.get():
            asset_types.add("ALL")
        else:
            if self.replace_texture2d_var.get(): asset_types.add("Texture2D")
            if self.replace_textasset_var.get(): asset_types.add("TextAsset")
            if self.replace_mesh_var.get(): asset_types.add("Mesh")
        
        if not asset_types:
            messagebox.showwarning("提示", "请至少选择一种要提取的资源类型。\n您可以在设置对话框中配置这些选项。")
            return
            
        self.run_in_thread(self.run_extraction, self.bundle_path, final_output_path, asset_types)

    def run_extraction(self, bundle_path, output_dir, asset_types):
        self.logger.status("正在提取资源...")
        
        success, message = processing.process_asset_extraction(
            bundle_path=bundle_path,
            output_dir=output_dir,
            asset_types_to_extract=asset_types,
            log=self.logger.log
        )
        
        if success:
            messagebox.showinfo("成功", message)
        else:
            messagebox.showerror("失败", message)
            
        self.logger.status("提取完成")