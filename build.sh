# sudo rm -rf dist/* build elemental_tools.egg-info

uv build --wheel

twine upload dist/* -u __token__ -p pypi-AgEIcHlwaS5vcmcCJDhhMDFhZTQ2LTE1MGQtNDQ1ZC05NTI2LTY3Y2NjZGYzZTgxZgACDlsxLFsic3RlZWx5Il1dAAIsWzIsWyI5NjUwMTQ2NC01OTQ1LTRlYWMtODQzOS05NmE4MTcyYTY0YWYiXV0AAAYgfuN0NpKXKEi7J7_eq0UCXVnQ_cWHe7DSUBJOkNJFBWE

sudo rm -rf dist build steely.egg-info

