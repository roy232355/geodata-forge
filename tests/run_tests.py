# -*- coding: utf-8 -*-
import sys
import os
import unittest

# Resolve absolute paths so this script can be run from any working directory
current_dir = os.path.dirname(os.path.abspath(__file__))
plugin_root = os.path.dirname(current_dir)

if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)


def run_all_tests():
    print("Running GeoData Forge Offline Test Suite...")
    print(f"Plugin root: {plugin_root}")
    print("-" * 50)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=current_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    success = result.wasSuccessful()
    print("-" * 50)
    if success:
        print("SUCCESS: All tests passed!")
    else:
        print(f"FAILURE: {len(result.failures)} failures, {len(result.errors)} errors encountered.")

    return success


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
