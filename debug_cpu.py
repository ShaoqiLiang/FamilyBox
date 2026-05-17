"""Debug CPU execution at 0x90DE."""
from familybox.nes import NES

nes = NES('rom/super-mario-bros.nes', headless=True)
nes.reset()
for _ in range(2):
    nes._run_frame()

# 0x90D8-0x90EC 反汇编
print('0x90D8-0x90EC 代码:')
for addr in range(0x90D8, 0x90F0):
    val = nes._cpu._bus.read(addr)
    print(f'  0x{addr:04X}: 0x{val:02X}')

# 追踪执行
print('\n执行追踪 (20条指令):')
for i in range(20):
    pc = nes._cpu._regs.pc
    op = nes._cpu._bus.read(pc)
    op2 = nes._cpu._bus.read(pc+1) if pc < 0xFFFF else 0
    op3 = nes._cpu._bus.read(pc+2) if pc < 0xFFFE else 0
    
    addr = op2 | (op3 << 8)
    
    if op == 0xAD:  # LDA abs
        val = nes._cpu._bus.read(addr)
        print(f'  0x{pc:04X}: LDA ${addr:04X} = 0x{val:02X} (A=0x{nes._cpu._regs.a:02X})')
    elif op == 0x10:  # BPL
        target = pc + 2 + (op2 if op2 < 128 else op2 - 256)
        print(f'  0x{pc:04X}: BPL ${target:04X}  (P=0x{nes._cpu._regs.p:02X}, N={(nes._cpu._regs.p>>7)&1})')
    elif op == 0x30:  # BMI
        target = pc + 2 + (op2 if op2 < 128 else op2 - 256)
        print(f'  0x{pc:04X}: BMI ${target:04X}  (P=0x{nes._cpu._regs.p:02X}, N={(nes._cpu._regs.p>>7)&1})')
    elif op == 0xD0:  # BNE
        target = pc + 2 + (op2 if op2 < 128 else op2 - 256)
        print(f'  0x{pc:04X}: BNE ${target:04X}  (P=0x{nes._cpu._regs.p:02X}, Z={(nes._cpu._regs.p>>1)&1})')
    elif op == 0xCE:  # DEC abs
        print(f'  0x{pc:04X}: DEC ${addr:04X}')
    elif op == 0xEE:  # INC abs
        print(f'  0x{pc:04X}: INC ${addr:04X}')
    elif op == 0x20:  # JSR
        print(f'  0x{pc:04X}: JSR ${addr:04X}')
    elif op == 0x4C:  # JMP
        print(f'  0x{pc:04X}: JMP ${addr:04X}')
    elif op == 0xA9:  # LDA imm
        print(f'  0x{pc:04X}: LDA #0x{op2:02X}')
    elif op == 0xA5:  # LDA zp
        print(f'  0x{pc:04X}: LDA \${op2:02X}')
    elif op == 0x85:  # STA zp
        print(f'  0x{pc:04X}: STA \${op2:02X}')
    elif op == 0x8D:  # STA abs
        print(f'  0x{pc:04X}: STA ${addr:04X}')
    elif op == 0xC9:  # CMP imm
        print(f'  0x{pc:04X}: CMP #0x{op2:02X}')
    elif op == 0xE0:  # CPX imm
        print(f'  0x{pc:04X}: CPX #0x{op2:02X}')
    elif op == 0x60:  # RTS
        print(f'  0x{pc:04X}: RTS')
    elif op == 0x88:  # DEY
        print(f'  0x{pc:04X}: DEY (Y=0x{nes._cpu._regs.y:02X})')
    elif op == 0xC8:  # INY
        print(f'  0x{pc:04X}: INY (Y=0x{nes._cpu._regs.y:02X})')
    elif op == 0xCA:  # DEX
        print(f'  0x{pc:04X}: DEX (X=0x{nes._cpu._regs.x:02X})')
    else:
        print(f'  0x{pc:04X}: op=0x{op:02X} (A=0x{nes._cpu._regs.a:02X} X=0x{nes._cpu._regs.x:02X} Y=0x{nes._cpu._regs.y:02X})')
    
    nes._cpu.tick()