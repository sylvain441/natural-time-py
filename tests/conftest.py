import pytest


@pytest.fixture(scope="session")
def deltas(request):
    """Max observed |expected - received| per group, printed at the end of the run."""
    request.config.observed_deltas = {}
    return request.config.observed_deltas


def pytest_terminal_summary(terminalreporter, config):
    observed = getattr(config, "observed_deltas", None)
    if observed:
        terminalreporter.section("max observed deltas against the golden vectors")
        for group, (delta, where) in sorted(observed.items()):
            terminalreporter.write_line(f"{group:<22} {delta:.3e}  (at {where})")
