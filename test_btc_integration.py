#!/usr/bin/env python3

import logging
import numpy as np
from pathlib import Path

from src.chord_detection import ChordDetector, ChordDetectionConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_model_loading():
    logger.info("=" * 60)
    logger.info("TEST 1: Model Loading")
    logger.info("=" * 60)
    
    try:
        config = ChordDetectionConfig(
            model_path="models/chord_detection/btc_model.pt",
            use_voca=False,
            device="auto",
        )
        
        detector = ChordDetector(config)
        detector.load_model()
        
        logger.info("✓ Model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_extraction():
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Feature Extraction")
    logger.info("=" * 60)
    
    try:
        config = ChordDetectionConfig(
            model_path="models/chord_detection/btc_model.pt",
            use_voca=False,
        )
        
        detector = ChordDetector(config)
        
        duration = 10.0
        sr = 22050
        audio = np.random.randn(int(duration * sr)).astype(np.float32)
        
        features = detector.btc_model.extract_features(audio, sr)
        
        logger.info(f"✓ Feature extraction successful")
        logger.info(f"  Audio shape: {audio.shape}")
        logger.info(f"  Feature shape: {features.shape}")
        return True
    except Exception as e:
        logger.error(f"✗ Feature extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_inference():
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: BTC Inference")
    logger.info("=" * 60)
    
    try:
        config = ChordDetectionConfig(
            model_path="models/chord_detection/btc_model.pt",
            use_voca=False,
            device="auto",
        )
        
        detector = ChordDetector(config)
        detector.load_model()
        
        duration = 10.0
        sr = 22050
        audio = np.random.randn(int(duration * sr)).astype(np.float32)
        
        predictions = detector.btc_model.predict(audio, sr)
        
        logger.info(f"✓ Inference successful")
        logger.info(f"  Number of predictions: {len(predictions)}")
        if len(predictions) > 0:
            logger.info(f"  First prediction: time={predictions[0][0]:.3f}s, chord={predictions[0][1]}, conf={predictions[0][2]:.3f}")
            logger.info(f"  Last prediction: time={predictions[-1][0]:.3f}s, chord={predictions[-1][1]}, conf={predictions[-1][2]:.3f}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Inference failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vocabulary():
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Vocabulary Check")
    logger.info("=" * 60)
    
    try:
        config_majmin = ChordDetectionConfig(use_voca=False)
        detector_majmin = ChordDetector(config_majmin)
        vocab_majmin = detector_majmin.btc_model.get_vocabulary()
        
        config_extended = ChordDetectionConfig(use_voca=True)
        detector_extended = ChordDetector(config_extended)
        vocab_extended = detector_extended.btc_model.get_vocabulary()
        
        logger.info(f"✓ Vocabulary check successful")
        logger.info(f"  Maj/Min vocabulary size: {len(vocab_majmin)}")
        logger.info(f"  Extended vocabulary size: {len(vocab_extended)}")
        logger.info(f"  Maj/Min sample: {vocab_majmin[:5]}")
        logger.info(f"  Extended sample: {vocab_extended[:5]}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Vocabulary check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    logger.info("BTC MODEL INTEGRATION TEST")
    logger.info("=" * 60)
    
    tests = [
        ("Vocabulary Check", test_vocabulary),
        ("Feature Extraction", test_feature_extraction),
        ("Model Loading", test_model_loading),
        ("BTC Inference", test_inference),
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, result in results:
        status = "PASS ✓" if result else "FAIL ✗"
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

