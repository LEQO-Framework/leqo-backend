#!/usr/bin/env python
import numpy as np

def test_amplitude_encoding_fixed():
    print("=== Testing Fixed Amplitude Encoding Logic \n")
    ##///////////////////
    # Test 1: bounds=1 input validation
    print("Test 1: bounds=1 must be in [0,1]")
    bounds = 1
    values = [0.2, 0.3, 0.4, 0.5]
    vec = np.asarray(values, dtype=float)
    print(f"  Input: {values}")
    print(f"  In [0,1]? {not (np.any(vec < 0.0) or np.any(vec > 1.0))}")
    
    if bounds == 1:
        if np.any(vec < 0.0) or np.any(vec > 1.0):
            print("  ERROR: Out of bounds")
        else:
            print(" Validation passed")
    
    target_len = 1 << (int(vec.size) - 1).bit_length()
    vec = np.pad(vec, (0, target_len - vec.size), mode="constant")
    print(f"  After padding: {vec}")
    
    norm = np.linalg.norm(vec)
    print(f"  Norm: {norm}")
    
    vec = vec / norm 
    print(f"  After normalization: {vec}")
    print(f"   StatePreparation ready: norm = {np.linalg.norm(vec):.10f}")
    print()
    
    # Test 2: bounds=0 
    print("Test 2: bounds=0 allows any value")
    bounds = 0
    values = [1.5, 2.0, 0.5, 1.0]
    vec = np.asarray(values, dtype=float)
    print(f"  Input: {values}")
    print(f"  (no [0,1] check for bounds=0)")
    
    
    target_len = 1 << (int(vec.size) - 1).bit_length()
    vec = np.pad(vec, (0, target_len - vec.size), mode="constant")
    print(f"  After padding: {vec}")
    
    norm = np.linalg.norm(vec)
    print(f"  Norm: {norm}")
    
    vec = vec / norm  
    print(f"  After normalization: {vec}")
    print(f"  StatePreparation ready: norm = {np.linalg.norm(vec):.10f}")
    print()
    
    # Test 3: Show the fix
    print("Test 3: normalize?")
    print("  StatePreparation requires a normalized quantum state.")
    print("  bounds parameter only controls INPUT validation:")
    print("    - bounds=1: Input must be in [0,1]")
    print("    - bounds=0: Input can be any value")
    print("  Normalization: alwayss required for valid quantum state")
    print("  Result: ||vec|| = 1.0 ")

if __name__ == "__main__":
    test_amplitude_encoding_fixed()
