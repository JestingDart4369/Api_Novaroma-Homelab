"""
Test script for rate limiting functionality.
Run this to verify rate limiting works correctly.
"""

import sys
import time
from datetime import datetime

# Test the rate limit store independently
sys.path.insert(0, 'D:/02_ApiServer')

# Mock environment variables before importing
import os
os.environ.setdefault('JWT_SECRET', 'test_secret')
os.environ.setdefault('OPENWEATHER_KEY', 'test_key')
os.environ.setdefault('GEOAPIFY_KEY', 'test_key')
os.environ.setdefault('NASA_API_KEY', 'test_key')
os.environ.setdefault('IPREGISTRY_KEY', 'test_key')
os.environ.setdefault('TELEPHONE_SEARCH_KEY', 'test_key')

from app.rate_limit import RateLimitStore, USER_RATE_LIMITS, API_RATE_LIMITS

def test_user_rate_limit():
    """Test per-user rate limiting"""
    print("=" * 60)
    print("Testing Per-User Rate Limits")
    print("=" * 60)

    store = RateLimitStore()
    user_id = 1
    role = "user"
    limit = USER_RATE_LIMITS[role]

    print(f"\nUser ID: {user_id}, Role: {role}, Limit: {limit}/hour")

    # Make requests up to limit
    for i in range(limit):
        allowed, remaining, reset = store.check_user_limit(user_id, role)
        if not allowed:
            print(f"[FAIL] FAIL: Request {i+1} blocked before reaching limit!")
            return False
        store.increment_user(user_id)

        if i % 100 == 0:
            print(f"  Request {i+1}/{limit}: allowed={allowed}, remaining={remaining}")

    # Try one more request (should be blocked)
    allowed, remaining, reset = store.check_user_limit(user_id, role)
    if allowed:
        print(f"[FAIL] FAIL: Request {limit+1} allowed after exceeding limit!")
        return False

    print(f"\n[PASS] SUCCESS: User rate limit enforced correctly")
    print(f"   - Allowed {limit} requests")
    print(f"   - Blocked request {limit+1}")
    print(f"   - Reset time: {datetime.fromtimestamp(reset)}")
    return True


def test_api_rate_limit():
    """Test per-API rate limiting"""
    print("\n" + "=" * 60)
    print("Testing Per-API Rate Limits")
    print("=" * 60)

    store = RateLimitStore()
    api_name = "nasa"
    limit = API_RATE_LIMITS[api_name]

    print(f"\nAPI: {api_name}, Limit: {limit}/hour")

    # Make requests up to limit
    for i in range(limit):
        allowed, remaining, reset = store.check_api_limit(api_name)
        if not allowed:
            print(f"[FAIL] FAIL: Request {i+1} blocked before reaching limit!")
            return False
        store.increment_api(api_name)

        if i % 100 == 0:
            print(f"  Request {i+1}/{limit}: allowed={allowed}, remaining={remaining}")

    # Try one more request (should be blocked)
    allowed, remaining, reset = store.check_api_limit(api_name)
    if allowed:
        print(f"[FAIL] FAIL: Request {limit+1} allowed after exceeding limit!")
        return False

    print(f"\n[PASS] SUCCESS: API rate limit enforced correctly")
    print(f"   - Allowed {limit} requests")
    print(f"   - Blocked request {limit+1}")
    print(f"   - Reset time: {datetime.fromtimestamp(reset)}")
    return True


def test_different_roles():
    """Test that admins have higher limits"""
    print("\n" + "=" * 60)
    print("Testing Different User Roles")
    print("=" * 60)

    store = RateLimitStore()

    # Test regular user
    user_limit = USER_RATE_LIMITS["user"]
    allowed, remaining, reset = store.check_user_limit(1, "user")
    print(f"\nRegular User: limit={user_limit}, remaining={remaining}")

    # Test admin user
    admin_limit = USER_RATE_LIMITS["admin"]
    allowed, remaining, reset = store.check_user_limit(2, "admin")
    print(f"Admin User: limit={admin_limit}, remaining={remaining}")

    if admin_limit > user_limit:
        print(f"\n[PASS] SUCCESS: Admin limit ({admin_limit}) > User limit ({user_limit})")
        return True
    else:
        print(f"\n[FAIL] FAIL: Admin limit should be higher than user limit")
        return False


def test_cleanup():
    """Test automatic cleanup of old entries"""
    print("\n" + "=" * 60)
    print("Testing Cleanup Functionality")
    print("=" * 60)

    store = RateLimitStore()

    # Add some data
    store.increment_user(1)
    store.increment_api("nasa")

    print(f"\nBefore cleanup:")
    print(f"  User requests: {len(store.user_requests)} users")
    print(f"  API requests: {len(store.api_requests)} APIs")

    # Trigger cleanup
    store._cleanup_expired()

    print(f"\nAfter cleanup:")
    print(f"  User requests: {len(store.user_requests)} users")
    print(f"  API requests: {len(store.api_requests)} APIs")

    print(f"\n[PASS] SUCCESS: Cleanup executed without errors")
    return True


def test_multiple_users():
    """Test multiple users don't interfere with each other"""
    print("\n" + "=" * 60)
    print("Testing Multiple Users")
    print("=" * 60)

    store = RateLimitStore()

    # User 1 makes 10 requests
    for i in range(10):
        store.increment_user(1)

    # User 2 makes 5 requests
    for i in range(5):
        store.increment_user(2)

    # Check both users
    allowed1, remaining1, reset1 = store.check_user_limit(1, "user")
    allowed2, remaining2, reset2 = store.check_user_limit(2, "user")

    user_limit = USER_RATE_LIMITS["user"]

    print(f"\nUser 1: made 10 requests, remaining={remaining1}/{user_limit}")
    print(f"User 2: made 5 requests, remaining={remaining2}/{user_limit}")

    # User 1 should have 10 counted, User 2 should have 5 counted
    expected_remaining_1 = user_limit - 10 - 1  # -1 for the check itself
    expected_remaining_2 = user_limit - 5 - 1

    if remaining1 == expected_remaining_1 and remaining2 == expected_remaining_2:
        print(f"\n[PASS] SUCCESS: User rate limits are isolated")
        return True
    else:
        print(f"\n[FAIL] FAIL: Expected user 1 remaining={expected_remaining_1}, got {remaining1}")
        print(f"        Expected user 2 remaining={expected_remaining_2}, got {remaining2}")
        return False


def main():
    """Run all tests"""
    print("\n")
    print("=" * 60)
    print("         RATE LIMITING TEST SUITE")
    print("=" * 60)

    tests = [
        ("Different Roles", test_different_roles),
        ("Cleanup", test_cleanup),
        ("Multiple Users", test_multiple_users),
        ("User Rate Limit", test_user_rate_limit),
        ("API Rate Limit", test_api_rate_limit),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n[FAIL] ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, success in results:
        status = "[PASS] PASS" if success else "[FAIL] FAIL"
        print(f"{status}: {name}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[WARNING]  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
