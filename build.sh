# sudo rm -rf dist/* build elemental_tools.egg-info

python3 setup.py bdist_wheel # or uv build --wheel

twine upload dist/*

sudo rm -rf dist build steely.egg-info

