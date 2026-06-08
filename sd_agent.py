#!/usr/bin/env python3
"""Shortcut: python sd_agent.py instead of python main.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from main import main
main()
