# Flag set by the test fixture in tests/conftest.py.
# Used by autodiscovery to track loaded modules during tests.
IS_TESTING = False


def is_testing() -> bool:
    return IS_TESTING
