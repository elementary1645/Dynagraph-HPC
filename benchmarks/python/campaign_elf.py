"""Bounded ELF64 metadata and Linux mapping reconciliation, without execution.

Supported: little-endian x86-64, 4 KiB pages, direct dynamic libgomp dependency.
Raw metadata is retained for offline reparsing, not authenticated by this module.
"""
import re
import struct

from campaign_contract import fields, integer

U64 = (1 << 64) - 1
PAGE = 4096
MAX_METADATA = 65536


def add(a, b):
    integer(a, 0, U64, 'ELF arithmetic operand')
    integer(b, 0, U64, 'ELF arithmetic operand')
    if a > U64-b:
        raise ValueError('ELF/mapping arithmetic overflow')
    return a+b


def down(n):
    return n-n % PAGE


def up(n):
    return down(add(n, PAGE-1))


def bounded_range(offset, length, size):
    if add(offset, length) > size:
        raise ValueError('ELF range outside file')


def header(raw, size):
    if len(raw) != 64 or raw[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError('unsupported ELF magic/class/encoding/version')
    if raw[7] not in (0, 3) or any(raw[8:16]):
        raise ValueError('unsupported ELF ABI')
    kind, machine, version, entry, phoff, shoff, flags, ehsize, phsize, count, shsize, shcount, shnames = struct.unpack('<HHIQQQIHHHHHH', raw[16:])
    if (kind not in (2, 3) or machine != 62 or version != 1 or flags != 0 or
            ehsize != 64 or phsize != 56 or not 1 <= count <= 128 or phoff < 64):
        raise ValueError('invalid or unsupported ELF header')
    bounded_range(phoff, count*56, size)
    if shoff:
        if shsize != 64 or not 1 <= shcount < 65535 or shnames >= shcount:
            raise ValueError('unsupported ELF section header table')
        bounded_range(shoff, shcount*64, size)
    elif shcount or shnames:
        raise ValueError('contradictory ELF section header table')
    return dict(kind=kind, entry=entry, phoff=phoff, count=count)


def programs(raw, h, size):
    if len(raw) != h['count']*56:
        raise ValueError('truncated ELF program table')
    rows=[]
    for start in range(0, len(raw), 56):
        kind, flags, offset, vaddr, _, filesz, memsz, align = struct.unpack('<IIQQQQQQ', raw[start:start+56])
        if kind == 0:
            continue
        bounded_range(offset, filesz, size)
        add(vaddr, memsz)
        row=dict(kind=kind, flags=flags, offset=offset, vaddr=vaddr,
                 filesz=filesz, memsz=memsz, align=align)
        if kind == 1:
            if align > PAGE:
                raise ValueError('unsupported ELF PT_LOAD alignment')
            if (filesz > memsz or flags not in (4, 5, 6) or
                    (align not in (0, 1) and (align & (align-1) or offset % align != vaddr % align)) or
                    offset % PAGE != vaddr % PAGE):
                raise ValueError('invalid or unsupported ELF PT_LOAD')
        rows.append(row)
    loads=[r for r in rows if r['kind']==1]
    if not loads or loads != sorted(loads, key=lambda r:r['vaddr']):
        raise ValueError('missing or unordered ELF load segments')
    if not any(r['flags']==5 and r['filesz'] for r in loads):
        raise ValueError('missing executable ELF PT_LOAD')
    # Include zero-fill/BSS pages: anonymous loads can overwrite certified VMAs.
    # Conservatively reject shared memory pages instead of emulating loader order.
    spans=[(down(r['vaddr']),up(add(r['vaddr'],r['memsz']))) for r in loads if r['memsz']]
    if any(a[1]>b[0] for a,b in zip(spans,spans[1:])):
        raise ValueError('unsupported overlapping ELF load memory pages')
    if h['entry'] and not any(r['flags']==5 and r['vaddr']<=h['entry']<add(r['vaddr'],r['memsz']) for r in loads):
        raise ValueError('ELF entry outside executable segment')
    return rows


def one(rows, kind):
    found=[r for r in rows if r['kind']==kind]
    if len(found)!=1:
        raise ValueError('missing or ambiguous ELF segment')
    return found[0]


def file_offset(rows, address, length):
    end=add(address,length)
    found=[r for r in rows if r['kind']==1 and r['vaddr']<=address and end<=add(r['vaddr'],r['filesz'])]
    if len(found)!=1:
        raise ValueError('ELF metadata outside unique file-backed PT_LOAD')
    return add(found[0]['offset'],address-found[0]['vaddr'])


def dynamic(raw):
    if not raw or len(raw)>MAX_METADATA or len(raw)%16:
        raise ValueError('invalid ELF dynamic table size')
    tags={}; ended=False
    for offset in range(0,len(raw),16):
        tag,value=struct.unpack('<qQ',raw[offset:offset+16])
        if ended:
            if tag or value: raise ValueError('nonzero ELF dynamic padding')
        elif tag==0:
            if value: raise ValueError('invalid ELF DT_NULL')
            ended=True
        else:
            if tag<0: raise ValueError('unsupported ELF dynamic tag')
            tags.setdefault(tag,[]).append(value)
    if not ended: raise ValueError('unterminated ELF dynamic table')
    for tag in (5,10):
        if len(tags.get(tag,[]))!=1: raise ValueError('missing or ambiguous ELF string table')
    if not 1<=tags[10][0]<=MAX_METADATA:
        raise ValueError('ELF string table limit')
    return tags


def string_at(raw, index):
    if index>=len(raw): raise ValueError('ELF string offset outside table')
    end=raw.find(b'\0',index)
    if end<0 or end-index>4096: raise ValueError('unterminated or excessive ELF string')
    try: value=raw[index:end].decode('ascii')
    except UnicodeError as error: raise ValueError('unsupported ELF dynamic string') from error
    if not value or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('invalid ELF dynamic string')
    return value


def parse_elf(evidence):
    """Reparse closed raw metadata; do not trust extracted SONAME/segment labels."""
    fields(evidence,'file_size header program_headers dynamic strings interpreter','ELF evidence')
    size=integer(evidence['file_size'],64,(1<<63)-1,'ELF file size')
    decoded={}
    for key in ('header','program_headers','dynamic','strings','interpreter'):
        value=evidence[key]
        if type(value) is not str or len(value)>MAX_METADATA*2 or re.fullmatch(r'(?:[0-9a-f]{2})*',value) is None:
            raise ValueError('invalid bounded ELF hexadecimal evidence')
        decoded[key]=bytes.fromhex(value)
    h=header(decoded['header'],size)
    rows=programs(decoded['program_headers'],h,size)
    d=one(rows,2)
    if d['filesz']!=d['memsz'] or file_offset(rows,d['vaddr'],d['filesz'])!=d['offset']:
        raise ValueError('contradictory ELF PT_DYNAMIC')
    if len(decoded['dynamic'])!=d['filesz']:
        raise ValueError('truncated ELF dynamic evidence')
    relros=[r for r in rows if r['kind']==0x6474e552]
    if len(relros)>1:
        raise ValueError('ambiguous ELF RELRO')
    for r in relros:
        if (r['filesz']>r['memsz'] or file_offset(rows,r['vaddr'],r['filesz'])!=r['offset'] or
                not any(s['kind']==1 and s['flags']==6 and s['vaddr']<=r['vaddr'] and
                        add(r['vaddr'],r['memsz'])<=add(s['vaddr'],s['memsz']) for s in rows)):
            raise ValueError('ELF RELRO outside writable load segment')
    tags=dynamic(decoded['dynamic'])
    stroff=file_offset(rows,tags[5][0],tags[10][0])
    if len(decoded['strings'])!=tags[10][0] or decoded['strings'][0]!=0:
        raise ValueError('contradictory ELF string evidence')
    sonames=tags.get(14,[])
    if len(sonames)>1: raise ValueError('ambiguous ELF SONAME')
    needed=[string_at(decoded['strings'],v) for v in tags.get(1,[])]
    if len(needed)!=len(set(needed)): raise ValueError('duplicate ELF dependency')
    soname=string_at(decoded['strings'],sonames[0]) if sonames else None
    interps=[r for r in rows if r['kind']==3]
    chunks=[(0,decoded['header']),(h['phoff'],decoded['program_headers']),
            (d['offset'],decoded['dynamic']),(stroff,decoded['strings'])]
    interp=None
    if interps:
        i=one(rows,3);raw=decoded['interpreter']
        if not 2<=i['filesz']<=4096 or len(raw)!=i['filesz'] or raw[-1:]!=b'\0' or b'\0' in raw[:-1]:
            raise ValueError('invalid ELF interpreter')
        if file_offset(rows,i['vaddr'],i['filesz'])!=i['offset']:
            raise ValueError('contradictory ELF interpreter segment')
        interp=string_at(raw,0);chunks.append((i['offset'],raw))
    elif decoded['interpreter']:
        raise ValueError('unexpected ELF interpreter evidence')
    # A supplied report cannot give different bytes for overlapping metadata.
    for offset,raw in chunks:
        for other,data in chunks:
            lo=max(offset,other);hi=min(add(offset,len(raw)),add(other,len(data)))
            if lo<hi and raw[lo-offset:hi-offset]!=data[lo-other:hi-other]:
                raise ValueError('contradictory overlapping ELF metadata')
    return dict(kind=h['kind'],entry=h['entry'],segments=rows,soname=soname,needed=needed,interpreter=interp)


def collect_elf(stream):
    """Read bounded metadata from an already-open regular file, never execute it."""
    stream.seek(0,2);size=stream.tell()
    integer(size,64,(1<<63)-1,'ELF file size')
    def read(offset,length):
        bounded_range(offset,length,size)
        if length>MAX_METADATA: raise ValueError('ELF metadata limit')
        stream.seek(offset);raw=stream.read(length)
        if len(raw)!=length: raise ValueError('truncated ELF file')
        return raw
    raw=read(0,64);h=header(raw,size)
    ph=read(h['phoff'],h['count']*56);rows=programs(ph,h,size)
    d=one(rows,2);dyn=read(d['offset'],d['filesz']);tags=dynamic(dyn)
    strings=read(file_offset(rows,tags[5][0],tags[10][0]),tags[10][0])
    interps=[r for r in rows if r['kind']==3]
    interp=read(one(rows,3)['offset'],one(rows,3)['filesz']) if interps else b''
    result=dict(file_size=size,header=raw.hex(),program_headers=ph.hex(),
                dynamic=dyn.hex(),strings=strings.hex(),interpreter=interp.hex())
    parse_elf(result)
    return result


def reconcile_mappings(rows, elf, size, page_size):
    integer(page_size,PAGE,PAGE,'supported Linux page size')
    for row in rows:
        if (row['lo']%PAGE or row['hi']%PAGE or row['offset']%PAGE or
                row['offset']>=size or add(row['offset'],row['hi']-row['lo'])>up(size) or
                row['permissions'][3]!='p'):
            raise ValueError('unaligned or out-of-bounds runtime mapping')
    loads=[r for r in elf['segments'] if r['kind']==1 and r['filesz']]
    executable=[r for r in loads if r['flags']==5]
    biases=set()
    first=next((r for r in rows if r['permissions']=='r-xp'),None)
    if first is None:
        raise ValueError('missing executable runtime mapping')
    # Any valid layout must explain this VMA. At most one candidate per PT_LOAD;
    # do not multiply candidate work by every possible VMA/segment pairing.
    for segment in executable:
        delta=first['offset']-down(segment['offset'])
        bias=first['lo']-down(segment['vaddr'])-delta
        if delta>=0 and 0<=bias<=U64 and bias%PAGE==0: biases.add(bias)
    def matches(bias):
        # Check translated memory endpoints even for anonymous-only regions;
        # their contents/VMAs need not be included in this file-backed record.
        for segment in elf['segments']:
            if segment['kind']==1 and segment['memsz']:
                add(bias,up(add(segment['vaddr'],segment['memsz'])))
        coverage=[[] for _ in loads]
        relro=[(add(bias,down(s['vaddr'])),add(bias,down(add(s['vaddr'],s['memsz']))))
               for s in elf['segments'] if s['kind']==0x6474e552]
        for row in rows:
            found=[]
            for index,segment in enumerate(loads):
                lo=add(bias,down(segment['vaddr']));hi=add(bias,up(add(segment['vaddr'],segment['filesz'])))
                if not lo<=row['lo']<row['hi']<=hi:continue
                if row['offset']!=add(down(segment['offset']),row['lo']-lo):continue
                expected={4:'r--p',5:'r-xp',6:'rw-p'}[segment['flags']]
                if row['permissions']!=expected:
                    if not (expected=='rw-p' and row['permissions']=='r--p' and
                            any(a<=row['lo'] and row['hi']<=b for a,b in relro)):continue
                found.append(index)
            if len(found)!=1:return False
            coverage[found[0]].append((row['lo'],row['hi']))
        for segment,spans in zip(loads,coverage):
            current=add(bias,down(segment['vaddr']))
            for lo,hi in sorted(spans):
                if lo!=current:return False
                current=hi
            if current!=add(bias,up(add(segment['vaddr'],segment['filesz']))):return False
        return True
    if sum(matches(bias) for bias in biases)!=1:
        raise ValueError('incomplete or contradictory ELF load mappings')
