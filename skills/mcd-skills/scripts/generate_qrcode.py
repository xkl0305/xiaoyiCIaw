#!/usr/bin/env python3
"""
生成二维码 PNG 图片（纯标准库实现，零第三方依赖）

使用方式:
  python generate_qrcode.py <url> [output_path]

示例:
  python generate_qrcode.py "https://m.mcd.cn/mcp/jumpToApp?orderId=123456" /tmp/mcd_pay_qr.png
"""

import sys
import os
import struct
import zlib

# ===== GF(256) 运算（Reed-Solomon 纠错）=====

GF_EXP = [0] * 512
GF_LOG = [0] * 256


def _init_gf():
    x = 1
    for i in range(255):
        GF_EXP[i] = x
        GF_LOG[x] = i
        x <<= 1
        if x & 256:
            x ^= 0x11d
    for i in range(255, 512):
        GF_EXP[i] = GF_EXP[i - 255]


_init_gf()


def gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return GF_EXP[GF_LOG[a] + GF_LOG[b]]


def gf_poly_mul(p, q):
    r = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            r[i + j] ^= gf_mul(a, b)
    return r


def rs_generator(nsym):
    g = [1]
    for i in range(nsym):
        g = gf_poly_mul(g, [1, GF_EXP[i]])
    return g


def rs_encode(data, nsym):
    gen = rs_generator(nsym)
    msg = list(data) + [0] * nsym
    for i in range(len(data)):
        coef = msg[i]
        if coef != 0:
            for j in range(len(gen)):
                msg[i + j] ^= gf_mul(gen[j], coef)
    return msg[len(data):]


# ===== QR 版本信息（纠错等级 M）=====
# (total_data_codewords, ec_codewords_per_block, num_blocks)
VERSION_INFO = {
    1: (16, 10, 1),
    2: (28, 16, 1),
    3: (44, 26, 1),
    4: (64, 18, 2),
    5: (86, 24, 2),
    6: (108, 16, 4),
    7: (124, 18, 4),
    8: (154, 22, 4),
    9: (182, 22, 5),
    10: (216, 26, 5),
}

ALIGNMENT_POSITIONS = {
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 52],
}


def get_version_for_data(data_len):
    for ver in range(1, 11):
        total_data, _, _ = VERSION_INFO[ver]
        char_count_bits = 8 if ver < 10 else 16
        available_bits = total_data * 8
        needed_bits = 4 + char_count_bits + data_len * 8
        if needed_bits <= available_bits:
            return ver
    return None


def encode_data(data_bytes, version):
    total_data, ec_per_block, num_blocks = VERSION_INFO[version]
    char_count_bits = 8 if version < 10 else 16

    bits = []
    # Mode indicator: byte mode = 0100
    bits.extend([0, 1, 0, 0])
    # Character count
    for i in range(char_count_bits - 1, -1, -1):
        bits.append((len(data_bytes) >> i) & 1)
    # Data
    for byte in data_bytes:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    # Terminator
    bits.extend([0] * min(4, total_data * 8 - len(bits)))
    # Pad to byte boundary
    while len(bits) % 8 != 0:
        bits.append(0)
    # Pad codewords
    pad_bytes = [0xEC, 0x11]
    pad_idx = 0
    while len(bits) < total_data * 8:
        for b in range(7, -1, -1):
            bits.append((pad_bytes[pad_idx % 2] >> b) & 1)
        pad_idx += 1

    # Convert to codewords
    codewords = []
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        codewords.append(byte)

    # Split into blocks and compute EC
    data_per_block = total_data // num_blocks
    remainder = total_data % num_blocks
    blocks_data = []
    blocks_ec = []
    offset = 0
    for i in range(num_blocks):
        block_size = data_per_block + (1 if i >= num_blocks - remainder else 0)
        block = codewords[offset:offset + block_size]
        blocks_data.append(block)
        blocks_ec.append(rs_encode(block, ec_per_block))
        offset += block_size

    # Interleave
    result = []
    max_data = max(len(b) for b in blocks_data)
    for i in range(max_data):
        for block in blocks_data:
            if i < len(block):
                result.append(block[i])
    for i in range(ec_per_block):
        for block in blocks_ec:
            if i < len(block):
                result.append(block[i])

    return result


