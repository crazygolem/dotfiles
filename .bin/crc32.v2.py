#!/usr/bin/python

# Version: 2016-01-22
# Author: crazygolem
# License: WTFPL Version 2 (http://www.wtfpl.net)
#
# Inspired by the script by Taoufix (aka Taoufik El Aoumari)
# ANIME CRC32 CHECKSUM IN LINUX V2.0
# http://agafix.org/anime-crc32-checksum-in-linux-v20

import sys, re, zlib, os

pat     = r'(?<=\[)(%s)(?=\])'  # CRC must be enclosed in brackets
c_res   = '\x1b[00;00m'         # Removes color
c_err   = '\x1b[31;01m'         # Fail: Red
c_ok    = '\x1b[32;01m'         # Match: Green

def progress(current, total, file):
    # The file size cannot always be known by the OS, and if it is not, total
    # will be 0. E.g., running
    #   `$0 <(cat file.dat)`
    # will create a file descriptor in /proc/self/fd/ of unknown (= 0) size
    # from which the output of `cat` will be read. It's basically the same
    # when reading from stdin.
    if total:
        print('%7d%%\t%s' %((current / total) * 100, file), end='\r')
    elif file:
        print('%8s\t%s\r' %('...', file), end='\r')

def match(name, crc):
    anycrc = r'[a-f0-9]{8}'
    sub = r'%s\1%s' %('%s', c_res)
    cn = re.subn(pat %(crc), sub %(c_ok), name, flags=re.I) + (True,)
    if cn[1] is 0:
        cn = re.subn(pat %(anycrc), sub %(c_err), name, flags=re.I) + (False,)
    print('%s%s%s\t%s' %(c_ok if cn[2] else c_err, crc, c_res, cn[0]))
    return cn[2]

def crc32sum(stream):
    try:
        crc = 0
        fsize = os.fstat(stream.fileno()).st_size
        bsize = 2**16           # 64k: arbitrary but balanced
        processed = 0
        for data in iter(lambda: stream.read(bsize), b''):
            crc = zlib.crc32(data, crc)
            processed += len(data)
            progress(processed, fsize, stream.name)
        return crc & 0xffffffff     # Compat for some python < 3.0
    except KeyboardInterrupt:
        sys.stdout.write('\n')      # Prevents garbage on line when cancelled
        sys.exit(1)

allmatching = True
for file in sys.argv[1:]:
    try:
        with (sys.stdin.buffer if file is '-' else open(file, 'rb')) as stream:
            crc = crc32sum(stream)
            allmatching &= match(stream.name, '%.8X' %(crc))
    except IOError as e:
        print(e, file=sys.stderr)
sys.exit(int(not allmatching))

