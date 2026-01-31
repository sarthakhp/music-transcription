#!/usr/bin/env python3
"""
Test script for chord detection module.
This script verifies that the module structure is correct and can be imported.
"""

import logging
from pathlib import Path

from src.chord_detection import ChordDetector, ChordDetectionConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_module_import():
    """Test that all modules can be imported."""
    logger.info("Testing module imports...")
    
    try:
        from src.chord_detection import (
            ChordDetectionConfig,
            ChordEvent,
            ChordProgression,
            ChordDetector,
        )
        logger.info("✓ All modules imported successfully")
        return True
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False


def test_config_creation():
    """Test configuration creation."""
    logger.info("Testing configuration creation...")
    
    try:
        config = ChordDetectionConfig(
            bass_weight=0.5,
            other_weight=0.5,
            device="auto",
        )
        logger.info(f"✓ Config created: device={config.get_device()}")
        return True
    except Exception as e:
        logger.error(f"✗ Config creation failed: {e}")
        return False


def test_detector_creation():
    """Test detector creation."""
    logger.info("Testing detector creation...")
    
    try:
        detector = ChordDetector()
        logger.info("✓ ChordDetector created successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Detector creation failed: {e}")
        return False


def main():
    logger.info("="*60)
    logger.info("CHORD DETECTION MODULE TEST")
    logger.info("="*60)
    
    tests = [
        ("Module Import", test_module_import),
        ("Config Creation", test_config_creation),
        ("Detector Creation", test_detector_creation),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\nRunning: {test_name}")
        result = test_func()
        results.append((test_name, result))
    
    logger.info("\n" + "="*60)
    logger.info("TEST RESULTS")
    logger.info("="*60)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        logger.info("\n✓ All tests passed!")
        return 0
    else:
        logger.error("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())

