# utils.py

import binascii
import os
import re
from pathlib import Path

def no_log(message):
    """A dummy logger that does nothing."""
    pass

class CRCUtils:
    """
    一个封装了CRC32计算和修正逻辑的工具类。
    """

    # --- 公开的静态方法 ---

    @staticmethod
    def compute_crc32(data: bytes) -> int:
        """
        计算数据的标准CRC32 (IEEE)值。
        """
        return binascii.crc32(data) & 0xFFFFFFFF

    @staticmethod
    def check_crc_match(file_1: Path, file_2: Path) -> bool:
        """
        检测两个文件的CRC值是否匹配。
        返回True表示CRC值一致，False表示不一致。
        """
        with open(str(file_1), "rb") as f:
            data_1 = f.read()
        with open(str(file_2), "rb") as f:
            data_2 = f.read()

        crc_1 = CRCUtils.compute_crc32(data_1)
        crc_2 = CRCUtils.compute_crc32(data_2)
        
        return crc_1 == crc_2
    
    @staticmethod
    def manipulate_crc(original_path: Path, modified_path: Path, enable_padding: bool = False) -> bool:
        """
        修正修改后文件的CRC，使其与原始文件匹配。
        此方法处理文件的读写操作。
        """
        with open(str(original_path), "rb") as f:
            original_data = f.read()
        with open(str(modified_path), "rb") as f:
            modified_data = f.read()

        original_crc = CRCUtils.compute_crc32(original_data)
        
        padding_bytes = b'\x08\x08\x08\x08' if enable_padding else b''
        # 计算新数据加上4个空字节的CRC，为修正值留出空间
        modified_crc = CRCUtils.compute_crc32(modified_data + padding_bytes + b'\x00\x00\x00\x00')

        original_bytes = CRCUtils._u32_to_bytes_be(original_crc)
        modified_bytes = CRCUtils._u32_to_bytes_be(modified_crc)

        xor_result = CRCUtils._xor_bytes(original_bytes, modified_bytes)
        reversed_bytes = CRCUtils._reverse_bits_in_bytes(xor_result)
        k = CRCUtils._bytes_to_u32_be(reversed_bytes)

        # CRC32多项式: x^32 + x^26 + ... + 1
        crc32_poly = 0x104C11DB7

        correction_value = CRCUtils._gf_inverse(k, crc32_poly)
        correction_bytes_raw = CRCUtils._u32_to_bytes_be(correction_value)

        # 反转每个字节内的位
        correction_bytes = bytes(CRCUtils._reverse_byte_bits(b) for b in correction_bytes_raw)

        if enable_padding:
            final_data = modified_data + padding_bytes + correction_bytes
        else:
            final_data = modified_data + correction_bytes

        final_crc = CRCUtils.compute_crc32(final_data)
        is_crc_match = (final_crc == original_crc)

        if is_crc_match:
            with open(modified_path, "wb") as f:
                f.write(final_data)

        return is_crc_match

    # --- 内部使用的私有静态方法 ---

    @staticmethod
    def _bytes_to_u32_be(b):
        return int.from_bytes(b, 'big')

    @staticmethod
    def _u32_to_bytes_be(i):
        return i.to_bytes(4, 'big')

    @staticmethod
    def _reverse_bits_in_bytes(b):
        num = CRCUtils._bytes_to_u32_be(b)
        rev = 0
        for i in range(32):
            if (num >> i) & 1:
                rev |= 1 << (31 - i)
        return CRCUtils._u32_to_bytes_be(rev)

    @staticmethod
    def _gf_multiply(a, b):
        result = 0
        while b:
            if b & 1:
                result ^= a
            a <<= 1
            b >>= 1
        return result

    @staticmethod
    def _gf_divide(dividend, divisor):
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

    @staticmethod
    def _gf_mod(dividend, divisor, n):
        if divisor == 0:
            return dividend
        while dividend != 0 and dividend.bit_length() >= divisor.bit_length():
            shift = dividend.bit_length() - divisor.bit_length()
            dividend ^= divisor << shift
        mask = (1 << n) - 1 if n < 64 else 0xFFFFFFFFFFFFFFFF
        return dividend & mask

    @staticmethod
    def _gf_multiply_modular(a, b, modulus, n):
        product = CRCUtils._gf_multiply(a, b)
        return CRCUtils._gf_mod(product, modulus, n)

    @staticmethod
    def _gf_modular_inverse(a, m):
        if a == 0:
            raise ValueError("Inverse of zero does not exist")
        old_r, r = m, a
        old_s, s = 0, 1
        while r != 0:
            q = CRCUtils._gf_divide(old_r, r)
            old_r, r = r, old_r ^ CRCUtils._gf_multiply(q, r)
            old_s, s = s, old_s ^ CRCUtils._gf_multiply(q, s)
        if old_r != 1:
            raise ValueError("Modular inverse does not exist")
        return old_s

    @staticmethod
    def _gf_inverse(k, poly):
        x32 = 0x100000000
        inverse = CRCUtils._gf_modular_inverse(x32, poly)
        result = CRCUtils._gf_multiply_modular(k, inverse, poly, 32)
        return result

    @staticmethod
    def _xor_bytes(a: bytes, b: bytes) -> bytes:
        return bytes(x ^ y for x, y in zip(a, b))

    @staticmethod
    def _reverse_byte_bits(byte):
        return int('{:08b}'.format(byte)[::-1], 2)

