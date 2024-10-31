from pytest import Parser


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--long",
        action="store_true",
        dest="long",
        default=False,
        help="enable long running tests (excluded in CI)",
    )
