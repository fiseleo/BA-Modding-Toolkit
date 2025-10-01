# processing.py

import UnityPy
import os
import traceback
from pathlib import Path
from PIL import Image
import shutil
import re

from utils import CRCUtils

def load_bundle(bundle_path: Path, log):
    """
    尝试加载一个 Unity bundle 文件。
    如果直接加载失败，会尝试移除末尾的几个字节后再次加载。
    """
    log(f"正在加载 bundle: {bundle_path.name}")

    # 1. 尝试直接加载
    try:
        env = UnityPy.load(str(bundle_path))
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
        log(f"  ❌ 错误: 无法读取文件 '{bundle_path.name}': {e}")
        return None

    # 定义加载策略：字节移除数量
    bytes_to_remove = [4, 8, 12]

    # 2. 依次尝试不同的加载策略
    for bytes_num in bytes_to_remove:
        if len(data) > bytes_num:
            try:
                trimmed_data = data[:-bytes_num]
                env = UnityPy.load(trimmed_data)
                log(f"  ✅ 尝试移除末尾{bytes_num}字节后成功加载")
                return env
            except Exception as e:
                log(f"  > 移除{bytes_num}字节后加载失败: {e}")
        else:
            log(f"  > 文件太小，无法移除{bytes_num}字节。")

    log(f"❌ 严重错误: 无法以任何方式加载 '{bundle_path.name}'。文件可能已损坏。")
    return None

def create_backup(original_path: Path, log, backup_mode: str = "default") -> bool:
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
        
        log(f"正在备份原始文件到: {backup_path.name}")
        shutil.copy2(original_path, backup_path)
        log("✅ 备份已创建。")
        return True
    except Exception as e:
        log(f"❌ 严重错误: 创建备份文件失败: {e}")
        return False

def save_bundle(env: UnityPy.Environment, output_path: Path, log) -> bool:
    """
    将修改后的 Unity bundle 保存到指定路径。
    """
    try:
        log(f"\n正在将修改后的 bundle 保存到: {output_path.name}")
        log("压缩方式: LZMA (这可能需要一些时间...)")
        
        with open(output_path, "wb") as f:
            f.write(env.file.save(packer="lzma"))
        
        log(f"✅ Bundle 文件已成功保存到: {output_path}")
        return True
    except Exception as e:
        log(f"❌ 保存 bundle 文件到 '{output_path}' 时失败: {e}")
        log(traceback.format_exc())
        return False

