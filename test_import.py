#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test import of app_gui module"""

try:
    import app_gui
    print("OK")
except Exception as e:
    import traceback
    print("ERROR")
    traceback.print_exc()
