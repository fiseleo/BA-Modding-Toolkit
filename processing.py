# processing.py

import UnityPy
import os
import traceback
from pathlib import Path
from PIL import Image
import shutil
import re
import tempfile
import subprocess
from dataclasses import dataclass
from typing import Callable, Any, Literal

from utils import CRCUtils, no_log, get_skel_version

# -------- 类型别名 ---------

# AssetKey 表示资源的唯一标识符，在不同的流程中可以使用不同的键
# str 类型 表示资源名称，在资源打包工具中使用
# int 类型 表示 path_id
# tuple[str, str] 类型 表示 (名称, 类型) 元组
AssetKey = str | int | tuple[str, str]

# 资源的具体内容，可以是字节数据、PIL图像或None
AssetContent = bytes | Image.Image | None  

# 从对象生成资源键的函数，接收UnityPy对象和一个额外参数，返回该资源的键
KeyGeneratorFunc = Callable[[UnityPy.classes.Object, Any], AssetKey]

# 日志函数类型
LogFunc = Callable[[str], None]  

# 压缩类型
CompressionType = Literal["lzma", "lz4", "original", "none"]  

@dataclass
class SaveOptions:
    """封装了保存、压缩和CRC修正相关的选项。"""
    perform_crc: bool = True
    enable_padding: bool = False
    compression: CompressionType = "lzma"

@dataclass
class SpineOptions:
    """封装了Spine版本更新相关的选项。"""
    enabled: bool = False
    converter_path: Path | None = None
    target_version: str | None = None

    def is_enabled(self) -> bool:
        """检查Spine升级功能是否已配置并可用。"""
        return (
            self.enabled
            and self.converter_path
            and self.converter_path.exists()
            and self.target_version
            and self.target_version.count(".") == 2
        )

def load_bundle(
    bundle_path: Path,
    log: LogFunc = no_log
) -> UnityPy.Environment | None:
    """
    尝试加载一个 Unity bundle 文件。
    如果直接加载失败，会尝试移除末尾的几个字节后再次加载。
    """

    # 1. 尝试直接加载
    try:
        env = UnityPy.load(str(bundle_path))
        return env
    except Exception as e:
        pass

    # 如果直接加载失败，读取文件内容到内存
    try:
        with open(bundle_path, "rb") as f:
            data = f.read()
    except Exception as e:
        log(f"  ❌ 无法在内存中读取文件 '{bundle_path.name}': {e}")
        return None

    # 定义加载策略：字节移除数量
    bytes_to_remove = [4, 8, 12]

    # 2. 依次尝试不同的加载策略
    for bytes_num in bytes_to_remove:
        if len(data) > bytes_num:
            try:
                trimmed_data = data[:-bytes_num]
                env = UnityPy.load(trimmed_data)
                return env
            except Exception as e:
                pass

    log(f"❌ 无法以任何方式加载 '{bundle_path}'。文件可能已损坏。")
    return None

def create_backup(
    original_path: Path,
    backup_mode: str = "default",
    log: LogFunc = no_log,
) -> bool:
    """
    创建原始文件的备份
    backup_mode: "default" - 在原文件后缀后添加.bak
                 "b2b" - 重命名为orig_(原名)
    """
    try:
        if backup_mode == "b2b":
            backup_path = original_path.with_name(f"orig_{original_path.name}")
        else:
            backup_path = original_path.with_suffix(original_path.suffix + '.bak')

        shutil.copy2(original_path, backup_path)
        return True
    except Exception as e:
        log(f"❌ 创建备份文件失败: {e}")
        return False

def save_bundle(
    env: UnityPy.Environment,
    output_path: Path,
    compression: CompressionType = "lzma",
    log: LogFunc = no_log,
) -> bool:
    """
    将修改后的 Unity bundle 保存到指定路径。
    """
    try:
        bundle_data = compress_bundle(env, compression, log)
        with open(output_path, "wb") as f:
            f.write(bundle_data)
        return True
    except Exception as e:
        log(f"❌ 保存 bundle 文件到 '{output_path}' 时失败: {e}")
        log(traceback.format_exc())
        return False

