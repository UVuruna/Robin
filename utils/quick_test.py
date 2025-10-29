# utils/quick_test.py
# VERSION: 2.0 - Refactored to use RegionManager (v4.0 architecture)
# PURPOSE: Quick system test for coordinate system
# Tests: JSON format, RegionManager, coordinate calculation

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from config.settings import PATH
from core.capture.region_manager import RegionManager


def test_json_format():
    """Test JSON file format."""
    print("\n" + "=" * 70)
    print("TEST 1: JSON FORMAT")
    print("=" * 70)

    coords_file = PATH.screen_regions

    if not coords_file.exists():
        print("❌ FAIL: screen_regions.json not found!")
        print(f"   Expected: {coords_file}")
        return False

    try:
        with open(coords_file, "r") as f:
            data = json.load(f)

        # Check structure
        if "layouts" not in data:
            print("❌ FAIL: Missing 'layouts' key in JSON!")
            return False

        if "regions" not in data:
            print("❌ FAIL: Missing 'regions' key in JSON!")
            return False

        if "region_colors" not in data:
            print("❌ FAIL: Missing 'region_colors' key in JSON!")
            return False

        print("✅ PASS: JSON structure is correct")
        print(f"   Positions: {len(data['positions'])}")
        print(f"   Bookmakers: {len(data['bookmakers'])}")

        return True

    except json.JSONDecodeError as e:
        print("❌ FAIL: Invalid JSON format!")
        print(f"   Error: {e}")
        return False


def test_region_manager():
    """Test RegionManager functionality."""
    print("\n" + "=" * 70)
    print("TEST 2: REGION MANAGER")
    print("=" * 70)

    try:
        manager = RegionManager()

        # Test monitor detection
        monitors = manager.monitors
        print(f"✅ Detected monitors: {len(monitors)}")
        for mon in monitors:
            print(f"   {mon}")

        # Test layout positions
        print(f"✅ Layout 4 positions: {manager.LAYOUT_4_POSITIONS}")
        print(f"✅ Layout 6 positions: {manager.LAYOUT_6_POSITIONS}")
        print(f"✅ Layout 8 positions: {manager.LAYOUT_8_POSITIONS}")

        # Test regions configured
        regions = manager.config.get("regions", {})
        print(f"✅ Configured regions: {len(regions)}")

        if not regions:
            print("⚠️  WARNING: No regions configured!")
            print("   Add regions to screen_regions.json")
            return False

        return True

    except Exception as e:
        print("❌ FAIL: RegionManager error!")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_coordinate_calculation():
    """Test coordinate calculation."""
    print("\n" + "=" * 70)
    print("TEST 3: COORDINATE CALCULATION")
    print("=" * 70)

    try:
        manager = RegionManager()

        # Test layout offset calculation
        test_layout = "GRID 2×3"
        test_position = "TC"

        print(f"\nTesting: {test_layout} @ {test_position}")

        offsets = manager.calculate_layout_offsets(test_layout, "primary")
        print(f"✅ Calculated offsets for {test_layout}:")
        for pos, (x, y) in offsets.items():
            print(f"   {pos:3s} → ({x:5d}, {y:5d})")

        # Test region retrieval
        region = manager.get_region("score_region_small", test_position, test_layout)
        print(f"\n✅ Retrieved region: {region}")

        # Test all regions for position
        all_regions = manager.get_all_regions_for_position(test_position, test_layout)
        print(f"\n✅ Retrieved {len(all_regions)} regions for position {test_position}")

        # Display sample coordinates
        print("\nSample calculated regions:")
        for region_name, region_obj in list(all_regions.items())[:3]:
            print(f"  {region_name:30s} → ({region_obj.left:5d}, {region_obj.top:5d}, {region_obj.width:4d}x{region_obj.height:3d})")

        return True

    except Exception as e:
        print("❌ FAIL: Coordinate calculation error!")
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_all_combinations():
    """Test all layout x position combinations."""
    print("\n" + "=" * 70)
    print("TEST 4: ALL LAYOUT/POSITION COMBINATIONS")
    print("=" * 70)

    try:
        manager = RegionManager()

        layouts = ["layout_4", "GRID 2×3", "layout_8"]
        test_results = []

        for layout in layouts:
            offsets = manager.calculate_layout_offsets(layout, "primary")

            print(f"\n{layout}:")
            for position in offsets.keys():
                try:
                    region = manager.get_region("score_region_small", position, layout)
                    print(f"  ✅ {position:3s} → Region at ({region.left}, {region.top})")
                    test_results.append(True)
                except Exception as e:
                    print(f"  ❌ {position:3s} → Failed: {e}")
                    test_results.append(False)

        passed = sum(test_results)
        total = len(test_results)
        print(f"\nResults: {passed}/{total} passed")

        if passed < total:
            print(f"❌ FAIL: {total - passed} combinations failed!")
            return False

        print("✅ PASS: All combinations work!")
        return True

    except Exception as e:
        print("❌ FAIL: Error testing combinations!")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("AVIATOR COORDINATE SYSTEM - QUICK TEST")
    print("=" * 70)

    results = []

    # Run tests
    results.append(("JSON Format", test_json_format()))
    results.append(("RegionManager", test_region_manager()))
    results.append(("Coordinate Calculation", test_coordinate_calculation()))
    results.append(("All Combinations", test_all_combinations()))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name:30s} {status}")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print("\n" + "=" * 70)
    print(f"TOTAL: {total_passed}/{total_tests} tests passed")
    print("=" * 70)

    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
        print("   System is ready to use!")
        print("\nNext steps:")
        print("  1. Inject CSS into browsers")
        print("  2. Run: python apps/main_data_collector.py")
    else:
        print("\n⚠️  SOME TESTS FAILED!")
        print("   Fix issues above before running apps")
        print("\nCommon fixes:")
        print("  • Run region_editor.py to create coordinates")
        print("  • Check JSON format in screen_regions.json")
        print("  • Ensure positions are defined")

    print("=" * 70 + "\n")

    return total_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
