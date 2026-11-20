#!/usr/bin/env python3
import sys
import os

os.chdir(r"C:\Users\Usuario\LocalNetworkAgent")
sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")

# Monkey-patch import to trace
original_import = __builtins__.__import__

def tracing_import(name, *args, **kwargs):
    if 'tts_kokoro' in name:
        print(f"[TRACE] Importing: {name}")
        import traceback
        traceback.print_stack(limit=5)
    return original_import(name, *args, **kwargs)

__builtins__.__import__ = tracing_import

# Now run the script
import voice_loop