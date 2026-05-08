Bump the patch version in `pyproject.toml` and publish to PyPI.

Steps:
1. Read `/mnt/c/Users/antonio.andriett/git/steely/pyproject.toml` and find the current `version = "X.Y.Z.N"` line.
2. Increment the last numeric segment by 1 (e.g. `1.0.2.1` → `1.0.2.2`).
3. Write the new version back to `pyproject.toml`.
4. Run the following commands in order (each must succeed before the next):
   ```
   cd /mnt/c/Users/antonio.andriett/git/steely && sudo rm -rf dist build steely.egg-info
   cd /mnt/c/Users/antonio.andriett/git/steely && uv build --wheel
   cd /mnt/c/Users/antonio.andriett/git/steely && twine upload dist/* -u __token__ -p $(grep '^password' pyproject.toml | head -1 | sed 's/.*= *//' | tr -d '"')
   ```
5. Report the new version and confirm the upload succeeded.
