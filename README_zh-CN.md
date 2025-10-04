[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

# BA Modding Toolkit

简体中文 | [English](README.md)

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

![How to update a mod with BAMT GUI](assets/help/gui-help-mod-update-en.png)


- 设定游戏资源目录（即存放 Bundle 文件的目录）与输出目录
- 开启 CRC 修正选项，自动修正 Bundle 文件的 CRC 校验值
    - 当前仅 Steam 版本 Mod 需要此步骤，其他版本 Mod 可忽略
- 开启创建备份选项，在覆盖原文件之前创建原文件的备份。

### 一键更新 Mod
1. 拖放或浏览选择需要更新的旧版 Mod Bundle 文件
2. 程序会自动根据资源目录寻找对应目标 Bundle 文件
3. 勾选需要替换的资源类型
    - Texture2D（贴图纹理）
    - TextAsset（`.atlas`、`.skel`文件，Spine使用的骨骼文件）
    - Mesh（3D模型）
4. 点击"开始一键更新"按钮
5. （可选）成功后点击"覆盖原文件"应用修改。请确保开启了“创建备份”选项以防止风险。

此功能同样适用于在不同平台间移植 Mod，只需在第二步中选择来自对应平台的 Bundle 文件即可。

### CRC 修正工具
1. 拖放或浏览选择需要修改的目标 Bundle 文件
2. 点击"运行 CRC 修正"按钮：自动修正 Bundle 文件的 CRC 校验值
3. （可选）成功后点击"替换原始文件"应用修改。请确保开启了“创建备份”选项以防止风险。

“计算CRC值” 按钮可用于手动查看文件的 CRC 校验值。

### PNG 文件夹替换
1. 拖放或浏览选择包含需要替换的 PNG 图片文件所在的文件夹。
    - 确保新 PNG 文件的文件名与目标 Bundle 文件中的贴图文件名匹配。
2. 拖放或浏览选择需要修改的目标 Bundle 文件
3. 点击"开始替换"按钮：执行贴图替换操作
4. （可选）成功后点击"覆盖原文件"应用修改。请确保开启了“创建备份”选项以防止风险。

此功能适用于制作新的 Mod。

### 选项说明
- CRC 修正：自动修正 Bundle 文件的 CRC 校验值，防止文件被修改后无法运行。
    - 当前仅 Steam 版本 Mod 需要此步骤，其他版本 Mod 可忽略。
- ~~添加私货：在 CRC 修正前添加`0x08080808`，没用~~
- 创建备份：在覆盖原文件之前创建原文件的备份。

## 开发

作者的编程水平有限，欢迎贡献代码或提出建议。

您可以将 `BA-Modding-Toolkit` 的代码（主要是 `processing.py` 与 `utils.py`）加入您的项目中或是进行修改，以实现自定义的 Mod 制作和更新功能。

`maincli.py` 是一个命令行接口（CLI）版本的主程序，您可以参考其调用处理函数的方式。

### 文件结构

```
BA-Modding-Toolkit/
├── main.pyw          # GUI程序主入口
├── ui.py             # 图形界面
├── maincli.py        # 命令行接口主入口
├── processing.py     # 核心处理逻辑
├── utils.py          # 工具类和辅助函数
├── requirements.txt  # Python依赖列表
├── assets/           # 项目资源文件夹
└── README_zh-CN.md   # 项目说明文档（简体中文）
```

## 鸣谢

- Deathemonic: Patching CRC with [BA-CY](https://github.com/Deathemonic/BA-CY).
- [kalinaowo](https://github.com/kalinaowo): The prototype of the `CRCUtils` class, the starting point of BAMT.
- [fiseleo](https://github.com/fiseleo): Help with the CLI version.