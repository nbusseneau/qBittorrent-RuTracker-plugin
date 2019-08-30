def pytest_addoption(parser):
    parser.addoption("--username", required=False, help="RuTracker username")
    parser.addoption("--password", required=False, help="RuTracker password")

