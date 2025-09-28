# utils.py

import tkinter as tk
import binascii

class CRCUtils:
    """
    一个封装了CRC32计算和修正逻辑的工具类。
    所有复杂的位运算和GF(2^32)算法都作为私有静态方法实现。
    """

    # --- 公开的静态方法 ---

    @staticmethod
    def compute_crc32(data: bytes) -> int:
        """
        计算数据的标准CRC32 (IEEE)值。
        """
        return binascii.crc32(data) & 0xFFFFFFFF

    @staticmethod
    def check_crc_match(original_path: str, modified_path: str) -> bool:
        """
        检测两个文件的CRC值是否匹配。
        返回True表示CRC值一致，False表示不一致。
        """
        with open(original_path, "rb") as f:
            original_data = f.read()
        with open(modified_path, "rb") as f:
            modified_data = f.read()

        original_crc = CRCUtils.compute_crc32(original_data)
        modified_crc = CRCUtils.compute_crc32(modified_data)
        
        return original_crc == modified_crc
    @staticmethod
    def manipulate_crc(original_path: str, modified_path: str, enable_padding: bool = False) -> bool:
        """
        修正修改后文件的CRC，使其与原始文件匹配。
        此方法处理文件的读写操作。
        """
        with open(original_path, "rb") as f:
            original_data = f.read()
        with open(modified_path, "rb") as f:
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


class Logger:
    def __init__(self, master, log_widget: tk.Text, status_widget: tk.Label):
        self.master = master
        self.log_widget = log_widget
        self.status_widget = status_widget

    def log(self, message):
        """线程安全地向日志区域添加消息"""
        def _update_log():
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.insert(tk.END, message + "\n")
            self.log_widget.see(tk.END)
            self.log_widget.config(state=tk.DISABLED)
        
        self.master.after(0, _update_log)

    def status(self, message):
        """线程安全地更新状态栏消息"""
        def _update_status():
            self.status_widget.config(text=f"状态：{message}")
        
        self.master.after(0, _update_status)

    def clear(self):
        """清空日志区域"""
        def _clear_log():
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.delete('1.0', tk.END)
            self.log_widget.config(state=tk.DISABLED)
        
        self.master.after(0, _clear_log)