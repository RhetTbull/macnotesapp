#!/bin/sh

# script to help build macnotesapp release
# this is unique to my own dev setup

echo "Cleaning old build and dist directories"
rm -rf dist
rm -rf build

echo "Updating README.md"
uv run cog -r README.md

# update docs
echo "Building docs"
uv run mkdocs build

# build the package
echo "Building package"
uv build

# build CLI executable
echo "Building CLI executable"
uv run pyinstaller macnotesapp.spec

# package executable as DMG
echo "Zipping executable"
test -f dist/notes.zip && rm dist/notes.zip
zip dist/notes.zip dist/notes && rm dist/notes

# Tidy up the homebrew formula
sha256=$(openssl dgst -hex -sha256 dist/notes.zip | cut -d ' ' -f 2)
sed -i '' "s/sha256 \".*\"/sha256 \"$sha256\"/" HomebrewFormula/macnotesapp.rb

# Done!
echo "Done"