def get_environment_info():
    """Collects and formats key environment details."""
    
    # --- Attempt to import libraries and get their versions ---
    # This approach prevents the script from crashing if a library is not installed.

    try:
        import UnityPy
        unitypy_version = UnityPy.__version__
    except ImportError:
        unitypy_version = "Not installed"
    try:
        from PIL import Image
        pillow_version = Image.__version__
    except ImportError:
        pillow_version = "Not installed"
    try:
        import tkinter
        tk_version = tkinter.Tcl().eval('info patchlevel')
    except (ImportError, tkinter.TclError):
        tk_version = "Not available"

    import sys
    import platform
    import locale

    def _is_admin():
        if sys.platform == 'win32':
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except (ImportError, AttributeError):
                return False
        return False # 在非Windows系统上不是管理员

    # --- System Information ---
    lines = []
    lines.append("--- System Information ---")
    lines.append(f"Operating System:  {platform.system()} {platform.release()} ({platform.architecture()[0]})")
    lines.append(f"System Platform:   {sys.platform}")

    # --- Locale and Encoding Information (crucial for file path/text bugs) ---
    try:
        lang_code, encoding = locale.getdefaultlocale()
        system_locale = f"{lang_code} (Encoding: {encoding})"
    except (ValueError, TypeError):
        system_locale = "Could not determine"
    
    lines.append(f"System Locale:     {system_locale}")
    lines.append(f"Filesystem Enc:    {sys.getfilesystemencoding()}")
    lines.append(f"Preferred Enc:     {locale.getpreferredencoding()}")
    
    # --- Python Information ---
    lines.append("\n--- Python Information ---")
    lines.append(f"Python Version:    {sys.version.splitlines()[0]}")
    lines.append(f"Python Executable: {sys.executable}")
    lines.append(f"Working Directory: {Path.cwd()}")
    lines.append(f"Running as Admin:  {_is_admin()}")

    # --- Library Versions ---
    lines.append("\n--- Library Versions ---")
    lines.append(f"UnityPy Version:   {unitypy_version}")
    lines.append(f"Pillow Version:    {pillow_version}")
    lines.append(f"Tkinter Version:   {tk_version}")
    lines.append("")

    return "\n".join(lines)

def get_skel_version_from_file(filepath: Path, log = no_log) -> str | None:
    """
    通过扫描文件头部来查找Spine版本号。

    Args:
        filepath: .skel 文件的路径。

    Returns:
        一个字符串，表示Spine的版本号，例如 "4.2.33"。
        如果未找到，则返回 None。
    """
    if not filepath.exists():
        log(f"错误: 文件不存在 -> {filepath}")
        return None

    try:
        with open(str(filepath), 'rb') as f:
            # 读取文件的前256个字节。版本号几乎总是在这个范围内。
            header_chunk = f.read(256)
            return get_skel_version_from_bytes(header_chunk, log)

    except Exception as e:
        log(f"处理文件时发生错误: {e}")
        return None

def get_skel_version_from_bytes(data: bytes, log = no_log) -> str | None:
    """
    通过扫描字节数据头部来查找Spine版本号。

    Args:
        data: .skel 文件的字节数据。

    Returns:
        一个字符串，表示Spine的版本号，例如 "4.2.33"。
        如果未找到，则返回 None。
    """
    try:
        # 读取数据的前256个字节。版本号几乎总是在这个范围内。
        header_chunk = data[:256]
        header_text = header_chunk.decode('utf-8', errors='ignore')

        # 使用正则表达式查找 "数字.数字.数字" 格式的字符串。
        match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{1,2})', header_text)
        
        if match:
            version_string = match.group(1)
            return version_string
        else:
            log("未能在数据头部找到Spine版本号模式")
            return None

    except Exception as e:
        log(f"处理字节数据时发生错误: {e}")
        return None