def make_qr_matrix(version, codewords):
    size = 17 + version * 4
    matrix = [[None] * size for _ in range(size)]
    reserved = [[False] * size for _ in range(size)]

    def set_module(row, col, val):
        if 0 <= row < size and 0 <= col < size:
            matrix[row][col] = val
            reserved[row][col] = True

    def place_finder(top, left):
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = top + r, left + c
                if 0 <= rr < size and 0 <= cc < size:
                    if 0 <= r <= 6 and 0 <= c <= 6:
                        if (r in (0, 6) or c in (0, 6) or
                                (2 <= r <= 4 and 2 <= c <= 4)):
                            set_module(rr, cc, True)
                        else:
                            set_module(rr, cc, False)
                    else:
                        set_module(rr, cc, False)

    place_finder(0, 0)
    place_finder(0, size - 7)
    place_finder(size - 7, 0)

    if version in ALIGNMENT_POSITIONS:
        positions = ALIGNMENT_POSITIONS[version]
        for row in positions:
            for col in positions:
                if reserved[row][col]:
                    continue
                for r in range(-2, 3):
                    for c in range(-2, 3):
                        if abs(r) == 2 or abs(c) == 2 or (r == 0 and c == 0):
                            set_module(row + r, col + c, True)
                        else:
                            set_module(row + r, col + c, False)

    for i in range(size):
        if not reserved[6][i]:
            set_module(6, i, i % 2 == 0)
        if not reserved[i][6]:
            set_module(i, 6, i % 2 == 0)

    for i in range(9):
        if not reserved[8][i]:
            reserved[8][i] = True
            matrix[8][i] = False
        if not reserved[i][8]:
            reserved[i][8] = True
            matrix[i][8] = False
    for i in range(8):
        if not reserved[8][size - 1 - i]:
            reserved[8][size - 1 - i] = True
            matrix[8][size - 1 - i] = False
        if not reserved[size - 1 - i][8]:
            reserved[size - 1 - i][8] = True
            matrix[size - 1 - i][8] = False

    set_module(size - 8, 8, True)

    bit_idx = 0
    total_bits = len(codewords) * 8
    col = size - 1
    going_up = True

    while col >= 0:
        if col == 6:
            col -= 1
            continue
        rows_range = range(size - 1, -1, -1) if going_up else range(size)
        for row in rows_range:
            for dc in (0, -1):
                c = col + dc
                if c < 0 or reserved[row][c]:
                    continue
                if bit_idx < total_bits:
                    byte_idx = bit_idx // 8
                    bit_pos = 7 - (bit_idx % 8)
                    matrix[row][c] = bool((codewords[byte_idx] >> bit_pos) & 1)
                else:
                    matrix[row][c] = False
                bit_idx += 1
        col -= 2
        going_up = not going_up

    for row in range(size):
        for col_idx in range(size):
            if not reserved[row][col_idx] and matrix[row][col_idx] is not None:
                if (row + col_idx) % 2 == 0:
                    matrix[row][col_idx] = not matrix[row][col_idx]

    format_bits = 0b101010000010010
    positions_h = [
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)
    ]
    positions_v = [
        (size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8),
        (size - 5, 8), (size - 6, 8), (size - 7, 8),
        (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5),
        (8, size - 4), (8, size - 3), (8, size - 2), (8, size - 1)
    ]

    for i in range(15):
        bit = bool((format_bits >> (14 - i)) & 1)
        r, c = positions_h[i]
        matrix[r][c] = bit
        r, c = positions_v[i]
        matrix[r][c] = bit

    return matrix


def matrix_to_png(matrix, scale=10, border=4):
    size = len(matrix)
    img_size = (size + border * 2) * scale

    raw = bytearray()
    for y in range(img_size):
        raw.append(0)
        for x in range(img_size):
            mx = x // scale - border
            my = y // scale - border
            if 0 <= mx < size and 0 <= my < size and matrix[my][mx]:
                raw.append(0)
            else:
                raw.append(255)

    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk) & 0xffffffff)
        return struct.pack('>I', len(data)) + chunk + crc

    png = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', img_size, img_size, 8, 0, 0, 0, 0)
    png += png_chunk(b'IHDR', ihdr_data)
    compressed = zlib.compress(bytes(raw))
    png += png_chunk(b'IDAT', compressed)
    png += png_chunk(b'IEND', b'')

    return png


def matrix_to_terminal(matrix, border=2):
    size = len(matrix)
    total = size + border * 2
    lines = []
    for y in range(0, total, 2):
        line = []
        for x in range(total):
            mx = x - border
            my_top = y - border
            my_bot = y + 1 - border
            top = (0 <= mx < size and 0 <= my_top < size and matrix[my_top][mx])
            bot = (0 <= mx < size and 0 <= my_bot < size and matrix[my_bot][mx])
            if top and bot:
                line.append('█')
            elif top and not bot:
                line.append('▀')
            elif not top and bot:
                line.append('▄')
            else:
                line.append(' ')
        lines.append(''.join(line))
    return '\n'.join(lines)


def generate_qrcode(url, output_path="/tmp/mcd_pay_qr.png"):
    data_bytes = url.encode('utf-8')
    version = get_version_for_data(len(data_bytes))
    if version is None:
        print("错误：数据过长，超出支持的 QR 版本范围", file=sys.stderr)
        sys.exit(1)

    codewords = encode_data(data_bytes, version)
    matrix = make_qr_matrix(version, codewords)
    png_data = matrix_to_png(matrix)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(png_data)

    print(output_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <url> [output_path|--terminal]", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    if "--terminal" in sys.argv:
        data_bytes = url.encode('utf-8')
        version = get_version_for_data(len(data_bytes))
        if version is None:
            print("错误：数据过长", file=sys.stderr)
            sys.exit(1)
        codewords = encode_data(data_bytes, version)
        matrix = make_qr_matrix(version, codewords)
        print(matrix_to_terminal(matrix))
    else:
        output = sys.argv[2] if len(sys.argv) > 2 else "/tmp/mcd_pay_qr.png"
        generate_qrcode(url, output)
