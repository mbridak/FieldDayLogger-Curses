#!/bin/bash
pip uninstall -y fdcurses
rm dist/*
python3 -m build
pip install -e .
