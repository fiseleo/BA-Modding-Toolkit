# main.py

from tkinterdnd2 import TkinterDnD
from ui import App

if __name__ == "__main__":
    # 使用 TkinterDnD.Tk() 作为主窗口以支持拖放
    root = TkinterDnD.Tk()
    
    # 创建并运行应用
    app = App(root)
    print("BA Modding Toolkit 已启动")
    
    # 启动 Tkinter 事件循环
    root.mainloop()