"""Foundation checks for package installation and test discovery."""

import lasi


def test_package_imports() -> None:
    assert lasi.__version__ == "0.1.0"