def compress_bundle(
    env: UnityPy.Environment,
    compression: CompressionType = "none",
    log: LogFunc = no_log,
) -> bytes:
    """
    从 UnityPy.Environment 对象生成 bundle 文件的字节数据。
    compression: 用于控制压缩方式。
                 - "lzma": 使用 LZMA 压缩。
                 - "lz4": 使用 LZ4 压缩。
                 - "original": 保留原始压缩方式。
                 - "none": 不进行压缩。
    """
    save_kwargs = {}
    if compression == "original":
        log("   > 压缩方式: 保持原始设置")
        # Not passing the 'packer' argument preserves the original compression.
    elif compression == "none":
        log("    > 压缩方式: 不压缩")
        save_kwargs['packer'] = ""  # An empty string typically means no compression.
    else:
        log(f"    > 压缩方式: {compression.upper()}")
        save_kwargs['packer'] = compression
    
    return env.file.save(**save_kwargs)

def _save_and_crc(
    env: UnityPy.Environment,
    output_path: Path,
    original_bundle_path: Path,
    save_options: SaveOptions,
    log: LogFunc = no_log,
) -> tuple[bool, str]:
    """
    一个辅助函数，用于生成压缩bundle数据，根据需要执行CRC修正，并最终保存到文件。
    封装了保存、CRC修正的逻辑。

    Returns:
        tuple(bool, str): (是否成功, 状态消息) 的元组。
    """
    try:
        # 1. 从 env 生成修改后的压缩 bundle 数据
        log(f"\n--- 导出修改后的 Bundle 文件 ---")
        log("  > 压缩 Bundle 数据")
        modified_data = compress_bundle(env, save_options.compression, log)

        final_data = modified_data
        success_message = "文件保存成功。"

        if save_options.perform_crc:
            log(f"  > 准备修正CRC...")
            
            with open(original_bundle_path, "rb") as f:
                original_data = f.read()

            corrected_data = CRCUtils.apply_crc_fix(
                original_data, 
                modified_data, 
                save_options.enable_padding
            )

            if not corrected_data:
                return False, f"CRC 修正失败。最终文件 '{output_path.name}' 未能生成。"
            
            final_data = corrected_data
            success_message = "文件保存和CRC修正成功。"
            log("✅ CRC 修正成功！")

        # 2. 将最终数据写入文件
        log(f"  > 正在写入文件: {output_path}")
        with open(output_path, "wb") as f:
            f.write(final_data)
        
        return True, success_message

    except Exception as e:
        log(f"❌ 保存或修正 bundle 文件到 '{output_path}' 时失败: {e}")
        log(traceback.format_exc())
        return False, f"保存或修正文件时发生错误: {e}"

def upgrade_skel(
    raw_skel_data: bytes,
    spine_options: SpineOptions,
    log: LogFunc = no_log,
) -> tuple[bool, bytes]:
    """
    使用外部工具升级 .skel 文件。
    返回 (是否成功, skel数据) 的元组。
    """
    # 检查Spine升级功能是否可用
    if not spine_options.is_enabled():
        log(f"  > ⚠️ Spine升级功能未启用或配置无效")
        return False, raw_skel_data

    temp_in_path, temp_out_path = None, None
    try:
        # 使用临时文件来进行转换
        with tempfile.NamedTemporaryFile(delete=False, suffix=".skel") as temp_in_file:
            temp_in_file.write(raw_skel_data)
            temp_in_path = Path(temp_in_file.name)
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".skel") as temp_out_file:
            temp_out_path = Path(temp_out_file.name)

        # 构建并执行命令
        command = [
            str(spine_options.converter_path),
            str(temp_in_path),
            str(temp_out_path),
            "-v",
            spine_options.target_version
        ]
        log(f"    > 执行命令: {' '.join(map(str, command))}")
        # 命令格式：SpineConverter.exe input.skel output.skel -v 4.2.33
        
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            check=True, 
            encoding='utf-8', 
            errors='ignore'
        )
        
        if result.stdout:
            log(f"    > Spine 转换器输出:\n{result.stdout}")
        if result.stderr:
            log(f"    > Spine 转换器错误输出:\n{result.stderr}")

        # 读取转换后的内容
        with open(temp_out_path, "rb") as f_out:
            upgraded_data = f_out.read()
        return True, upgraded_data

    except FileNotFoundError:
        log(f"    ❌ Spine 转换器未找到: {spine_options.converter_path}")
        return False, raw_skel_data
    except subprocess.CalledProcessError as e:
        log(f"    ❌ Spine 转换器执行失败 (返回码: {e.returncode})")
        if e.stdout: log(f"      > 输出: {e.stdout}")
        if e.stderr: log(f"      > 错误: {e.stderr}")
        return False, raw_skel_data
    except Exception as e:
        log(f"    ❌ 升级 .skel 文件时发生未知错误: {e}")
        return False, raw_skel_data
    finally:
        # 清理临时文件
        for p in [temp_in_path, temp_out_path]:
            if p and p.exists():
                try:
                    p.unlink()
                except OSError:
                    log(f"    ❌ 无法删除临时文件: {p}")

