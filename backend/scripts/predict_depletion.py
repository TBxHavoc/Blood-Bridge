#!/usr/bin/env python3
"""
Blood Bridge - ML Supply Depletion & Usage Prediction Engine
IBM Z Datathon 2026 - AI Secured Track (Innovation without Exposure)
"""
import os
import sys

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_dir = os.path.dirname(parent_dir)

if os.path.exists(os.path.join(root_dir, "scripts", "predict_depletion.py")):
    sys.path.insert(0, os.path.join(root_dir, "scripts"))
    import predict_depletion
    predict_depletion.main()
else:
    print("Please run scripts/predict_depletion.py from project root.")
