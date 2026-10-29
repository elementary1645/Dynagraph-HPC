"""Independent bounded ELF64 images; never executed or dynamically loaded."""
import struct


def add_load(evidence, address, memsz, filesz=0, offset=0, flags=6):
    table=bytes.fromhex(evidence['program_headers'])
    rows=[table[i:i+56] for i in range(0,len(table),56)]
    index=next((i for i,row in enumerate(rows) if struct.unpack_from('<I',row)[0]==1 and
                struct.unpack_from('<Q',row,16)[0]>address),len(rows))
    rows.insert(index,struct.pack('<IIQQQQQQ',1,flags,offset,address,0,filesz,memsz,4096))
    evidence['program_headers']=b''.join(rows).hex();patch_hex(evidence,'header',56,'<H',len(rows))


def harden_case(evidence, case):
    """Audit mutations, independent of the production ELF parser."""
    rows=[bytearray.fromhex(evidence['program_headers'])[i:i+56]
          for i in range(0,len(bytes.fromhex(evidence['program_headers'])),56)]
    if case=='alignment':
        for row in rows:
            if struct.unpack_from('<I',row)[0]==1:
                struct.pack_into('<Q',row,48,0x200000)
                break
    elif case=='zero-fill':
        index=next(i for i,row in enumerate(rows) if struct.unpack_from('<II',row)==(1,5))
        address=struct.unpack_from('<Q',rows[index],16)[0]+0x1000
        rows.insert(index+1,bytearray(struct.pack('<IIQQQQQQ',1,6,0,address,0,0,0x1000,0x1000)))
    else:raise ValueError('unknown audit case')
    evidence['program_headers']=b''.join(rows).hex()
    patch_hex(evidence,'header',56,'<H',len(rows))


def modified_runtime_file(value, case, directory):
    """Write actual mutated bytes; refresh hash and stat without tested parsing."""
    import copy
    import hashlib
    import os
    from pathlib import Path
    value=copy.deepcopy(value);evidence=value['elf'];raw=bytearray(Path(value['path']).read_bytes())
    harden_case(evidence,case)
    header=bytes.fromhex(evidence['header']);table=bytes.fromhex(evidence['program_headers'])
    offset=int.from_bytes(header[32:40],'little');raw[:64]=header;raw[offset:offset+len(table)]=table
    path=Path(directory)/'libgomp.so.1';path.write_bytes(raw);info=path.stat()
    value['path']=str(path);value['sha256']=hashlib.sha256(raw).hexdigest()
    value['file_identity']=dict(device_major=os.major(info.st_dev),device_minor=os.minor(info.st_dev),
        inode=info.st_ino,size=info.st_size,mtime_ns=info.st_mtime_ns)
    mapped=[]
    for line in value['mappings']:
        parts=line.split(None,5);parts[3]=f'{os.major(info.st_dev):x}:{os.minor(info.st_dev):x}'
        parts[4]=str(info.st_ino);parts[5]=str(path);mapped.append(' '.join(parts))
    value['mappings']=mapped
    return value,path


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
