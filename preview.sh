#!/usr/bin/env bash
python3 generate.py
python3 -m http.server -d ./dist/ 5000
