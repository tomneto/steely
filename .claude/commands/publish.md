Bump the patch version in `steely/__init__.py` and publish to PyPI.

The version has a single source of truth: `__version__` in `steely/__init__.py`
(`pyproject.toml` reads it via `[tool.hatch.version]`). Never edit a version in
`pyproject.toml`.

Steps:
1. Read `/mnt/c/Users/antonio.andriett/git/steely/steely/__init__.py` and find the current `__version__ = "X.Y.Z.N"` line.
2. Increment the last numeric segment by 1 (e.g. `1.0.3.5` → `1.0.3.6`).
3. Write the new version back to `steely/__init__.py`.
4. Make sure `PYPI_TOKEN` is exported in the environment (it lives in `.env`, which is gitignored — never hardcode it).
5. Run the following commands in order (each must succeed before the next):
   ```
   rm -rf dist build steely.egg-info
   cd /mnt/c/Users/antonio.andriett/git/steely && uv build --wheel
   cd /mnt/c/Users/antonio.andriett/git/steely && ./build.sh
   ```
   (`build.sh` builds the wheel and uploads with `twine ... -p "$PYPI_TOKEN"`.)
6. Report the new version and confirm the upload succeeded.
