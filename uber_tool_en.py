# -*- coding: utf-8 -*-
"""Uber Receipt Helper — English build entry point.

Same codebase as uber_tool.py; this wrapper only forces the UI language to English
so the packaged exe defaults to English regardless of the system locale.
"""
import os

os.environ["UBER_TOOL_LANG"] = "en"

import uber_tool  # noqa: E402

if __name__ == "__main__":
    uber_tool.main()
