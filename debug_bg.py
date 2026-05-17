"""Debug background rendering."""
from familybox.nes import NES
import os

nes = NES('rom/super-mario-bros.nes', headless=True)
nes.reset()
for f in range(40):
    nes._run_frame()

# 检查 nametable 中是否有非零数据
nt = nes._ppu_bus._nametable
non_zero = sum(1 for b in nt if b != 0)
print(f'Nametable 非零字节: {non_zero}/{len(nt)}')

# 前 64 字节
print('前 64 字节:')
for i in range(4):
    for j in range(16):
        print(f'{nt[i*16+j]:02X} ', end='')
    print()

# 同时检查 Python 渲染器的输出
os.environ['FAMILYBOX_NO_FAST_RENDERER'] = '1'
from familybox.ppu.renderer import Renderer
py_r = Renderer(nes._ppu)

# 手动渲染第 100 行（游戏区域）
for x in range(256):
    py_r.render_pixel(x, 100)
py_fb = py_r.get_framebuffer()

# 对比第 100 行的颜色
fast_fb_bytes = nes._ppu._renderer.get_framebuffer_bytes()
print()
print('第 100 行前 16 像素对比:')
for x in range(16):
    py_color = py_fb[100*256+x]
    off = (100*256+x)*3
    c_color = (fast_fb_bytes[off]<<16) | (fast_fb_bytes[off+1]<<8) | fast_fb_bytes[off+2]
    match = "相同" if py_color==c_color else "不同"
    print(f'  x={x:3d}: Python=0x{py_color:06X}  C=0x{c_color:06X}  {match}')