#!/usr/bin/env python3

"""
   Some utilities for working with JSON
   Python3 only
"""

import sys
if sys.hexversion < 0x03000000:
    raise ImportError("This script requires Python 3")
import json

def write_utf8(output, path, indent=1, sort_keys=True, ensure_ascii=False):
    """
    Write output to the given file path using UTF_8
    Defaults to sorted keys, ident=1
    Preserves UTF-8 characters by default.
    """
    with open(path, "w", encoding='utf-8') as f:
        json.dump(output, f, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii)
        
def read_utf8(path):
    """
    Read and parse JSON from the given file path assuming UTF-8 encoding
    """
    with open(path, "rb") as f:
        input = json.loads(f.read().decode('UTF-8', errors='replace'))
