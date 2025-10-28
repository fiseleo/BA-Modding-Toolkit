# ui/tabs/jp_gb_conversion_tab.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinterdnd2 import DND_FILES
from pathlib import Path

import processing
from ui.base_tab import TabFrame
from ui.components import Theme, UIComponents
from ui.utils import is_multiple_drop

class JpGbConversionTab(TabFrame):
    """日服与国际服格式互相转换的标签页"""
    def create_widgets(self, output_dir_var, enable_padding_var, enable_crc_correction_var, 
                      create_backup_var, compression_method_var):
        # --- 共享变量 ---
        self.output_dir_var: tk.StringVar = output_dir_var
        self.enable_padding: tk.BooleanVar = enable_padding_var
        self.enable_crc_correction: tk.BooleanVar = enable_crc_correction_var
        self.create_backup: tk.BooleanVar = create_backup_var
        self.compression_method: tk.StringVar = compression_method_var
        
        # 文件路径变量
        self.global_bundle_path: Path | None = None
        self.jp_textasset_bundle_path: Path | None = None
        self.jp_texture2d_bundle_path: Path | None = None
        
        # --- 转换模式选择 ---
        mode_frame = tk.Frame(self, bg=Theme.WINDOW_BG)
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.mode_var = tk.StringVar(value="jp_to_global")
        
        style = ttk.Style()
        style.configure("Toolbutton", 
                        background=Theme.MUTED_BG, 
                        foreground=Theme.TEXT_NORMAL,
                        font=Theme.BUTTON_FONT,
                        padding=(10, 5),
                        borderwidth=1,
                        relief=tk.FLAT)
        style.map("Toolbutton",
                  background=[('selected', Theme.FRAME_BG), ('active', '#e0e0e0')],
                  relief=[('selected', tk.GROOVE)])

        ttk.Radiobutton(mode_frame, text="JP -> Global", variable=self.mode_var, 
                       value="jp_to_global", command=self._switch_view, style="Toolbutton").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Radiobutton(mode_frame, text="Global -> JP", variable=self.mode_var, 
                       value="global_to_jp", command=self._switch_view, style="Toolbutton").pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- 文件输入区域 ---
        self.file_frame = tk.Frame(self, bg=Theme.WINDOW_BG)
        self.file_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 创建文件输入区域
        self._create_file_input_areas()
        
        # --- 操作按钮 ---
        action_button_frame = tk.Frame(self)
        action_button_frame.pack(fill=tk.X, pady=2)
        
        self.run_button = UIComponents.create_button(
            action_button_frame, "开始转换", 
            self.run_conversion_thread, 
            bg_color=Theme.BUTTON_SUCCESS_BG, 
            padx=15, pady=8
        )
        self.run_button.pack(fill=tk.X)
        
        # 初始化视图
        self._switch_view()
    
    def _create_file_input_areas(self):
        """创建文件输入区域"""
        # 区域1: 国际服 Bundle 文件
        self.global_frame, self.global_label = UIComponents.create_file_drop_zone(
            self.file_frame, "Global Bundle 文件", 
            self.drop_global_bundle, self.browse_global_bundle
        )
        
        # 创建一个框架来包含两个日服文件框，使它们水平排列
        jp_files_frame = tk.Frame(self.file_frame, bg=Theme.WINDOW_BG)
        jp_files_frame.pack(fill=tk.X, pady=0)
        
        # 区域2: 日服 TextAsset Bundle 文件
        self.jp_textasset_frame, self.jp_textasset_label = UIComponents.create_file_drop_zone(
            jp_files_frame, "JP TextAsset Bundle", 
            self.drop_jp_textasset_bundle, self.browse_jp_textasset_bundle
        )
        self.jp_textasset_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 区域3: 日服 Texture2D Bundle 文件
        self.jp_texture2d_frame, self.jp_texture2d_label = UIComponents.create_file_drop_zone(
            jp_files_frame, "JP Texture2D Bundle", 
            self.drop_jp_texture2d_bundle, self.browse_jp_texture2d_bundle
        )
        self.jp_texture2d_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
    
    def _switch_view(self):
        """根据选择的模式更新UI"""
        if self.mode_var.get() == "jp_to_global":
            # 日服 -> 国际服模式
            self.global_frame.config(text="Global Bundle（基础）")
            self.jp_textasset_frame.config(text="JP TextAsset Bundle（源）")
            self.jp_texture2d_frame.config(text="JP Texture2D Bundle（源）")
        else:
            # 国际服 -> 日服模式
            self.global_frame.config(text="Global Bundle（源）")
            self.jp_textasset_frame.config(text="JP TextAsset Bundle（模板）")
            self.jp_texture2d_frame.config(text="JP Texture2D Bundle（模板）")
    
    # --- 文件拖放和浏览方法 ---
    def drop_global_bundle(self, event):
        if is_multiple_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
        path = Path(event.data.strip('{}'))
        self.set_file_path('global_bundle_path', self.global_label, path, "国际服 Bundle 文件")
    
    def browse_global_bundle(self):
        p = filedialog.askopenfilename(title="选择国际服 Bundle 文件")
        if p:
            self.set_file_path('global_bundle_path', self.global_label, Path(p), "国际服 Bundle 文件")
    
    def drop_jp_textasset_bundle(self, event):
        if is_multiple_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
        path = Path(event.data.strip('{}'))
        self.set_file_path('jp_textasset_bundle_path', self.jp_textasset_label, path, "日服 TextAsset Bundle 文件")
    
    def browse_jp_textasset_bundle(self):
        p = filedialog.askopenfilename(title="选择日服 TextAsset Bundle 文件")
        if p:
            self.set_file_path('jp_textasset_bundle_path', self.jp_textasset_label, Path(p), "日服 TextAsset Bundle 文件")
    
    def drop_jp_texture2d_bundle(self, event):
        if is_multiple_drop(event.data):
            messagebox.showwarning("操作无效", "请一次只拖放一个文件。")
            return
        path = Path(event.data.strip('{}'))
        self.set_file_path('jp_texture2d_bundle_path', self.jp_texture2d_label, path, "日服 Texture2D Bundle 文件")
    
    def browse_jp_texture2d_bundle(self):
        p = filedialog.askopenfilename(title="选择日服 Texture2D Bundle 文件")
        if p:
            self.set_file_path('jp_texture2d_bundle_path', self.jp_texture2d_label, Path(p), "日服 Texture2D Bundle 文件")
    
    # --- 转换逻辑 ---
    def run_conversion_thread(self):
        """在线程中运行转换过程"""
        self.run_in_thread(self.run_conversion)
    
    def run_conversion(self):
        """执行转换过程"""
        # 验证输出目录
        output_dir = Path(self.output_dir_var.get())
        try:
            output_dir.mkdir(parents=True, exist_ok=True) 
        except Exception as e:
            messagebox.showerror("错误", f"无法创建输出目录:\n{output_dir}\n\n错误详情: {e}")
            return
        
        # 创建保存选项
        save_options = processing.SaveOptions(
            perform_crc=self.enable_crc_correction.get(),
            enable_padding=self.enable_padding.get(),
            compression=self.compression_method.get()
        )
        
        # 根据选择的模式执行不同的转换
        if self.mode_var.get() == "jp_to_global":
            self._run_jp_to_global_conversion(output_dir, save_options)
        else:
            self._run_global_to_jp_conversion(output_dir, save_options)
    
    def _run_jp_to_global_conversion(self, output_dir, save_options):
        """执行日服到国际服的转换"""
        # 验证必需的文件
        if not all([self.global_bundle_path, self.jp_textasset_bundle_path, self.jp_texture2d_bundle_path]):
            messagebox.showerror("错误", "请确保已选择所有必需的文件：\n- 国际服 Bundle 文件\n- 日服 TextAsset Bundle 文件\n- 日服 Texture2D Bundle 文件")
            return
        
        self.logger.log("\n" + "="*50)
        self.logger.log("开始JP -> Global转换...")
        self.logger.status("正在处理中，请稍候...")
        
        # 执行转换
        success, message = processing.process_jp_to_global_conversion(
            global_bundle_path=self.global_bundle_path,
            jp_textasset_bundle_path=self.jp_textasset_bundle_path,
            jp_texture2d_bundle_path=self.jp_texture2d_bundle_path,
            output_dir=output_dir,
            save_options=save_options,
            log=self.logger.log
        )
        
        # 显示结果
        if success:
            self.logger.status("转换完成")
            messagebox.showinfo("成功", message)
        else:
            self.logger.status("转换失败")
            messagebox.showerror("失败", message)
    
    def _run_global_to_jp_conversion(self, output_dir, save_options):
        """执行国际服到日服的转换"""
        # 验证必需的文件
        if not self.global_bundle_path:
            messagebox.showerror("错误", "请确保已选择国际服 Bundle 文件")
            return
        
        # 在国际服转日服模式下，需要日服模板文件
        if not self.jp_textasset_bundle_path or not self.jp_texture2d_bundle_path:
            messagebox.showerror("错误", "请确保已选择所有必需的模板文件：\n- 日服 TextAsset Bundle 文件（模板）\n- 日服 Texture2D Bundle 文件（模板）")
            return
        
        self.logger.log("\n" + "="*50)
        self.logger.log("开始Global -> JP转换...")
        self.logger.status("正在处理中，请稍候...")
        
        # 执行转换
        success, message = processing.process_global_to_jp_conversion(
            global_bundle_path=self.global_bundle_path,
            jp_textasset_bundle_path=self.jp_textasset_bundle_path,
            jp_texture2d_bundle_path=self.jp_texture2d_bundle_path,
            output_dir=output_dir,
            save_options=save_options,
            log=self.logger.log
        )
        
        # 更新UI显示输出文件路径
        if success:
            self.logger.status("转换完成")
            messagebox.showinfo("成功", message)
        else:
            self.logger.status("转换失败")
            messagebox.showerror("失败", message)