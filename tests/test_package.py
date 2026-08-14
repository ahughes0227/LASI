"""Foundation checks for package installation and test discovery."""

import services


def test_package_imports() -> None:
    assert services.__version__ == "0.1.0"