def _handle_skel_upgrade(
    skel_bytes: bytes,
    resource_name: str,
    spine_options: SpineOptions | None = None,
    log: LogFunc = no_log,
) -> bytes:
    """
    处理 .skel 文件的版本检查和升级。
    如果无需升级或升级失败，则返回原始字节。
    """
    # 检查Spine升级功能是否可用
    if spine_options is None or not spine_options.is_enabled():
        return skel_bytes
    
    log(f"    > 检测到 .skel 文件: {resource_name}")
    try:
        # 检测 skel 的 spine 版本
        current_version = get_skel_version(skel_bytes, log)
        target_major_minor = ".".join(spine_options.target_version.split('.')[:2])
        
        # 仅在主版本或次版本不匹配时才尝试升级
        if current_version and not current_version.startswith(target_major_minor):
            log(f"      > spine 版本不匹配 (当前: {current_version}, 目标: {spine_options.target_version})。尝试升级...")

            skel_success, upgraded_content = upgrade_skel(
                raw_skel_data=skel_bytes,
                spine_options=spine_options,
                log=log
            )
            if skel_success:
                log(f"    > 成功升级 .skel 文件: {resource_name}")
                return upgraded_content
            else:
                log(f"    ❌ 升级 .skel 文件 '{resource_name}' 失败，将使用原始文件")
        else:
            log(f"      > 版本匹配或无法检测 ({current_version})，无需升级。")

    except Exception as e:
        log(f"      ❌ 错误: 检测或升级 .skel 文件 '{resource_name}' 时发生错误: {e}")

    # 默认返回原始字节
    return skel_bytes

def _apply_replacements(
    env: UnityPy.Environment,
    replacement_map: dict[AssetKey, AssetContent],
    key_func: KeyGeneratorFunc,
    log: LogFunc = no_log,
) -> tuple[int, list[str]]:
    """
    将“替换清单”中的资源应用到目标环境中。

    Args:
        env: 目标 UnityPy 环境。
        replacement_map: 资源替换清单，格式为 { asset_key: content }。
        key_func: 用于从目标环境中的对象生成 asset_key 的函数。
        log: 日志记录函数。

    Returns:
        一个元组 (成功替换的数量, 成功替换的资源日志列表)。
    """
    replacement_count = 0
    replaced_assets_log = []
    
    # 创建一个副本用于操作，因为我们会从中移除已处理的项
    tasks = replacement_map.copy()

    for obj in env.objects:
        if not tasks:  # 如果清单空了，就提前退出
            break
        
        data = obj.read()
        asset_key = key_func(obj, data)

        if asset_key in tasks:
            content = tasks.pop(asset_key)
            resource_name = getattr(data, 'm_Name', f"<{obj.type.name} 资源>")
            
            try:
                if obj.type.name == "Texture2D":
                    data.image = content
                    data.save()
                elif obj.type.name == "TextAsset":
                    # content 是 bytes，需要解码成 str
                    data.m_Script = content.decode("utf-8", "surrogateescape")
                    data.save()
                elif obj.type.name == "Mesh":
                    obj.set_raw_data(content)
                else: # 适用于 "ALL" 模式下的其他类型
                    obj.set_raw_data(content)

                replacement_count += 1
                log_message = f"  - {resource_name} ({obj.type.name})"
                replaced_assets_log.append(log_message)

            except Exception as e:
                log(f"  ❌ 错误: 替换资源 '{resource_name}' ({obj.type.name} 类型) 时发生错误: {e}")

    return replacement_count, replaced_assets_log

