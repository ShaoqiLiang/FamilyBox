"""Save and analyze a frame from the emulator."""
from familybox.nes import NES
from collections import Counter

nes = NES('rom/super-mario-bros.nes', headless=True)
nes.reset()

# 跑够帧数让渲染开启（30帧）
for f in range(30):
    nes._run_frame()

# 保存一帧画面
renderer = nes._ppu._renderer
pixels = renderer.get_framebuffer_bytes()

# 写 PPM 文件
with open('test_frame.ppm', 'wb') as f:
    f.write(b'P6\n256 240\n255\n')
    f.write(pixels)

print(f'Frame saved: test_frame.ppm ({len(pixels)} bytes)')
print(f'PPU frame: {nes._ppu._frame}')
print(f'show_bg: {nes._ppu._mask.show_bg}')
print(f'show_sprites: {nes._ppu._mask.show_sprites}')

# 分析画面
data = pixels
pix_list = [data[i:i+3] for i in range(0, len(data), 3)]
unique = len(set(pix_list))
counter = Counter(pix_list)
print(f'唯一颜色数: {unique}')
print('前10最常见颜色:')
for rgb, cnt in counter.most_common(10):
    print(f'  RGB({rgb[0]:3d},{rgb[1]:3d},{rgb[2]:3d}) = {cnt:6d} 像素')

black_key = bytes([0, 0, 0])
print(f'黑色像素: {counter.get(black_key, 0)}')