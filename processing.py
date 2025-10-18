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

from utils import CRCUtils, no_log, get_skel_version_from_bytes

def load_bundle(
    bundle_path: Path,
    log = no_log
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
    log = no_log
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
    compression: str = "lzma",
    log=no_log
) -> bool:
    """
    将修改后的 Unity bundle 保存到指定路径。
    compression: 用于控制压缩方式。
                 - "lzma": (默认) 使用 LZMA 压缩。
                 - "lz4": 使用 LZ4 压缩。
                 - "original": 保留原始压缩方式。
                 - "none": 不进行压缩。
    """
    try:
        save_kwargs = {}
        if compression == "original":
            log("压缩方式: 保持原始设置")
            # Not passing the 'packer' argument preserves the original compression.
        elif compression == "none":
            log("压缩方式: 不压缩")
            save_kwargs['packer'] = ""  # An empty string typically means no compression.
        else:
            log(f"压缩方式: {compression.upper()}")
            save_kwargs['packer'] = compression

        with open(output_path, "wb") as f:
            f.write(env.file.save(**save_kwargs))

        return True
    except Exception as e:
        log(f"❌ 保存 bundle 文件到 '{output_path}' 时失败: {e}")
        log(traceback.format_exc())
        return False

def upgrade_skel(
    raw_skel_data: bytes,
    spine_converter_path: Path,
    target_spine_version: str,
    log=no_log
) -> tuple[bool, bytes]:
    """
    使用外部工具升级 .skel 文件。
    返回 (是否成功, skel数据) 的元组。
    """
    # 检查spine_converter_path是否为空或不存在
    if not spine_converter_path or not spine_converter_path.exists():
        log(f"  > ⚠️ Spine转换器路径无效或不存在: {spine_converter_path}")
        return False, raw_skel_data
    
    # 检查target_spine_version是否为空
    if not target_spine_version or not target_spine_version.strip():
        log(f"  > ⚠️ 目标Spine版本为空")
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
            str(spine_converter_path),
            str(temp_in_path),
            str(temp_out_path),
            "-v",
            target_spine_version
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
        log(f"    ❌ Spine 转换器未找到: {spine_converter_path}")
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

