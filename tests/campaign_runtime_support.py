"""Independent bounded ELF64 images; never executed or dynamically loaded."""
import struct


def patch_hex(evidence, key, offset, fmt, value):
    raw=bytearray.fromhex(evidence[key])
    struct.pack_into(fmt,raw,offset,value)
    evidence[key]=raw.hex()


def elf_bytes(executable=False):
    image=bytearray(0x3800)
    def ph(kind,flags,offset,vaddr,filesz,memsz,align):
        return struct.pack('<IIQQQQQQ',kind,flags,offset,vaddr,0,filesz,memsz,align)
    interpreter=b'/lib64/ld-linux-x86-64.so.2\0' if executable else b''
    rows=([ph(3,4,0x300,0x300,len(interpreter),len(interpreter),1)] if executable else [])
    rows += [ph(1,5,0,0,0x2000,0x2000,0x1000),
             ph(1,6,0x2000,0x5000,0x1800,0x2800,0x1000),
             ph(2,4,0x400,0x400,64,64,8),
             ph(0x6474e552,4,0x2000,0x5000,0x1000,0x1000,1)]
    ident=b'\x7fELF\x02\x01\x01'+b'\0'*9
    image[:64]=ident+struct.pack('<HHIQQQIHHHHHH',3,62,1,0x1000 if executable else 0,
                                64,0,0,64,56,len(rows),0,0,0)
    image[64:64+len(rows)*56]=b''.join(rows)
    image[0x300:0x300+len(interpreter)]=interpreter
    strings=b'\0libgomp.so.1\0'
    image[0x800:0x800+len(strings)]=strings
    image[0x400:0x440]=b''.join(struct.pack('<qQ',tag,val) for tag,val in
                              [(5,0x800),(10,len(strings)),(1 if executable else 14,1),(0,0)])
    return bytes(image)


def elf_evidence(executable=False):
    raw=elf_bytes(executable)
    count=5 if executable else 4
    return dict(file_size=len(raw),header=raw[:64].hex(),program_headers=raw[64:64+count*56].hex(),
                dynamic=raw[0x400:0x440].hex(),strings=raw[0x800:0x80e].hex(),
                interpreter=raw[0x300:0x31c].hex() if executable else '')
