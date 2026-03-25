#!/usr/bin/env python3
"""Quick verification script for FlowValidator refactoring."""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src/datasift_opensource/backend'))

from core.orchestrator.flow_validator import FlowValidator, ValidateStepResults
from core.orchestrator.abstract_orchestrator import AbstractOrchestrator

def test_imports():
    """Test that all imports work correctly."""
    print("✓ FlowValidator imported successfully")
    print("✓ ValidateStepResults imported successfully")
    print("✓ AbstractOrchestrator imported successfully")
    return True

def test_validator_methods_exist():
    """Test that FlowValidator has all expected methods."""
    expected_methods = [
        'validate',
        'validate_dag',
        'validate_operators',
        'validate_first_operator',
        'validate_disjoint_operators',
        'check_duplicate_extract_operators',
        'validate_operator_category',
        'get_operator_category',
        'create_validation_alerts',
        'get_duplicate_node_names',
        '_validate_node',
        '_evaluate_node_validation_skip',
        '_build_graph',
        '_make_undirected_graph',
        '_find_connected_components',
    ]
    
    for method in expected_methods:
        if not hasattr(FlowValidator, method):
            print(f"✗ Missing method: {method}")
            return False
        print(f"✓ Method exists: {method}")
    
    return True

def test_orchestrator_delegation():
    """Test that AbstractOrchestrator properly delegates to FlowValidator."""
    delegation_methods = [
        'validate',
        'validate_dag',
        'validate_operators',
    ]
    
    for method in delegation_methods:
        if not hasattr(AbstractOrchestrator, method):
            print(f"✗ AbstractOrchestrator missing delegation method: {method}")
            return False
        print(f"✓ AbstractOrchestrator has delegation method: {method}")
    
    return True

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("FlowValidator Refactoring Verification")
    print("=" * 60)
    print()
    
    tests = [
        ("Import Test", test_imports),
        ("FlowValidator Methods Test", test_validator_methods_exist),
        ("AbstractOrchestrator Delegation Test", test_orchestrator_delegation),
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 60)
        try:
            if not test_func():
                all_passed = False
                print(f"✗ {test_name} FAILED")
            else:
                print(f"✓ {test_name} PASSED")
        except Exception as e:
            print(f"✗ {test_name} FAILED with exception: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
