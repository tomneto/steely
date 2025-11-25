# sudo rm -rf dist/* build elemental_tools.egg-info

uv build --wheel

twine upload dist/*

sudo rm -rf dist build steely.egg-info