def process_png_replacement(target_bundle_path: Path, image_folder: Path, working_dir: Path, enable_padding: bool, perform_crc: bool, log):
    """
    从PNG文件夹替换贴图，并根据选项执行CRC修正。
    此函数将生成的文件保存在工作目录中，以便后续进行“覆盖原文件”操作。
    返回 (是否成功, 状态消息) 的元组。
    """
    try:
        env = load_bundle(target_bundle_path, log)
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

        final_path = working_dir / target_bundle_path.name

        if perform_crc:
            log(f"\n--- 阶段 2: CRC修正 ---")
            log(f"  > 准备直接保存并修正CRC...")
            
            # 先保存未修正CRC的文件到最终路径
            if not save_bundle(env, final_path, log):
                return False, "保存文件失败，操作已终止。"
            
            log(f"  > 原始文件 (用于CRC校验): {target_bundle_path}")
            log(f"  > 待修正文件: {final_path}")
            
            # 直接对最终文件进行CRC修正
            is_crc_success = CRCUtils.manipulate_crc(target_bundle_path, final_path, enable_padding)

            if not is_crc_success:
                if final_path.exists():
                    try:
                        final_path.unlink()
                        log(f"  > 已删除失败的CRC修正文件: {final_path}")
                    except OSError as e:
                        log(f"  > 警告: 清理失败的CRC修正文件时出错: {e}")
                return False, f"CRC 修正失败。最终文件 '{final_path}' 未能生成。"
            
            log("✅ CRC 修正成功！")
        else:
            log(f"\n--- 阶段 2: 保存最终文件 ---")
            log(f"  > 准备直接保存最终文件...")
            if not save_bundle(env, final_path, log):
                return False, "保存最终文件失败，操作已终止。"

        log(f"最终文件已保存至: {final_path}")
        log(f"\n🎉 处理完成！")
        return True, f"处理完成！\n成功替换 {replacement_count} 个资源。\n\n文件已保存至工作目录，现在可以点击“覆盖原文件”按钮应用更改。"

    except Exception as e:
        log(f"\n❌ 严重错误: 处理 bundle 文件时发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"

def _b2b_replace(old_bundle_path: Path, new_bundle_path: Path, log, asset_types_to_replace: set):
    """
    执行 Bundle-to-Bundle 的核心替换逻辑。
    首先尝试使用 path_id 进行匹配替换，如果没有任何资源被替换，则回退到使用 (资源名, 资源类型) 进行匹配。
    返回一个元组 (modified_env, replacement_count)，如果失败则 modified_env 为 None。
    """
    # 1. 加载两个 bundles
    log(f"正在从旧版 bundle 中提取指定类型的资源: {', '.join(asset_types_to_replace)}")
    old_env = load_bundle(old_bundle_path, log)
    if not old_env:
        return None, 0
    
    log("正在加载新版 bundle...")
    new_env = load_bundle(new_bundle_path, log)
    if not new_env:
        return None, 0

    # 辅助函数: 根据不同策略从旧版 bundle 提取资源
    def extract_old_assets(key_strategy: str):
        """
        根据给定的策略从旧版 bundle 中提取资源。
        返回一个字典，键为资源键，值为资源内容。
        """
        assets_map = {}
        log(f"  > 正在使用 '{key_strategy}' 策略从旧版 bundle 提取资源...")
        for obj in old_env.objects:
            if obj.type.name in asset_types_to_replace:
                data = obj.read()
                
                if key_strategy == 'path_id':
                    asset_key = obj.path_id
                elif key_strategy == 'name_type':
                    asset_key = (data.m_Name, obj.type.name)
                else:
                    continue

                # 获取资源内容
                # 对于 Texture2D，只提取出图片数据，保留资源其他属性
                content = data.image if obj.type.name == "Texture2D" else obj.get_raw_data()
                assets_map[asset_key] = content
        
        if not assets_map:
            log(f"  > ⚠️ 警告: 使用 '{key_strategy}' 策略未在旧版 bundle 中找到任何指定类型的资源。")
        else:
            log(f"  > 提取完成，使用 '{key_strategy}' 策略找到 {len(assets_map)} 个资源。")
        return assets_map

    # 辅助函数: 执行一轮替换
    def perform_replacement_pass(assets_map: dict, key_strategy: str):
        """
        根据给定的策略执行一轮替换。
        返回一个元组 (replacement_count, replaced_assets)，
        其中 replacement_count 为替换的资源数量，replaced_assets 为被替换的资源列表。
        """

        log(f"正在使用 '{key_strategy}' 策略进行替换扫描")
        count = 0
        replaced = []
        for obj in new_env.objects:
            if obj.type.name in asset_types_to_replace:
                new_data = obj.read()
                
                if key_strategy == 'path_id':
                    asset_key = obj.path_id
                elif key_strategy == 'name_type':
                    asset_key = (new_data.m_Name, obj.type.name)
                else:
                    log(f"  ❌ 错误: 未知的替换策略 '{key_strategy}'。")
                    return 0, []

                if asset_key in assets_map:
                    old_content = assets_map[asset_key]
                    try:
                        if obj.type.name == "Texture2D":
                            new_data.image = old_content
                            new_data.save()
                            log(f"  ✅ 成功: 已替换图像 '{new_data.m_Name}' ({new_data.m_TextureFormat.name} 格式)。")
                        else:
                            obj.set_raw_data(old_content)
                            log(f"  ✅ 成功: 已替换资源 '{new_data.m_Name}' ({obj.type.name} 类型)。")

                        count += 1
                        # 在日志中明确 key，方便调试
                        replaced.append(f"{new_data.m_Name} ({obj.type.name}, key: {asset_key})")
                    except Exception as e:
                        log(f"  ❌ 错误: 替换资源 '{new_data.m_Name}' ({obj.type.name}类型)时发生错误: {e}")
        return count, replaced

    # 4.1 尝试使用 path_id (主要策略)
    old_assets_map_by_id = extract_old_assets('path_id')
    replacement_count = 0
    replaced_assets = []

    if old_assets_map_by_id:
        replacement_count, replaced_assets = perform_replacement_pass(old_assets_map_by_id, 'path_id')

    # 4.2: 如果主要策略失败，回退到 name_type
    if replacement_count == 0:
        log("\n⚠️ 警告: 使用 path_id 未能匹配到任何资源。正在尝试使用 (资源名, 资源类型) 作为备用策略...")
        
        old_assets_map_by_name = extract_old_assets('name_type')
        if old_assets_map_by_name:
            replacement_count, replaced_assets = perform_replacement_pass(old_assets_map_by_name, 'name_type')

    # 5. 总结和返回
    if replacement_count == 0:
        # 两种策略都失败了，返回失败
        log(f"⚠️ 警告: 两种匹配策略均未能在新版 bundle 中找到可替换的资源 ({', '.join(asset_types_to_replace)})。")
        return None, 0

    log(f"\n成功替换了 {replacement_count} 个资源:")
    for name in replaced_assets:
        log(f"  - {name}")
    return new_env, replacement_count

def process_bundle_to_bundle_replacement(new_bundle_path: Path, old_bundle_path: Path, output_path: Path, log, create_backup_file: bool = True):
    """
    从旧版Bundle包替换指定资源类型到新版Bundle包。
    """
    try:
        if create_backup_file:
            if not create_backup(new_bundle_path, log, "b2b"):
                return False, "创建备份失败，操作已终止。"

        asset_types = {"Texture2D"}
        modified_env, replacement_count = _b2b_replace(old_bundle_path, new_bundle_path, log, asset_types)

        if not modified_env:
            return False, "Bundle-to-Bundle 替换过程失败，请检查日志获取详细信息。"
        
        if replacement_count == 0:
            log("\n⚠️ 警告: 没有找到任何名称匹配的 Texture2D 资源进行替换。")
            log("请确认新旧两个bundle包中确实存在同名的贴图资源。")
            return False, "没有找到任何名称匹配的 Texture2D 资源进行替换。"

        if save_bundle(modified_env, output_path, log):
            log("\n🎉 处理完成！")
            return True, f"处理完成！\n成功恢复/替换了 {replacement_count} 个资源。\n\n文件已保存至:\n{output_path}"
        else:
            return False, "保存文件失败，请检查日志获取详细信息。"

    except Exception as e:
        log(f"\n❌ 严重错误: 处理 bundle 文件时发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"


def find_new_bundle_path(old_mod_path: Path, game_resource_dir: Path, log):
    """
    根据旧版Mod文件，在游戏资源目录中智能查找对应的新版文件。
    返回 (找到的路径对象, 状态消息) 的元组。
    """
    # TODO: 只用Texture2D比较好像不太对，但是it works

    log(f"正在为 '{old_mod_path.name}' 搜索对应文件...")

    # 1. 通过日期模式确定文件名位置
    date_match = re.search(r'\d{4}-\d{2}-\d{2}', old_mod_path.name)
    if not date_match:
        msg = f"无法在旧文件名 '{old_mod_path.name}' 中找到日期模式 (YYYY-MM-DD)，无法确定用于匹配的文件前缀。"
        log(f"  > 失败: {msg}")
        return None, msg

    # 2. 向前查找可能的日服额外文件名部分
    prefix_end_index = date_match.start()
    
    # 查找日期模式之前的最后一个连字符分隔的部分
    # 例如在 "...-textures-YYYY-MM-DD..." 中的 "textures"
    before_date = old_mod_path.name[:prefix_end_index]
    
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
        search_prefix = old_mod_path.name[:prefix_end_index]
    
    log(f"  > 使用前缀: '{search_prefix}'")
    extension = '.bundle'

    # 3. 查找所有候选文件（前缀相同且扩展名一致）
    candidates = [f for f in game_resource_dir.iterdir() if f.is_file() and f.name.startswith(search_prefix) and f.suffix == extension]
    if not candidates:
        msg = f"在指定目录 '{game_resource_dir}' 中未找到任何匹配的文件。"
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
        log(f"    - 正在检查: {candidate_path.name}")
        try:
            env = UnityPy.load(str(candidate_path))
            if not env: continue
            
            for obj in env.objects:
                if obj.type.name == "Texture2D" and obj.read().m_Name in old_textures_map:
                    msg = f"成功确定新版文件: {candidate_path.name}"
                    log(f"  ✅ {msg}")
                    return candidate_path, msg
        except Exception:
            log(f"    - 警告: 无法加载候选文件 {candidate_path.name}, 已跳过。")
            continue
    
    msg = "在所有候选文件中都未找到与旧版Mod贴图名称匹配的资源。无法确定正确的新版文件。"
    log(f"  > 失败: {msg}")
    return None, msg


def process_mod_update(
    old_mod_path: Path,
    new_bundle_path: Path,
    working_dir: Path,
    enable_padding: bool,
    log,
    perform_crc: bool,
    asset_types_to_replace: set):
    """
    自动化Mod更新流程。
    接收旧版Mod路径和新版资源路径，将生成文件保存在指定的working_dir下。
    返回 (是否成功, 状态消息) 的元组。
    """
    try:
        log(f"  > 使用旧版 Mod: {old_mod_path.name}")
        log(f"  > 使用新版资源: {new_bundle_path.name}")
        log(f"  > 使用工作目录: {working_dir}")

        # --- 1. 执行 B2B 替换 ---
        log("\n--- 阶段 1: Bundle-to-Bundle 替换 ---")
        
        # 将资源类型集合传递给核心函数
        modified_env, replacement_count = _b2b_replace(old_mod_path, new_bundle_path, log, asset_types_to_replace)

        if not modified_env:
            return False, "Bundle-to-Bundle 替换过程失败，请检查日志获取详细信息。"
        if replacement_count == 0:
            return False, "没有找到任何名称匹配的资源进行替换，无法继续更新。"
        
        log(f"  > B2B 替换完成，共处理 {replacement_count} 个资源。")

        # --- 2. 根据选项决定是否执行CRC修正 ---
        # 在工作目录下生成文件
        final_path = working_dir / new_bundle_path.name

        if perform_crc:
            log(f"\n--- 阶段 2: CRC修正 ---")
            # 先保存未修正CRC的文件到最终路径
            if not save_bundle(modified_env, final_path, log):
                return False, "保存文件失败，操作已终止。"
            
            log(f"  > 原始文件 (用于CRC校验): {new_bundle_path}")
            log(f"  > 待修正文件: {final_path}")
            
            # 直接对最终文件进行CRC修正
            is_crc_success = CRCUtils.manipulate_crc(new_bundle_path, final_path, enable_padding)

            if not is_crc_success:
                if final_path.exists():
                    try:
                        final_path.unlink()
                        log(f"  > 已删除失败的CRC修正文件: {final_path}")
                    except OSError as e:
                        log(f"  > 警告: 清理失败的CRC修正文件时出错: {e}")
                return False, f"CRC 修正失败。最终文件 '{final_path.name}' 未能生成。"
            
            log("✅ CRC 修正成功！")

        else:
            log(f"\n--- 阶段 2: 保存最终文件 ---")
            log(f"  > 准备直接保存最终文件...")
            if not save_bundle(modified_env, final_path, log):
                return False, "保存最终文件失败，操作已终止。"

        log(f"最终文件已保存至: {final_path}")
        log(f"\n🎉 全部流程处理完成！")
        return True, "一键更新成功！"

    except Exception as e:
        log(f"\n❌ 严重错误: 在一键更新流程中发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"