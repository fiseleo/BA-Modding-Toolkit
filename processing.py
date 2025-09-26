# processing.py

import UnityPy
import os
import traceback
from pathlib import Path
from PIL import Image
import shutil
import re

from utils import CRCUtils

def load_bundle(bundle_path: str, log):
    """
    尝试加载一个 Unity bundle 文件。
    如果直接加载失败，会尝试移除末尾的8个或4个字节（可能是CRC修正数据）后再次加载。
    """
    path_obj = Path(bundle_path)
    log(f"正在加载 bundle: {path_obj.name}")

    # 1. 尝试直接加载
    try:
        log("  > 尝试直接加载...")
        env = UnityPy.load(bundle_path)
        log("  ✅ 直接加载成功。")
        return env
    except Exception as e:
        if 'insufficient space' in str(e):
            log(f"  > 直接加载失败，将尝试作为CRC修正后的文件加载。")
        else:
            log(f"  > 直接加载失败: {e}。将尝试作为CRC修正后的文件加载。")

    # 如果直接加载失败，读取文件内容到内存
    try:
        with open(bundle_path, "rb") as f:
            data = f.read()
    except Exception as e:
        log(f"  ❌ 错误: 无法读取文件 '{path_obj.name}': {e}")
        return None

    # 2. 尝试移除末尾8个字节 (padding + crc)
    if len(data) > 8:
        try:
            log("  > 尝试移除末尾8字节后加载...")
            trimmed_data = data[:-8]
            env = UnityPy.load(trimmed_data)
            log("  ✅ 成功加载（移除了8字节）。")
            return env
        except Exception as e:
            log(f"  > 移除8字节后加载失败: {e}")
    else:
        log("  > 文件太小，无法移除8字节。")

    # 3. 尝试移除末尾4个字节 (crc only)
    if len(data) > 4:
        try:
            log("  > 尝试移除末尾4字节后加载...")
            trimmed_data = data[:-4]
            env = UnityPy.load(trimmed_data)
            log("  ✅ 成功加载（移除了4字节）。")
            return env
        except Exception as e:
            log(f"  > 移除4字节后加载失败: {e}")
    else:
        log("  > 文件太小，无法移除4字节。")

    log(f"❌ 严重错误: 无法以任何方式加载 '{path_obj.name}'。文件可能已损坏。")
    return None

def create_backup(original_path: str, log, backup_mode: str = "default") -> bool:
    """
    创建原始文件的备份
    backup_mode: "default" - 在原文件后缀后添加.bak
                 "b2b" - 重命名为orig_(原名)
    """
    try:
        path_obj = Path(original_path)
        if backup_mode == "b2b":
            backup_path = path_obj.with_name(f"orig_{path_obj.name}")
        else:
            backup_path = path_obj.with_suffix(path_obj.suffix + '.bak')
        
        log(f"正在备份原始文件到: {backup_path.name}")
        shutil.copy2(original_path, backup_path)
        log("✅ 备份已创建。")
        return True
    except Exception as e:
        log(f"❌ 严重错误: 创建备份文件失败: {e}")
        return False

