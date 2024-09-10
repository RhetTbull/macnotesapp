#!/bin/sh

# script to help build macnotesapp release
# this is unique to my own dev setup

echo "Cleaning old build and dist directories"
rm -rf dist
rm -rf build

echo "Updating README.md"
cog -r README.md

# update docs
echo "Building docs"
mkdocs build

# build the package
echo "Building package"
python3 -m build

# build CLI executable
echo "Building CLI executable"
pyinstaller macnotesapp.spec

# package executable as DMG
echo "Zipping executable"
test -f dist/notes.zip && rm dist/notes.zip
zip dist/notes.zip dist/notes && rm dist/notes

# update homebrew formula
# this relies on the tag for the release existing on github!
version=$(python -c 'import pkg_resources; print(pkg_resources.get_distribution("macnotesapp").version)' 2>/dev/null)
echo $version
brew update-python-resources HomebrewFormula/macnotesapp.rb

# Done!
echo "Done"
