from pyx64dbg import Debugger
import random

dbg = Debugger.start_and_debug("/bin/ls")
print("[+] Entry address:", hex(dbg.registers.rip))
# /bin/ls uses fwrite_unlocked to print its output
write_address = dbg.shared_objects["libc.so.6"].symbols.fwrite_unlocked
dbg.breakpoints.add_breakpoint(write_address)
dbg.control.continue_execution()
while not dbg.process_exited:
    print("[+] RIP:", hex(dbg.registers.rip))

    print("[+] RDI (first argument to fwrite_unlocked):", hex(dbg.registers.rdi))
    print("[+] String at RDI:", dbg.memory.read_c_string(dbg.registers.rdi))

    rdx = dbg.registers.rdx
    print("[+] RDX (length argument to fwrite_unlocked):", rdx)

    replacement = bytes(random.choices(b"0123456789", k=int(rdx)))
    dbg.memory.write_bytes(dbg.registers.rdi, replacement)
    print("[+] Replaced string with:", replacement.decode())
    print()
    dbg.control.continue_execution()

print("[+] Process exited with code", dbg.exit_code)
print("[+] All outputs from program:")
print(dbg.stdio.recvall().decode())