def process_asset_packing(
    target_bundle_path: Path,
    asset_folder: Path,
    output_dir: Path,
    save_options: SaveOptions,
    spine_options: SpineOptions | None = None,
    log: LogFunc = no_log,
) -> tuple[bool, str]:
    """
    从指定文件夹中，将同名的资源打包到指定的 Bundle 中。
    支持 .png, .skel, .atlas 文件。
    - .png 文件将替换同名的 Texture2D 资源 (文件名不含后缀)。
    - .skel 和 .atlas 文件将替换同名的 TextAsset 资源 (文件名含后缀)。
    可选地升级 Spine 动画的 Skel 资源版本。
    此函数将生成的文件保存在工作目录中，以便后续进行"覆盖原文件"操作。
    因为打包资源的操作在原理上是替换目标Bundle内的资源，因此里面可能有混用打包和替换的叫法。
    返回 (是否成功, 状态消息) 的元组。
    
    Args:
        target_bundle_path: 目标Bundle文件的路径
        asset_folder: 包含待打包资源的文件夹路径
        output_dir: 输出目录，用于保存生成的更新后文件
        save_options: 保存和CRC修正的选项
        spine_options: Spine资源升级的选项
        log: 日志记录函数，默认为空函数
    """
    try:
        env = load_bundle(target_bundle_path, log)
        if not env:
            return False, "无法加载目标 Bundle 文件，即使在尝试移除潜在的 CRC 补丁后也是如此。请检查文件是否损坏。"
        
        # 1. 从文件夹构建"替换清单"
        replacement_map: dict[AssetKey, AssetContent] = {}
        supported_extensions = [".png", ".skel", ".atlas"]
        input_files = [f for f in asset_folder.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions]

        if not input_files:
            msg = f"在指定文件夹中没有找到任何支持的文件 ({', '.join(supported_extensions)})。"
            log(f"⚠️ 警告: {msg}")
            return False, msg

        for file_path in input_files:
            asset_key: AssetKey
            content: AssetContent
            if file_path.suffix.lower() == ".png":
                asset_key = file_path.stem
                content = Image.open(file_path).convert("RGBA")
            else: # .skel, .atlas
                asset_key = file_path.name
                with open(file_path, "rb") as f:
                    content = f.read()
                
                if file_path.suffix.lower() == '.skel':
                    content = _handle_skel_upgrade(
                        skel_bytes=content,
                        resource_name=asset_key,
                        spine_options=spine_options,
                        log=log
                    )
            replacement_map[asset_key] = content
        
        original_tasks_count = len(replacement_map)
        log(f"找到 {original_tasks_count} 个待处理文件，正在扫描 bundle 并进行替换...")

        # 2. 定义用于在 bundle 中查找资源的 key 生成函数
        def key_func(obj: UnityPy.classes.Object, data: Any) -> AssetKey | None:
            if obj.type.name in ["Texture2D", "TextAsset"]:
                return data.m_Name
            return None

        # 3. 应用替换
        replacement_count, _ = _apply_replacements(env, replacement_map, key_func, log)

        if replacement_count == 0:
            log("⚠️ 警告: 没有执行任何成功的资源打包。")
            log("请检查：\n1. 文件名是否与 bundle 内的资源名完全匹配。\n2. bundle 文件是否正确。")
            return False, "没有找到任何名称匹配的资源进行打包。"
        
        log(f"\n打包完成: 成功打包 {replacement_count} / {original_tasks_count} 个资源。")

        # 报告未被打包的文件
        unmatched_keys = set(replacement_map.keys()) - {key for key, _ in replacement_map.items() if key not in [obj.read().m_Name for obj in env.objects]}
        if unmatched_keys:
            log("⚠️ 警告: 以下文件未在bundle中找到对应的资源:")
            # 为了找到原始文件名，我们需要反向查找
            original_filenames = {f.stem if f.suffix.lower() == '.png' else f.name: f.name for f in input_files}
            for key in unmatched_keys:
                log(f"  - {original_filenames.get(key, key)} (尝试匹配: '{key}')")

        # 4. 保存和修正
        output_path = output_dir / target_bundle_path.name
        save_ok, save_message = _save_and_crc(
            env=env,
            output_path=output_path,
            original_bundle_path=target_bundle_path,
            save_options=save_options,
            log=log
        )

        if not save_ok:
            return False, save_message

        log(f"最终文件已保存至: {output_path}")
        log(f"\n🎉 处理完成！")
        return True, f"处理完成！\n成功打包 {replacement_count} 个资源。\n\n文件已保存至工作目录，现在可以点击“覆盖原文件”按钮应用更改。"

    except Exception as e:
        log(f"\n❌ 严重错误: 处理 bundle 文件时发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"

def process_asset_extraction(
    bundle_path: Path,
    output_dir: Path,
    asset_types_to_extract: set[str],
    log: LogFunc = no_log,
) -> tuple[bool, str]:
    """
    从指定的 Bundle 文件中提取选定类型的资源到输出目录。
    支持 Texture2D (保存为 .png) 和 TextAsset (按原名保存)。

    Args:
        bundle_path: 目标 Bundle 文件的路径。
        output_dir: 提取资源的保存目录。
        asset_types_to_extract: 需要提取的资源类型集合 (如 {"Texture2D", "TextAsset"})。
        log: 日志记录函数。

    Returns:
        一个元组 (是否成功, 状态消息)。
    """
    try:
        log("\n" + "="*50)
        log(f"开始从 '{bundle_path.name}' 提取资源...")
        log(f"提取类型: {', '.join(asset_types_to_extract)}")
        log(f"输出目录: {output_dir}")

        env = load_bundle(bundle_path, log)
        if not env:
            return False, "无法加载 Bundle 文件。请检查文件是否损坏。"

        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)

        extraction_count = 0
        extracted_files = []

        for obj in env.objects:
            if obj.type.name in asset_types_to_extract:
                data = obj.read()
                resource_name = getattr(data, 'm_Name', None)
                if not resource_name:
                    log(f"  > 跳过一个未命名的 {obj.type.name} 资源")
                    continue

                try:
                    if obj.type.name == "Texture2D":
                        output_path = output_dir / f"{resource_name}.png"
                        log(f"  - 正在提取 Texture2D: {resource_name}.png")
                        image = data.image.convert("RGBA")
                        image.save(output_path)
                        extracted_files.append(output_path.name)
                        extraction_count += 1

                    elif obj.type.name == "TextAsset":
                        output_path = output_dir / resource_name
                        log(f"  - 正在提取 TextAsset: {resource_name}")
                        asset_bytes = data.m_Script.encode("utf-8", "surrogateescape")
                        with open(output_path, "wb") as f:
                            f.write(asset_bytes)
                        extracted_files.append(output_path.name)
                        extraction_count += 1

                except Exception as e:
                    log(f"  ❌ 提取资源 '{resource_name}' 时发生错误: {e}")

        if extraction_count == 0:
            msg = "未找到任何指定类型的资源进行提取。"
            log(f"⚠️ {msg}")
            return True, msg

        success_msg = f"成功提取 {extraction_count} 个资源。"
        log(f"\n🎉 {success_msg}")
        return True, success_msg

    except Exception as e:
        log(f"\n❌ 严重错误: 提取资源时发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"

def _extract_assets_from_bundle(
    env: UnityPy.Environment,
    asset_types_to_replace: set[str],
    key_func: KeyGeneratorFunc,
    spine_options: SpineOptions | None,
    log: LogFunc = no_log,
) -> dict[AssetKey, AssetContent]:
    """
    从源 bundle 的 env 构建替换清单
    即其他函数中使用的replacement_map
    """
    replacement_map: dict[AssetKey, AssetContent] = {}
    replace_all = "ALL" in asset_types_to_replace

    for obj in env.objects:
        if replace_all or (obj.type.name in asset_types_to_replace):
            data = obj.read()
            asset_key = key_func(obj, data)
            content = None
            resource_name = getattr(data, 'm_Name', f"<{obj.type.name} 资源>")

            if obj.type.name == "Texture2D":
                content = data.image
            elif obj.type.name == "TextAsset":
                asset_bytes = data.m_Script.encode("utf-8", "surrogateescape")
                if resource_name.lower().endswith('.skel'):
                    content = _handle_skel_upgrade(
                        skel_bytes=asset_bytes,
                        resource_name=resource_name,
                        spine_options=spine_options,
                        log=log
                    )
                else:
                    content = asset_bytes
            elif obj.type.name == "Mesh":
                content = obj.get_raw_data()
            elif replace_all:
                content = obj.get_raw_data()

            if content is not None:
                replacement_map[asset_key] = content
    
    return replacement_map

def _b2b_replace(
    old_bundle_path: Path,
    new_bundle_path: Path,
    asset_types_to_replace: set[str],
    spine_options: SpineOptions | None = None,
    log: LogFunc = no_log,
) -> tuple[UnityPy.Environment | None, int]:
    """
    执行 Bundle-to-Bundle 的核心替换逻辑。
    asset_types_to_replace: 要替换的资源类型集合（如 {"Texture2D", "TextAsset", "Mesh"} 的子集 或 {"ALL"}）
    按顺序尝试多种匹配策略（path_id, name_type），一旦有策略成功替换了至少一个资源，就停止并返回结果。
    返回一个元组 (modified_env, replacement_count)，如果失败则 modified_env 为 None。
    """
    # 1. 加载 bundles
    log(f"正在从旧版 bundle 中提取指定类型的资源: {', '.join(asset_types_to_replace)}")
    old_env = load_bundle(old_bundle_path, log)
    if not old_env:
        return None, 0
    
    log("正在加载新版 bundle...")
    new_env = load_bundle(new_bundle_path, log)
    if not new_env:
        return None, 0

    # 定义匹配策略
    strategies: list[tuple[str, KeyGeneratorFunc]] = [
        ('path_id', lambda obj, data: obj.path_id),
        ('name_type', lambda obj, data: (data.m_Name, obj.type.name))
    ]

    for name, key_func in strategies:
        log(f"\n正在尝试使用 '{name}' 策略进行匹配")
        
        # 2. 根据当前策略从旧版 bundle 构建“替换清单”
        log("  > 从旧版 bundle 提取资源...")
        old_assets_map = _extract_assets_from_bundle(
            old_env, asset_types_to_replace, key_func, spine_options, log
        )
        
        if not old_assets_map:
            log(f"  > ⚠️ 警告: 使用 '{name}' 策略未在旧版 bundle 中找到任何指定类型的资源。")
            continue

        log(f"  > 提取完成: 使用 '{name}' 策略从旧版 bundle 提取了 {len(old_assets_map)} 个资源。")

        # 3. 根据当前策略应用替换
        log("  > 向新版 bundle 写入资源...")
        
        replacement_count, replaced_logs \
        = _apply_replacements(new_env, old_assets_map, key_func, log)
        
        # 4. 如果当前策略成功替换了至少一个资源，就结束
        if replacement_count > 0:
            log(f"\n✅ 策略 '{name}' 成功替换了 {replacement_count} 个资源:")
            for item in replaced_logs:
                log(item)
            return new_env, replacement_count

        log(f"  > 策略 '{name}' 未能匹配到任何资源。")

    # 5. 所有策略都失败了
    log(f"\n⚠️ 警告: 所有匹配策略均未能在新版 bundle 中找到可替换的资源 ({', '.join(asset_types_to_replace)})。")
    return None, 0


def get_filename_prefix(filename: str, log: LogFunc = no_log) -> tuple[str | None, str]:
    """
    从旧版Mod文件名中提取用于搜索新版文件的前缀。
    返回 (前缀字符串, 状态消息) 的元组。
    """
    # 1. 通过日期模式确定文件名位置
    date_match = re.search(r'\d{4}-\d{2}-\d{2}', filename)
    if not date_match:
        msg = f"无法在文件名 '{filename}' 中找到日期模式 (YYYY-MM-DD)，无法确定用于匹配的文件前缀。"
        log(f"  > 失败: {msg}")
        return None, msg

    # 2. 向前查找可能的日服额外文件名部分
    prefix_end_index = date_match.start()
    
    # 查找日期模式之前的最后一个连字符分隔的部分
    # 例如在 "...-textures-YYYY-MM-DD..." 中的 "textures"
    before_date = filename[:prefix_end_index]
    
    # 如果日期模式前有连字符，尝试提取最后一个部分
    if before_date.endswith('-'):
        before_date = before_date[:-1]  # 移除末尾的连字符
    
    # 分割并获取最后一个部分
    parts = before_date.split('-')
    last_part = parts[-1] if parts else ''
    
    # 检查最后一个部分是否是日服版额外的资源类型
    resource_types = ['textures', 'assets', 'textassets', 'materials']
    
    if last_part.lower() in resource_types:
        # 如果找到了资源类型，则前缀不应该包含这个部分
        search_prefix = before_date.replace(f'-{last_part}', '') + '-'
    else:
        search_prefix = filename[:prefix_end_index]

    return search_prefix, "前缀提取成功"


def find_new_bundle_path(
    old_mod_path: Path,
    game_resource_dir: Path | list[Path],
    log: LogFunc = no_log,
) -> tuple[Path | None, str]:
    """
    根据旧版Mod文件，在游戏资源目录中智能查找对应的新版文件。
    支持单个目录路径或目录路径列表。
    返回 (找到的路径对象, 状态消息) 的元组。
    """
    # TODO: 只用Texture2D比较好像不太对，但是it works

    log(f"正在为 '{old_mod_path.name}' 搜索对应文件...")

    # 1. 提取文件名前缀
    prefix, prefix_message = get_filename_prefix(str(old_mod_path.name), log)
    if not prefix:
        return None, prefix_message
    log(f"  > 文件前缀: '{prefix}'")
    extension = '.bundle'

    # 2. 处理单个目录或目录列表
    if isinstance(game_resource_dir, Path):
        search_dirs = [game_resource_dir]
        log(f"  > 搜索目录: {game_resource_dir}")
    else:
        search_dirs = game_resource_dir
        log(f"  > 搜索目录列表: {[str(d) for d in search_dirs]}")

    # 3. 查找所有候选文件（前缀相同且扩展名一致）
    candidates: list[Path] = []
    for search_dir in search_dirs:
        if search_dir.exists() and search_dir.is_dir():
            dir_candidates = [f for f in search_dir.iterdir() if f.is_file() and f.name.startswith(prefix) and f.suffix == extension]
            candidates.extend(dir_candidates)
    
    if not candidates:
        if isinstance(game_resource_dir, Path):
            msg = f"在指定目录 '{game_resource_dir}' 中未找到任何匹配的文件。"
        else:
            msg = f"在所有指定目录中未找到任何匹配的文件。"
        log(f"  > 失败: {msg}")
        return None, msg
    log(f"  > 找到 {len(candidates)} 个候选文件，正在验证内容...")

    # 4. 加载旧Mod获取贴图列表
    old_env = load_bundle(old_mod_path, log)
    if not old_env:
        msg = "加载旧版Mod文件失败。"
        log(f"  > 失败: {msg}")
        return None, msg
    
    old_textures_map = {obj.read().m_Name for obj in old_env.objects if obj.type.name == "Texture2D"}
    
    if not old_textures_map:
        msg = "旧版Mod文件中不包含任何 Texture2D 资源。"
        log(f"  > 失败: {msg}")
        return None, msg
    log(f"  > 旧版Mod包含 {len(old_textures_map)} 个贴图资源。")

    # 5. 遍历候选文件，找到第一个包含匹配贴图的
    for candidate_path in candidates:
        log(f"  - 正在检查: {candidate_path.name}")
        
        env = load_bundle(candidate_path, log)
        if not env: continue
        
        for obj in env.objects:
            if obj.type.name == "Texture2D" and obj.read().m_Name in old_textures_map:
                msg = f"成功确定新版文件: {candidate_path.name}"
                log(f"  ✅ {msg}")
                return candidate_path, msg
    
    msg = "在所有候选文件中都未找到与旧版Mod贴图名称匹配的资源。无法确定正确的新版文件。"
    log(f"  > 失败: {msg}")
    return None, msg

def process_mod_update(
    old_mod_path: Path,
    new_bundle_path: Path,
    output_dir: Path,
    asset_types_to_replace: set[str],
    save_options: SaveOptions,
    spine_options: SpineOptions | None = None,
    log: LogFunc = no_log,
) -> tuple[bool, str]:
    """
    自动化Mod更新流程。
    
    该函数是Mod更新工具的核心处理函数，负责将旧版Mod中的资源替换到新版游戏资源中，
    并可选地进行CRC校验修正以确保文件兼容性。
    
    处理流程的主要阶段：
    - Bundle-to-Bundle替换：将旧版Mod中的指定类型资源替换到新版资源文件中
        - 支持替换Texture2D、TextAsset、Mesh等资源类型
        - 可选地升级Spine动画资源的Skel版本
    - CRC修正：根据选项决定是否对新生成的文件进行CRC校验修正
    
    Args:
        old_mod_path: 旧版Mod文件的路径
        new_bundle_path: 新版游戏资源文件的路径
        output_dir: 输出目录，用于保存生成的更新后文件
        asset_types_to_replace: 需要替换的资源类型集合（如 {"Texture2D", "TextAsset"}）
        save_options: 保存和CRC修正的选项
        spine_options: Spine资源升级的选项
        log: 日志记录函数，默认为空函数
    
    Returns:
        tuple[bool, str]: (是否成功, 状态消息) 的元组
    """
    try:
        log("="*50)
        log(f"  > 使用旧版 Mod: {old_mod_path.name}")
        log(f"  > 使用新版资源: {new_bundle_path.name}")
        if spine_options and spine_options.is_enabled():
            log(f"  > 已启用 Spine 升级工具: {spine_options.converter_path.name}")

        # 进行Bundle to Bundle 替换
        log("\n--- Bundle-to-Bundle 替换 ---")
        modified_env, replacement_count = _b2b_replace(
            old_bundle_path=old_mod_path, 
            new_bundle_path=new_bundle_path, 
            asset_types_to_replace=asset_types_to_replace, 
            spine_options=spine_options,
            log = log
        )

        if not modified_env:
            return False, "Bundle-to-Bundle 替换过程失败，请检查日志获取详细信息。"
        if replacement_count == 0:
            return False, "没有找到任何名称匹配的资源进行替换，无法继续更新。"
        
        log(f"  > B2B 替换完成，共处理 {replacement_count} 个资源。")
        
        # 保存和修正文件
        output_path = output_dir / new_bundle_path.name
        save_ok, save_message = _save_and_crc(
            env=modified_env,
            output_path=output_path,
            original_bundle_path=new_bundle_path,
            save_options=save_options,
            log=log
        )

        if not save_ok:
            return False, save_message

        log(f"最终文件已保存至: {output_path}")
        log(f"\n🎉 全部流程处理完成！")
        return True, "一键更新成功！"

    except Exception as e:
        log(f"\n❌ 严重错误: 在一键更新流程中发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"

def process_batch_mod_update(
    mod_file_list: list[Path],
    search_paths: list[Path],
    output_dir: Path,
    asset_types_to_replace: set[str],
    save_options: SaveOptions,
    spine_options: SpineOptions | None,
    log: LogFunc = no_log,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> tuple[int, int, list[str]]:
    """
    执行批量Mod更新的核心逻辑。

    Args:
        mod_file_list: 待更新的旧Mod文件路径列表。
        search_paths: 用于查找新版bundle文件的目录列表。
        output_dir: 输出目录。
        asset_types_to_replace: 需要替换的资源类型集合。
        save_options: 保存和CRC修正的选项。
        spine_options: Spine资源升级的选项。
        log: 日志记录函数。
        progress_callback: 进度回调函数，用于更新UI。
                           接收 (当前索引, 总数, 文件名)。

    Returns:
        tuple[int, int, list[str]]: (成功计数, 失败计数, 失败任务详情列表)
    """
    total_files = len(mod_file_list)
    success_count = 0
    fail_count = 0
    failed_tasks = []

    # 遍历每个旧Mod文件
    for i, old_mod_path in enumerate(mod_file_list):
        current_progress = i + 1
        filename = old_mod_path.name
        
        if progress_callback:
            progress_callback(current_progress, total_files, filename)

        log("\n" + "=" * 50)
        log(f"({current_progress}/{total_files}) 正在处理: {filename}")

        # 查找对应的新资源文件
        new_bundle_path, find_message = find_new_bundle_path(
            old_mod_path, search_paths, log
        )

        if not new_bundle_path:
            log(f"❌ 查找失败: {find_message}")
            fail_count += 1
            failed_tasks.append(f"{filename} - 查找失败: {find_message}")
            continue

        # 执行Mod更新处理
        success, process_message = process_mod_update(
            old_mod_path=old_mod_path,
            new_bundle_path=new_bundle_path,
            output_dir=output_dir,
            asset_types_to_replace=asset_types_to_replace,
            save_options=save_options,
            spine_options=spine_options,
            log=log
        )

        if success:
            log(f"✅ 处理成功: {filename}")
            success_count += 1
        else:
            log(f"❌ 处理失败: {filename} - {process_message}")
            fail_count += 1
            failed_tasks.append(f"{filename} - {process_message}")

    return success_count, fail_count, failed_tasks