def process_asset_replacement(
    target_bundle_path: Path,
    asset_folder: Path,
    output_dir: Path,
    perform_crc: bool = True,
    enable_padding: bool = False,
    compression: str = "lzma",
    spine_converter_path: Path | None = None,
    target_spine_version: str | None = None,
    log = no_log
):
    """
    从指定文件夹替换bundle中的资源。
    支持替换 .png, .skel, .atlas 文件。
    - .png 文件将替换同名的 Texture2D 资源 (文件名不含后缀)。
    - .skel 和 .atlas 文件将替换同名的 TextAsset 资源 (文件名含后缀)。
    可选地升级Spine动画资源的Skel版本。
    此函数将生成的文件保存在工作目录中，以便后续进行"覆盖原文件"操作。
    返回 (是否成功, 状态消息) 的元组。
    
    Args:
        target_bundle_path: 目标Bundle文件的路径
        asset_folder: 包含替换资源的文件夹路径
        output_dir: 输出目录，用于保存生成的更新后文件
        perform_crc: 是否执行CRC修正，默认为True
        enable_padding: CRC修正时是否启用填充，默认为False
        compression: 文件压缩方式，默认为"lzma"
        spine_converter_path: Spine资源转换器路径，用于升级Skel版本。若不填写则跳过此步骤。
        target_spine_version: 目标Spine版本，用于版本升级
        log: 日志记录函数，默认为空函数
    """
    try:
        env = load_bundle(target_bundle_path, log)
        if not env:
            return False, "无法加载目标 Bundle 文件，即使在尝试移除潜在的 CRC 补丁后也是如此。请检查文件是否损坏。"
        
        # 判断Spine升级功能是否可用，以便在循环中快速检查
        spine_upgrade_enabled = (
            spine_converter_path
            and spine_converter_path.exists()
            and target_spine_version
            and target_spine_version.count(".") == 2  # 目标版本必须是 "x.y.zz" 格式
        )
        
        if spine_upgrade_enabled:
            log(f"  > 已启用 Spine 升级功能，目标版本: {target_spine_version}")
        
        # 使用字典来优化查找，按资源类型分类
        tasks_by_type = {
            "Texture2D": {},
            "TextAsset": {}
        }
        
        supported_extensions = [".png", ".skel", ".atlas"]
        input_files = [f for f in os.listdir(asset_folder) if f.lower().endswith(tuple(supported_extensions))]

        if not input_files:
            msg = f"在指定文件夹中没有找到任何支持的文件 ({', '.join(supported_extensions)})。"
            log(f"⚠️ 警告: {msg}")
            return False, msg

        # 准备替换任务
        for filename in input_files:
            full_path = os.path.join(asset_folder, filename)
            if filename.lower().endswith(".png"):
                asset_name = os.path.splitext(filename)[0]
                tasks_by_type["Texture2D"][asset_name] = full_path
            elif filename.lower().endswith((".skel", ".atlas")):
                asset_name = filename # 包含后缀
                tasks_by_type["TextAsset"][asset_name] = full_path
        
        original_tasks_count = len(tasks_by_type["Texture2D"]) + len(tasks_by_type["TextAsset"])
        log(f"找到 {original_tasks_count} 个待处理文件，正在扫描 bundle 并进行替换...")
        replacement_count = 0

        for obj in env.objects:
            # 如果所有任务都完成了，就提前退出循环
            if replacement_count == original_tasks_count:
                break

            if obj.type.name == "Texture2D":
                data = obj.read()
                # 避免重复处理
                image_path = tasks_by_type["Texture2D"].pop(data.m_Name, None)
                if image_path:
                    log(f"  > 找到匹配资源 '{data.m_Name}' (Texture2D)，准备替换...")
                    try:
                        img = Image.open(image_path).convert("RGBA")
                        data.image = img
                        data.save()
                        log(f"    ✅ 成功: 资源 '{data.m_Name}' 已被替换。")
                        replacement_count += 1
                    except Exception as e:
                        log(f"    ❌ 错误: 替换资源 '{data.m_Name}' 时发生错误: {e}")
                        # 如果替换失败，把任务加回去以便在最终报告中显示
                        tasks_by_type["Texture2D"][data.m_Name] = image_path

            elif obj.type.name == "TextAsset":
                data = obj.read()
                file_path = tasks_by_type["TextAsset"].pop(data.m_Name, None)
                if file_path:
                    log(f"  > 找到匹配资源 '{data.m_Name}' (TextAsset)，准备替换...")
                    try:
                        # 以二进制模式读取文件内容
                        with open(file_path, "rb") as f:
                            content_bytes = f.read()
                        
                        # 检查是否是需要升级的 .skel 文件
                        is_skel = data.m_Name.lower().endswith('.skel')
                        
                        if is_skel and spine_upgrade_enabled:
                            log(f"    > 检测到 .skel 文件: {data.m_Name}")
                            try:
                                # 检测 skel 的 spine 版本
                                current_version = get_skel_version_from_bytes(content_bytes, log)
                                target_major_minor = ".".join(target_spine_version.split('.')[:2])
                                
                                # 仅在主版本或次版本不匹配时才尝试升级
                                if current_version and not current_version.startswith(target_major_minor):
                                    log(f"      > spine 版本不匹配 (当前: {current_version}, 目标: {target_spine_version})。尝试升级...")

                                    # 无论成功与否，content_bytes 都会被赋予正确的数据（升级后的或原始的）
                                    skel_success, upgraded_content = upgrade_skel(
                                        raw_skel_data=content_bytes,
                                        spine_converter_path=spine_converter_path,
                                        target_spine_version=target_spine_version,
                                        log=log
                                    )
                                    if skel_success:
                                        log(f"      > 成功升级 .skel 文件: {data.m_Name}")
                                        content_bytes = upgraded_content
                                    else:
                                        log(f"      ❌ 升级 .skel 文件 '{data.m_Name}' 失败，使用原始文件")
                                else:
                                    log(f"      > 版本匹配或无法检测 ({current_version})，无需升级。")
                            except Exception as e:
                                log(f"      ❌ 错误: 检测或升级 .skel 文件 '{data.m_Name}' 时发生错误: {e}")
                        
                        # 将读取到的 bytes 解码为 str，并使用正确的 .m_Script 属性
                        # 使用 "surrogateescape" 错误处理程序以确保二进制数据也能被正确处理
                        data.m_Script = content_bytes.decode("utf-8", "surrogateescape")
                        
                        # 标记对象已更改，以便在保存时写入新数据
                        data.save()
                        
                        log(f"    ✅ 成功: 资源 '{data.m_Name}' 已被替换。")
                        replacement_count += 1
                    except Exception as e:
                        log(f"    ❌ 错误: 替换资源 '{data.m_Name}' 时发生错误: {e}")
                        tasks_by_type["TextAsset"][data.m_Name] = file_path

        if replacement_count == 0:
            log("⚠️ 警告: 没有执行任何成功的资源替换。")
            log("请检查：\n1. 文件名是否与 bundle 内的资源名完全匹配。\n2. bundle 文件是否正确。")
            return False, "没有找到任何名称匹配的资源进行替换。"
        
        log(f"\n替换完成: 成功替换 {replacement_count} / {original_tasks_count} 个资源。")

        # 报告未被替换的文件
        unmatched_tasks = tasks_by_type["Texture2D"].items() | tasks_by_type["TextAsset"].items()
        if unmatched_tasks:
            log("⚠️ 警告: 以下文件未在bundle中找到对应的资源:")
            for asset_name, file_path in unmatched_tasks:
                log(f"  - {Path(file_path).name} (尝试匹配: '{asset_name}')")

        output_path = output_dir / target_bundle_path.name

        if perform_crc:
            log(f"\n--- 阶段 2: CRC修正 ---")
            log(f"  > 准备直接保存并修正CRC...")
            
            if not save_bundle(env, output_path, compression, log):
                return False, "保存文件失败，操作已终止。"
            
            is_crc_success = CRCUtils.manipulate_crc(target_bundle_path, output_path, enable_padding)

            if not is_crc_success:
                if output_path.exists():
                    try:
                        output_path.unlink()
                        log(f"  > 已删除失败的CRC修正文件: {output_path}")
                    except OSError as e:
                        log(f"  > 警告: 清理失败的CRC修正文件时出错: {e}")
                return False, f"CRC 修正失败。最终文件 '{output_path}' 未能生成。"
            
            log("✅ CRC 修正成功！")
        else:
            log(f"\n--- 阶段 2: 保存最终文件 ---")
            log(f"  > 准备直接保存最终文件...")
            if not save_bundle(env, output_path, compression, log):
                return False, "保存最终文件失败，操作已终止。"

        log(f"最终文件已保存至: {output_path}")
        log(f"\n🎉 处理完成！")
        return True, f"处理完成！\n成功替换 {replacement_count} 个资源。\n\n文件已保存至工作目录，现在可以点击“覆盖原文件”按钮应用更改。"

    except Exception as e:
        log(f"\n❌ 严重错误: 处理 bundle 文件时发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"

def _b2b_replace(
    old_bundle_path: Path,
    new_bundle_path: Path,
    asset_types_to_replace: set,
    spine_converter_path: Path | None = None,
    target_spine_version: str | None = None,
    log = no_log,
):
    """
    执行 Bundle-to-Bundle 的核心替换逻辑。
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

    # 判断Spine升级功能是否可用，以便在循环中快速检查
    spine_upgrade_enabled = (
        "TextAsset" in asset_types_to_replace # skel文件以TextAsset类型存储
        and spine_converter_path
        and spine_converter_path.exists()
        and target_spine_version
        and target_spine_version.count(".") == 2  # 目标版本必须是 "x.y.zz" 格式
    )

    # 定义匹配策略
    # 每个策略是一个元组: (策略名, 获取资源key的函数)
    strategies = [
        (
            'path_id',  # 根据path_id来匹配
            lambda obj, data: obj.path_id
        ),
        (
            'name_type', # 根据资源名称和类型来匹配
            lambda obj, data: (data.m_Name, obj.type.name)
        )
    ]

    replace_all = "ALL" in asset_types_to_replace
    for name, key_func in strategies:
        log(f"正在尝试使用 '{name}' 策略进行匹配")
        
        # 2. 根据当前策略从旧版 bundle 提取资源
        old_assets_map = {}
        log("  > 从旧版 bundle 提取资源...")
        for obj in old_env.objects:
            if replace_all or (obj.type.name in asset_types_to_replace):
                data = obj.read() # 资源数据
                asset_key = key_func(obj, data)
                content = None # 替换后的资源内容
                resource_name = getattr(data, 'm_Name', f"<{obj.type.name}资源>")

                if obj.type.name == "Texture2D":
                    content = data.image
                elif obj.type.name == "TextAsset":
                    # 从 m_Script 获取 TextAsset 的原始字节内容
                    asset_bytes = data.m_Script.encode("utf-8", "surrogateescape")
                    
                    # 检查是否是需要升级的 .skel 文件
                    is_skel = resource_name.lower().endswith('.skel')

                    if is_skel and spine_upgrade_enabled:
                        log(f"    > 检测到 .skel 文件: {resource_name}")
                        try:
                            # 检测 skel 的 spine 版本
                            current_version = get_skel_version_from_bytes(asset_bytes, log)
                            target_major_minor = ".".join(target_spine_version.split('.')[:2])
                            
                            # 仅在主版本或次版本不匹配时才尝试升级
                            if current_version and not current_version.startswith(target_major_minor):
                                log(f"      > spine 版本不匹配 (当前: {current_version}, 目标: {target_spine_version})。尝试升级...")

                                # 无论成功与否，content 都会被赋予正确的数据（升级后的或原始的）
                                skel_success, content = upgrade_skel(
                                    raw_skel_data=asset_bytes,
                                    spine_converter_path=spine_converter_path,
                                    target_spine_version=target_spine_version,
                                    log=log
                                )
                                if skel_success:
                                    log(f"      > 成功升级 .skel 文件: {resource_name}")
                                else:
                                    log(f"      ❌ 升级 .skel 文件 '{resource_name}' 失败")
                            else:
                                log(f"      > 版本匹配或无法检测 ({current_version})，无需升级。")
                                content = asset_bytes
                        except Exception as e:
                            log(f"      ❌ 错误: 检测或升级 .skel 文件 '{resource_name}' 时发生错误: {e}")
                            content = asset_bytes # 出错时使用原始数据
                    else:
                        # 对于 .atlas 文件或无需/无法升级的 .skel 文件
                        content = asset_bytes
                else:
                    # 为其他可能的类型提供备用方案
                    if replace_all:
                        content = obj.get_raw_data()

                if content is not None:
                    old_assets_map[asset_key] = content
        
        if not old_assets_map:
            log(f"  > ⚠️ 警告: 使用 '{name}' 策略未在旧版 bundle 中找到任何指定类型的资源。")
            continue

        log(f"  > 提取完成: 使用 '{name}' 策略从旧版 bundle 提取了 {len(old_assets_map)} 个资源。")

        # 3. 根据当前策略执行替换
        replacement_count = 0
        replaced_assets_log = []
        log("  > 向新版 bundle 写入资源...")
        
        for obj in new_env.objects:
            if replace_all or (obj.type.name in asset_types_to_replace):
                new_data = obj.read()
                asset_key = key_func(obj, new_data)

                if asset_key in old_assets_map:
                    old_content = old_assets_map.pop(asset_key) # 使用pop避免重复替换
                    # 安全地获取资源名称，避免某些类型没有 m_Name 属性
                    resource_name = getattr(new_data, 'm_Name', f"<{obj.type.name}资源>")
                    try:
                        if obj.type.name == "Texture2D":
                            new_data.image = old_content
                            new_data.save()
                        elif obj.type.name == "TextAsset":
                            # old_content 是我们从旧包里提取的 bytes
                            # 我们需要将其解码为字符串，然后赋给 m_Script 属性
                            new_data.m_Script = old_content.decode("utf-8", "surrogateescape")
                            new_data.save()
                        else:
                            obj.set_raw_data(old_content)

                        replacement_count += 1
                        replaced_assets_log.append(f"  - {resource_name} ({obj.type.name})")

                    except Exception as e:
                        log(f"  ❌ 错误: 替换资源 '{resource_name}' ({obj.type.name}类型)时发生错误: {e}")

        # 4. 如果当前策略成功替换了至少一个资源，就结束
        if replacement_count > 0:
            log(f"\n✅ 策略 '{name}' 成功替换了 {replacement_count} 个资源:")
            for item in replaced_assets_log:
                log(item)
            return new_env, replacement_count

        log(f"  > 策略 '{name}' 未能匹配到任何资源。")

    # 5. 所有策略都失败了
    log(f"\n⚠️ 警告: 所有匹配策略均未能在新版 bundle 中找到可替换的资源 ({', '.join(asset_types_to_replace)})。")
    return None, 0

def process_bundle_to_bundle_replacement(
    new_bundle_path: Path, 
    old_bundle_path: Path, 
    output_path: Path, 
    create_backup_file: bool = True,
    compression: str = "lzma",
    log = no_log
):
    """
    从旧版Bundle包替换指定资源类型到新版Bundle包。
    """
    try:
        if create_backup_file:
            if not create_backup(new_bundle_path, log, "b2b"):
                return False, "创建备份失败，操作已终止。"

        asset_types = {"Texture2D"}
        modified_env, replacement_count = _b2b_replace(old_bundle_path, new_bundle_path, asset_types, log)

        if not modified_env:
            return False, "Bundle-to-Bundle 替换过程失败，请检查日志获取详细信息。"
        
        if replacement_count == 0:
            log("\n⚠️ 警告: 没有找到任何名称匹配的 Texture2D 资源进行替换。")
            log("请确认新旧两个bundle包中确实存在同名的贴图资源。")
            return False, "没有找到任何名称匹配的 Texture2D 资源进行替换。"

        if save_bundle(modified_env, output_path, compression, log):
            log("\n🎉 处理完成！")
            return True, f"处理完成！\n成功恢复/替换了 {replacement_count} 个资源。\n\n文件已保存至:\n{output_path}"
        else:
            return False, "保存文件失败，请检查日志获取详细信息。"

    except Exception as e:
        log(f"\n❌ 严重错误: 处理 bundle 文件时发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"


def get_filename_prefix(filename: str, log = no_log) -> tuple[str | None, str]:
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
    log = no_log
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
    asset_types_to_replace: set,
    perform_crc: bool = True,
    enable_padding: bool = False,
    compression: str = "lzma",
    spine_converter_path: Path | None = None,
    target_spine_version: str | None = None,
    log = no_log,
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
        perform_crc: 是否执行CRC修正，默认为True
        enable_padding: CRC修正时是否启用填充，默认为False
        compression: 文件压缩方式，默认为"lzma"
        spine_converter_path: Spine资源转换器路径，用于升级Skel版本。若不填写则跳过此步骤。
        target_spine_version: 目标Spine版本，用于版本升级
        log: 日志记录函数，默认为空函数
    
    Returns:
        tuple[bool, str]: (是否成功, 状态消息) 的元组
    """
    try:
        log("="*50)
        log(f"  > 使用旧版 Mod: {old_mod_path.name}")
        log(f"  > 使用新版资源: {new_bundle_path.name}")
        if spine_converter_path and spine_converter_path.exists():
            log(f"  > 已启用 Spine 升级工具: {spine_converter_path.name}")

        # --- 1. 执行 B2B 替换 ---
        log("\n--- Bundle-to-Bundle 替换 ---")
        
        # 进行Bundle to Bundle 替换
        modified_env, replacement_count = _b2b_replace(
            old_bundle_path=old_mod_path, 
            new_bundle_path=new_bundle_path, 
            asset_types_to_replace=asset_types_to_replace, 
            spine_converter_path=spine_converter_path,
            target_spine_version=target_spine_version,
            log = log
        )

        if not modified_env:
            return False, "Bundle-to-Bundle 替换过程失败，请检查日志获取详细信息。"
        if replacement_count == 0:
            return False, "没有找到任何名称匹配的资源进行替换，无法继续更新。"
        
        log(f"  > B2B 替换完成，共处理 {replacement_count} 个资源。")

        # --- 2. 根据选项决定是否执行CRC修正 ---
        # 在工作目录下生成文件
        output_path = output_dir / new_bundle_path.name

        if perform_crc:
            log(f"\n--- CRC 修正 ---")
            # 先保存未修正CRC的文件
            if not save_bundle(modified_env, output_path, compression, log):
                return False, "保存文件失败。"
            
            # 直接对最终文件进行CRC修正
            is_crc_success = CRCUtils.manipulate_crc(new_bundle_path, output_path, enable_padding)

            if not is_crc_success:
                if output_path.exists():
                    try:
                        output_path.unlink()
                        log(f"  > 已删除失败的CRC修正文件: {output_path}")
                    except OSError as e:
                        log(f"  > 警告: 清理失败的CRC修正文件时出错: {e}")
                return False, f"CRC 修正失败。最终文件 '{output_path.name}' 未能生成。"
            
            log("✅ CRC 修正成功！")
            
        else:
            log(f"\n--- 保存最终文件 ---")
            log(f"  > 准备直接保存最终文件...")
            if not save_bundle(modified_env, output_path, compression, log):
                return False, "保存最终文件失败，操作已终止。"

        log(f"最终文件已保存至: {output_path}")
        log(f"\n🎉 全部流程处理完成！")
        return True, "一键更新成功！"

    except Exception as e:
        log(f"\n❌ 严重错误: 在一键更新流程中发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"