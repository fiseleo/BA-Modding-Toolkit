# processing.py

import UnityPy
import os
import traceback
from pathlib import Path
from PIL import Image
import shutil
import binascii

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

def bytes_to_u32_be(b):
    return int.from_bytes(b, 'big')

def u32_to_bytes_be(i):
    return i.to_bytes(4, 'big')

def reverse_bits_in_bytes(b):
    # b is 4 bytes
    num = bytes_to_u32_be(b)
    rev = 0
    for i in range(32):
        if (num >> i) & 1:
            rev |= 1 << (31 - i)
    return u32_to_bytes_be(rev)

def gf_multiply(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        a <<= 1
        b >>= 1
    return result

def gf_divide(dividend, divisor):
    if divisor == 0:
        return 0
    quotient = 0
    remainder = dividend
    divisor_bits = divisor.bit_length()
    while remainder.bit_length() >= divisor_bits and remainder != 0:
        shift = remainder.bit_length() - divisor_bits
        quotient |= 1 << shift
        remainder ^= divisor << shift
    return quotient

def gf_mod(dividend, divisor, n):
    if divisor == 0:
        return dividend
    dividend_bits = dividend.bit_length()
    divisor_bits = divisor.bit_length()
    while dividend != 0 and dividend.bit_length() >= divisor_bits:
        shift = dividend.bit_length() - divisor_bits
        dividend ^= divisor << shift
    mask = (1 << n) - 1 if n < 64 else 0xFFFFFFFFFFFFFFFF
    return dividend & mask

def gf_multiply_modular(a, b, modulus, n):
    product = gf_multiply(a, b)
    return gf_mod(product, modulus, n)

def gf_modular_inverse(a, m):
    if a == 0:
        raise ValueError("Inverse of zero does not exist")
    old_r, r = m, a
    old_s, s = 0, 1
    while r != 0:
        q = gf_divide(old_r, r)
        old_r, r = r, old_r ^ gf_multiply(q, r)
        old_s, s = s, old_s ^ gf_multiply(q, s)
    if old_r != 1:
        raise ValueError("Modular inverse does not exist")
    return old_s

def gf_inverse(k, poly):
    x32 = 0x100000000
    inverse = gf_modular_inverse(x32, poly)
    result = gf_multiply_modular(k, inverse, poly, 32)
    return result

def compute_crc32(data: bytes):
    # Standard CRC32 (IEEE)
    return binascii.crc32(data) & 0xFFFFFFFF

def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

def manipulate_crc(original_path, modified_path, enable_padding=False):
    with open(original_path, "rb") as f:
        original_data = f.read()
    with open(modified_path, "rb") as f:
        modified_data = f.read()

    original_crc = compute_crc32(original_data)
    
    padding_bytes = b'\x08\x08\x08\x08' if enable_padding else b''
    modified_crc = compute_crc32(modified_data + padding_bytes + b'\x00\x00\x00\x00')

    original_bytes = u32_to_bytes_be(original_crc)
    modified_bytes = u32_to_bytes_be(modified_crc)

    xor_result = xor_bytes(original_bytes, modified_bytes)
    reversed_bytes = reverse_bits_in_bytes(xor_result)
    k = bytes_to_u32_be(reversed_bytes)

    crc32_poly = 0x104C11DB7

    correction_value = gf_inverse(k, crc32_poly)
    correction_bytes_raw = u32_to_bytes_be(correction_value)

    def reverse_byte_bits(byte):
        return int('{:08b}'.format(byte)[::-1], 2)
    correction_bytes = bytes(reverse_byte_bits(b) for b in correction_bytes_raw)

    if enable_padding:
        final_data = modified_data + padding_bytes + correction_bytes
    else:
        final_data = modified_data + correction_bytes

    final_crc = compute_crc32(final_data)
    is_crc_match = (final_crc == original_crc)

    if is_crc_match:
        with open(modified_path, "wb") as f:
            f.write(final_data)

    return is_crc_match

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

        # MODIFIED: Use the robust loader, although this mode is less likely to need it.
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

def process_mod_update(old_mod_path_str: str, game_resource_dir_str: str, working_dir_str: str, enable_padding: bool, log):
    """
    自动化Mod更新流程：
    1. 根据旧版mod文件名，在游戏资源目录中寻找新版对应文件。
    2. 创建一个工作目录。
    3. 执行 B2B 替换，生成一个未修正CRC的中间文件。
    4. 对中间文件进行 CRC 修正。
    5. 将最终文件重命名为新版文件名，保存在工作目录中。
    """
    try:
        log("🚀 开始一键更新流程...")
        old_mod_path = Path(old_mod_path_str)
        game_resource_dir = Path(game_resource_dir_str)
        base_working_dir = Path(working_dir_str)

        # --- 1. 解析文件名并创建工作目录 ---
        log(f"分析旧版Mod文件: {old_mod_path.name}")
        match = re.search(r'(ch\d+)', old_mod_path.name)
        if not match:
            return False, "无法从旧版Mod文件名中解析出角色ID (例如 'ch0225')。"
        
        char_id = match.group(1)
        work_dir = base_working_dir / f"{char_id}_update_{Path(old_mod_path.name).stem[-4:]}"
        work_dir.mkdir(parents=True, exist_ok=True)
        log(f"已创建工作目录: {work_dir}")

        # --- 2. 寻找新版对应文件 ---
        log(f"正在 '{game_resource_dir.name}' 目录中寻找新版文件...")
        try:
            prefix_end_str = '_mxdependency-'
            prefix_end_index = old_mod_path.name.index(prefix_end_str) + len(prefix_end_str)
            search_prefix = old_mod_path.name[:prefix_end_index]
            log(f"  > 使用文件名前缀进行匹配: '{search_prefix}...'")
        except ValueError:
            return False, f"无法在旧文件名中找到关键部分 '{prefix_end_str}'，无法进行匹配。"

        candidates = [f for f in game_resource_dir.iterdir() if f.is_file() and f.name.startswith(search_prefix)]

        if not candidates:
            return False, f"在游戏资源目录中未找到任何与 '{search_prefix}' 匹配的新版文件。"

        log(f"  > 找到 {len(candidates)} 个候选文件。正在验证内容...")

        # --- 3. 验证候选文件，找到包含匹配Texture2D的那个 ---
        log("  > 正在加载旧版Mod以获取贴图列表...")
        old_env = load_bundle(str(old_mod_path), log)
        if not old_env:
            return False, "加载旧版Mod文件失败。"
        
        old_texture_names = {
            obj.read().m_Name for obj in old_env.objects if obj.type.name == "Texture2D"
        }
        if not old_texture_names:
            return False, "旧版Mod文件中不包含任何 Texture2D 资源。"
        log(f"  > 旧版Mod包含 {len(old_texture_names)} 个贴图资源。")

        new_bundle_path = None
        for candidate_path in candidates:
            log(f"    - 正在检查: {candidate_path.name}")
            env = load_bundle(str(candidate_path), lambda msg: None) # 使用静默加载避免日志混乱
            if not env:
                continue
            
            found_match = False
            for obj in env.objects:
                if obj.type.name == "Texture2D":
                    if obj.read().m_Name in old_texture_names:
                        found_match = True
                        break
            if found_match:
                new_bundle_path = candidate_path
                break
        
        if not new_bundle_path:
            return False, "在所有候选文件中都未找到与旧版Mod贴图名称匹配的资源。无法确定正确的新版文件。"
        
        log(f"✅ 成功确定新版文件: {new_bundle_path.name}")

        # --- 4. 执行 B2B 替换 ---
        log("\n--- 阶段 1: Bundle-to-Bundle 替换 ---")
        new_env = load_bundle(str(new_bundle_path), log)
        old_textures_map = {name: data.image for name, data in zip(old_texture_names, old_env.objects) if data.type.name == "Texture2D"}

        replacement_count = 0
        for obj in new_env.objects:
            if obj.type.name == "Texture2D":
                new_data = obj.read()
                if new_data.m_Name in old_textures_map:
                    new_data.image = old_textures_map[new_data.m_Name]
                    new_data.save()
                    replacement_count += 1
        
        log(f"  > B2B 替换完成，共处理 {replacement_count} 个贴图。")

        intermediate_path = work_dir / f"uncrc_{new_bundle_path.name}"
        log(f"  > 正在保存未修正CRC的中间文件到: {intermediate_path.name}")
        with open(intermediate_path, "wb") as f:
            f.write(new_env.file.save(packer="lzma"))
        log("  > 中间文件保存成功。")

        # --- 5. 执行 CRC 修正 ---
        log("\n--- 阶段 2: CRC 修正 ---")
        log(f"  > 原始文件 (用于CRC校验): {new_bundle_path.name}")
        log(f"  > 待修正文件: {intermediate_path.name}")

        is_crc_success = manipulate_crc(str(new_bundle_path), str(intermediate_path), enable_padding)

        if not is_crc_success:
            return False, f"CRC 修正失败。中间文件 '{intermediate_path.name}' 可能未被正确修改。"
        
        log("✅ CRC 修正成功！")

        # --- 6. 重命名最终文件 ---
        final_path = work_dir / new_bundle_path.name
        shutil.move(intermediate_path, final_path)
        log(f"\n🎉 全部流程处理完成！")
        log(f"最终文件已保存至: {final_path}")

        return True, f"一键更新成功！\n\n最终文件保存在工作目录中:\n{final_path}"

    except Exception as e:
        log(f"\n❌ 严重错误: 在一键更新流程中发生错误: {e}")
        log(traceback.format_exc())
        return False, f"处理过程中发生严重错误:\n{e}"