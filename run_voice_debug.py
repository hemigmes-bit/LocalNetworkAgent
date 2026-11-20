#!/usr/bin/env python3
"""
Debug runner for voice_loop.py
"""
import sys
import os

# Ensure we're in the right directory
os.chdir(r"C:\Users\Usuario\LocalNetworkAgent")

# Insert path BEFORE any other imports
sys.path.insert(0, r"C:\Users\Usuario\LocalNetworkAgent\python\src\main\python")

print("=== DEBUG START ===")
print("CWD:", os.getcwd())
print("sys.path[0]:", sys.path[0])

# Now import voice_loop and run
import voice_loop

print("Voice loop imported successfully")