def process_bundle_replacement(bundle_path: str, image_folder: str, output_path: str, log, create_backup_file: bool = True):
    """
    模式1: 从PNG文件夹替换贴图。
    """
    try:
        if create_backup_file:
            if not create_backup(bundle_path, log):
                return False, "创建备份失败，操作已终止。"

        env = load_bundle(bundle_path, log)
        if not env:
            return False, "无法加载目标 Bundle 文件，即使在尝试移除潜在的 CRC 补丁后也是如此。请检查文件是否损坏。"
        
        replacement_tasks = []
        image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(".png")]

        if not image_files:
            log("⚠️ 警告: 在指定文件夹中没有找到任何 .png 文件。")
            return False, "在指定文件夹中没有找到任何 .png 文件。"

        for filename in image_files:
            asset_name = os.path.splitext(filename)[0]
            full_image_path = os.path.join(image_folder, filename)
            replacement_tasks.append((asset_name, full_image_path))

        log("正在扫描 bundle 并进行替换...")
        replacement_count = 0
        original_tasks_count = len(replacement_tasks)

        for obj in env.objects:
            if obj.type.name == "Texture2D":
                data = obj.read()
                task_to_remove = None
                for asset_name, image_path in replacement_tasks:
                    if data.m_Name == asset_name:
                        log(f"  > 找到匹配资源 '{asset_name}'，准备替换...")
                        try:
                            img = Image.open(image_path).convert("RGBA")
                            data.image = img
                            data.save()
                            log(f"    ✅ 成功: 资源 '{data.m_Name}' 已被替换。")
                            replacement_count += 1
                            task_to_remove = (asset_name, image_path)
                            break 
                        except Exception as e:
                            log(f"    ❌ 错误: 替换资源 '{asset_name}' 时发生错误: {e}")
                if task_to_remove:
                    replacement_tasks.remove(task_to_remove)

        if replacement_count == 0:
            log("⚠️ 警告: 没有执行任何成功的资源替换。")
            log("请检查：\n1. 图片文件名（不含.png）是否与 bundle 内的 Texture2D 资源名完全匹配。\n2. bundle 文件是否正确。")
            return False, "没有找到任何名称匹配的资源进行替换。"
        
        log(f"\n替换完成: 成功替换 {replacement_count} / {original_tasks_count} 个资源。")

        if replacement_tasks:
            log("⚠️ 警告: 以下图片文件未在bundle中找到对应的Texture2D资源:")
            for asset_name, _ in replacement_tasks:
                log(f"  - {asset_name}")

        log(f"\n正在将修改后的 bundle 保存到: {Path(output_path).name}")
        log("压缩方式: LZMA (这可能需要一些时间...)")
        
        with open(output_path, "wb") as f:
            f.write(env.file.save(packer="lzma"))
        
        log("\n🎉 处理完成！新的 bundle 文件已成功保存。")
        return True, f"处理完成！\n成功替换 {replacement_count} 个资源。\n\n文件已保存至:\n{output_path}"

    except Exception as e:
        log(f"\n❌ 严重错误: 处理 bundle 文件时发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"

def process_bundle_to_bundle_replacement(new_bundle_path: str, old_bundle_path: str, output_path: str, log, create_backup_file: bool = True):
    """
    模式2: 从旧版Bundle包恢复/替换贴图到新版Bundle包。
    """
    try:
        if create_backup_file:
            if not create_backup(new_bundle_path, log, "b2b"):
                return False, "创建备份失败，操作已终止。"

        new_env = load_bundle(new_bundle_path, log)
        if not new_env:
            return False, "无法加载新版 Bundle 文件，即使在尝试移除潜在的 CRC 补丁后也是如此。请检查文件是否损坏。"
        
        old_env = load_bundle(old_bundle_path, log)
        if not old_env:
            return False, "无法加载旧版 Bundle 文件，即使在尝试移除潜在的 CRC 补丁后也是如此。请检查文件是否损坏。"

        log("\n正在从旧版 bundle 中提取 Texture2D 资源...")
        old_textures_map = {}
        for obj in old_env.objects:
            if obj.type.name == "Texture2D":
                data = obj.read()
                old_textures_map[data.m_Name] = data.image
        
        if not old_textures_map:
            log("⚠️ 警告: 在旧版 bundle 中没有找到任何 Texture2D 资源。")
            return False, "在旧版 bundle 中没有找到任何 Texture2D 资源，无法进行替换。"

        log(f"提取完成，共找到 {len(old_textures_map)} 个 Texture2D 资源。")

        log("\n正在扫描新版 bundle 并进行替换...")
        replacement_count = 0
        replaced_assets = []

        for obj in new_env.objects:
            if obj.type.name == "Texture2D":
                new_data = obj.read()
                if new_data.m_Name in old_textures_map:
                    log(f"  > 找到匹配资源 '{new_data.m_Name}'，准备从旧版恢复...")
                    try:
                        new_data.image = old_textures_map[new_data.m_Name]
                        new_data.save()
                        log(f"    ✅ 成功: 资源 '{new_data.m_Name}' 已被恢复。")
                        replacement_count += 1
                        replaced_assets.append(new_data.m_Name)
                    except Exception as e:
                        log(f"    ❌ 错误: 恢复资源 '{new_data.m_Name}' 时发生错误: {e}")

        if replacement_count == 0:
            log("\n⚠️ 警告: 没有找到任何名称匹配的 Texture2D 资源进行替换。")
            log("请确认新旧两个bundle包中确实存在同名的贴图资源。")
            return False, "没有找到任何名称匹配的 Texture2D 资源进行替换。"
        
        log(f"\n成功恢复/替换了 {replacement_count} 个资源:")
        for name in replaced_assets:
            log(f"  - {name}")

        log(f"\n正在将修改后的 bundle 保存到: {Path(output_path).name}")
        log("压缩方式: LZMA (这可能需要一些时间...)")
        
        with open(output_path, "wb") as f:
            f.write(new_env.file.save(packer="lzma"))

        log("\n🎉 处理完成！新的 bundle 文件已成功保存。")
        return True, f"处理完成！\n成功恢复/替换了 {replacement_count} 个资源。\n\n文件已保存至:\n{output_path}"

    except Exception as e:
        log(f"\n❌ 严重错误: 处理 bundle 文件时发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"


def find_new_bundle_path(old_mod_path_str: str, game_resource_dir_str: str, log):
    """
    根据旧版Mod文件，在游戏资源目录中智能查找对应的新版文件。
    返回 (找到的路径对象, 状态消息) 的元组。
    """
    old_mod_path = Path(old_mod_path_str)
    game_resource_dir = Path(game_resource_dir_str)
    
    log(f"正在为 '{old_mod_path.name}' 搜索新版文件...")

    # 1. 通过日期模式确定文件名前缀
    date_match = re.search(r'\d{4}-\d{2}-\d{2}', old_mod_path.name)
    if not date_match:
        msg = f"无法在旧文件名 '{old_mod_path.name}' 中找到日期模式 (YYYY-MM-DD)，无法确定用于匹配的文件前缀。"
        log(f"  > 失败: {msg}")
        return None, msg

    prefix_end_index = date_match.start()
    search_prefix = old_mod_path.name[:prefix_end_index]
    log(f"  > 已确定文件名前缀: '{search_prefix}...'")

    # 2. 查找所有候选文件
    candidates = [f for f in game_resource_dir.iterdir() if f.is_file() and f.name.startswith(search_prefix)]
    if not candidates:
        msg = f"在游戏资源目录中未找到任何与 '{search_prefix}' 匹配的新版文件。"
        log(f"  > 失败: {msg}")
        return None, msg
    log(f"  > 找到 {len(candidates)} 个候选文件，正在验证内容...")

    # 3. 加载旧Mod获取贴图列表
    old_env = load_bundle(str(old_mod_path), log)
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

    # 4. 遍历候选文件，找到第一个包含匹配贴图的
    for candidate_path in candidates:
        log(f"    - 正在检查: {candidate_path.name}")
        try:
            env = UnityPy.load(str(candidate_path))
            if not env: continue
            
            for obj in env.objects:
                if obj.type.name == "Texture2D" and obj.read().m_Name in old_textures_map:
                    msg = f"成功确定新版文件: {candidate_path.name}"
                    log(f"  > ✅ {msg}")
                    return candidate_path, msg
        except Exception:
            log(f"    - 警告: 无法加载候选文件 {candidate_path.name}, 已跳过。")
            continue
    
    msg = "在所有候选文件中都未找到与旧版Mod贴图名称匹配的资源。无法确定正确的新版文件。"
    log(f"  > 失败: {msg}")
    return None, msg


def process_mod_update(old_mod_path_str: str, new_bundle_path_str: str, working_dir_str: str, enable_padding: bool, log, perform_crc: bool):
    """
    自动化Mod更新流程。
    此版本直接接收旧版Mod路径和新版资源路径，并且将文件保存在指定的working_dir_str下。
    """
    try:
        log("🚀 开始一键更新流程...")
        old_mod_path = Path(old_mod_path_str)
        new_bundle_path = Path(new_bundle_path_str) 
        base_working_dir = Path(working_dir_str)

        log(f"  > 使用旧版 Mod: {old_mod_path.name}")
        log(f"  > 使用新版资源: {new_bundle_path.name}")

        # --- 1. 创建工作目录 ---
        # processing.py 不再创建子目录，直接使用 ui.py 提供的目录
        log(f"  > 使用工作目录: {base_working_dir}")

        # --- 2. 执行 B2B 替换 ---
        log("\n--- 阶段 1: Bundle-to-Bundle 替换 ---")
        
        # 加载旧版 Mod 的贴图数据
        old_env = load_bundle(old_mod_path_str, log)
        if not old_env:
            return False, "加载旧版 Mod 文件失败。"
        old_textures_map = {}
        for obj in old_env.objects:
            if obj.type.name == "Texture2D":
                data = obj.read()
                old_textures_map[data.m_Name] = data.image

        # 加载新版文件并替换
        new_env = load_bundle(str(new_bundle_path), log)
        if not new_env:
            return False, "加载新版文件失败。"

        replacement_count = 0
        for obj in new_env.objects:
            if obj.type.name == "Texture2D":
                new_data = obj.read()
                if new_data.m_Name in old_textures_map:
                    new_data.image = old_textures_map[new_data.m_Name]
                    new_data.save()
                    replacement_count += 1
        
        log(f"  > B2B 替换完成，共处理 {replacement_count} 个贴图。")

        # --- 3. 根据选项决定是否执行CRC修正 ---
        intermediate_path = None # 用于存储未修正CRC的文件路径
        final_path = base_working_dir / new_bundle_path.name # 最终文件直接保存在base_working_dir下

        if perform_crc:
            intermediate_path = base_working_dir / f"uncrc_{new_bundle_path.name}"
            log(f"  > 正在保存未修正CRC的中间文件到: {intermediate_path.name}")
            with open(intermediate_path, "wb") as f:
                f.write(new_env.file.save(packer="lzma"))
            log("  > 中间文件保存成功。")

            log("\n--- 阶段 2: CRC 修正 ---")
            
            log(f"  > 正在复制 '{intermediate_path.name}' 到 '{final_path.name}' 以进行CRC修正。")
            shutil.copy2(intermediate_path, final_path)
            
            log(f"  > 原始文件 (用于CRC校验): {new_bundle_path.name}")
            log(f"  > 待修正文件: {final_path.name}")
            
            # 注意：这里的原始文件应该是新版游戏资源文件 (new_bundle_path)
            is_crc_success = CRCUtils.manipulate_crc(str(new_bundle_path), str(final_path), enable_padding)

            if not is_crc_success:
                # 如果CRC修正失败，尝试删除最终文件（如果存在）
                if final_path.exists():
                    try:
                        final_path.unlink()
                        log(f"  > 已删除失败的CRC修正文件: {final_path.name}")
                    except OSError as e:
                        log(f"  > 警告: 清理失败的CRC修正文件时出错: {e}")
                return False, f"CRC 修正失败。最终文件 '{final_path.name}' 未能生成。"
            
            log("✅ CRC 修正成功！")
            log(f"\n🎉 全部流程处理完成！")
            log(f"未修正CRC的文件已保存: {intermediate_path}")
            log(f"最终文件已保存至: {final_path}")

            return True, f"一键更新成功！\n\n最终文件保存在:\n{final_path}\n\n(同时保留了未修正CRC的版本 '{intermediate_path.name}')"
        else:
            log(f"  > CRC修正已跳过。正在直接保存最终文件到: {final_path.name}")
            with open(final_path, "wb") as f:
                f.write(new_env.file.save(packer="lzma"))
            log("  > 最终文件保存成功。")

            log(f"\n🎉 全部流程处理完成！")
            log(f"最终文件已保存至: {final_path}")
            
            return True, f"一键更新成功！ (已跳过CRC修正)\n\n最终文件保存在:\n{final_path}"

    except Exception as e:
        log(f"\n❌ 严重错误: 在一键更新流程中发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"