[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

# BA Modding Toolkit

[简体中文](README_zh-CN.md) | [English](README.md)

一个用于自动化制作、更新 Unity 游戏 Mod Bundle 文件的工具集。

## 启动程序

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行程序
```bash
python main.pyw
```
或者直接双击 `main.pyw` 文件启动

## 使用方法

0. 设定游戏资源目录（即存放 Bundle 文件的目录）与输出目录

### 一键更新 Mod
1. 拖放或浏览选择需要更新的旧版 Mod Bundle 文件
2. 程序会自动根据资源目录寻找对应目标 Bundle 文件
3. 勾选需要替换的资源类型
    - Texture2D（贴图纹理）
    - TextAsset（`.atlas`、`.skel`文件，Spine使用的骨骼文件）
    - Mesh（3D模型）
4. 点击"开始一键更新"按钮
5. （可选）成功后点击"覆盖原文件"应用修改。请确保开启了“创建备份”选项以防止风险。

此功能同样适用于移植不同平台的Mod。

### CRC 修正工具
1. 拖放或浏览选择需要修改的目标 Bundle 文件
2. 点击"运行 CRC 修正"按钮：自动修正 Bundle 文件的 CRC 校验值
3. （可选）成功后点击"替换原始文件"应用修改。请确保开启了“创建备份”选项以防止风险。

“计算CRC值” 按钮可用于手动查看文件的 CRC 校验值。

### PNG 文件夹替换
1. 拖放或浏览选择需要替换的 PNG 图片文件
2. 拖放或浏览选择需要修改的目标 Bundle 文件
3. 点击"开始替换"按钮：执行贴图替换操作
4. （可选）成功后点击"覆盖原文件"应用修改。请确保开启了“创建备份”选项以防止风险。

此功能适用于制作新的 Mod。

### 选项说明
- CRC 修正：自动修正 Bundle 文件的 CRC 校验值，防止文件被修改后无法运行。
    - 当前仅 Steam 版本 Mod 需要此步骤，其他版本 Mod 可忽略。
- ~~添加私货：在 CRC 修正前添加`0x08080808`，没用~~
- 创建备份：在覆盖原文件之前创建原文件的备份。

## 文件结构

```
BA-Modding-Toolkit/
├── main.pyw          # 程序主入口
├── ui.py             # 图形界面
├── processing.py     # 核心处理逻辑
├── utils.py          # 工具类和辅助函数
├── requirements.txt  # Python依赖列表
└── README_zh-CN.md   # 项目说明文档（简体中文）
```