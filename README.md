[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

# BA Modding Toolkit

> Sorry for my program being written in Chinese without i18n support, but I believe it's easy to use with this README.

[简体中文](README_zh-CN.md) | English

A toolkit for automating the creation and updating of Unity game Mod Bundle files.

## Getting Started

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run the Program
```bash
python main.pyw
```
Alternatively, you can double-click the `main.pyw` file to launch the program.

## How to Use

![How to update a mod with BAMT GUI](assets/help/gui-help-mod-update-en.png)

- Set the "游戏资源目录" (Game Asset Directory) (where the original Bundle files are located) and the "输出目录" (Output Directory).

- Set the "CRC 修正" (CRC Fix) option to enable CRC checksum correction.
    - If you are making a mod for the Steam version of the game, this step is required. Otherwise, you can ignore it.

- Set the "创建备份" (Create Backup) option to enable backup creation before overwriting the original files.

### 一键更新 Mod (One-Click Mod Update)
1. Drag and drop into "旧版 Mod Bundle 文件" (Old Mod Bundle File) area, or browse to select the old Mod Bundle file you want to update.
2. The program will automatically find the corresponding target Bundle file in the game asset directory.
3. Check the asset types you want to replace:
    - Texture2D (textures)
    - TextAsset (`.atlas`, `.skel` files, used for Spine animations)
    - Mesh (3D models)
4. Click the "开始一键更新" (Start One-Click Update) button.
5. (Optional) After a successful update, click "覆盖原文件" (Overwrite Original File) to apply the changes. Please ensure the "创建备份" (Create Backup) option is enabled to prevent data loss.

This feature can also be used to port mods between different platforms, as long as you select the Bundle file from the target platform in Step 2.

### CRC 修正工具 (CRC Fix Tool)
1. Drag and drop or browse to select the target Bundle file to be fixed.
2. Click the "运行 CRC 修正" (Run CRC Fix) button to automatically correct the Bundle file's CRC checksum.
3. (Optional) After a successful fix, click "替换原始文件" (Replace Original File) to apply the changes. Please ensure the "创建备份" (Create Backup) option is enabled.

The "计算CRC值" (Calculate CRC Value) button can be used to manually check a file's CRC checksum.

### PNG 文件夹替换 (PNG Replacement)
1. Drag and drop or browse to select the folder containing the new PNG image files.
    - Make sure the filenames of the new PNG files match the textures in the target Bundle file.
2. Drag and drop or browse to select the target Bundle file to be modified.
3. Click the "开始替换" (Start Replacement) button to perform the texture replacement.
4. (Optional) After a successful replacement, click "覆盖原文件" (Overwrite Original File) to apply the changes. Please ensure the "创建备份" (Create Backup) option is enabled.

This feature is intended for creating new mods.

### Options Description
- CRC 修正 (CRC Fix): Automatically corrects the Bundle file's CRC checksum, which prevents the game from rejecting the modified file.
    - This step is currently only required for mods on the Steam version of the game and can be ignored for other versions (like AndroidGB and AndroidJP).
- 添加私货: ~~Adds `0x08080808` before the CRC fix.~~ Ignore it.
- 创建备份 (Create Backup): Creates a backup of the original file before overwriting it.

## Developing

The author's programming skills are limited, any contributions or suggestions are welcome.

You can add `BA-Modding-Toolkit` code (mainly `processing.py` and `utils.py`) to your project or modify the existing code to implement custom Mod creation and update functionality.

`maincli.py` is a command-line interface (CLI) version of the main program, which you can refer to for calling processing functions.

### File Structure

```
BA-Modding-Toolkit/
├── main.pyw          # GUI program main entry point
├── ui.py             # GUI interface
├── maincli.py        # Command-line interface entry point
├── processing.py     # Core processing logic
├── utils.py          # Utility classes and helper functions
├── requirements.txt  # Python dependency list
├── assets/           # Project asset folder
└── README.md         # Project documentation (this file)
```

## Thanks
- Deathemonic: Patching CRC with [BA-CY](https://github.com/Deathemonic/BA-CY).
- [kalinaowo](https://github.com/kalinaowo): Prototype of the `CRCUtils` class, the starting point of BAMT.
- [fiseleo](https://github.com/fiseleo): Help with the CLI version.