from pathlib import Path

import fixture_pixi_pkg


def test_add() -> None:
    assert fixture_pixi_pkg.add(1, 2) == 3


def test_imported_from_installed_wheel() -> None:
    # The repo env installs the package editable, so this fails unless library mode swapped in the wheel.
    assert "site-packages" in Path(fixture_pixi_pkg.__file__).parts
