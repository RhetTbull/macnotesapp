# Welcome to MacNotesApp

Work with Apple MacOS Notes.app from the command line. Also includes python interface for scripting Notes.app from your own python code. Interactive browsing of notes in a TUI (Terminal User Interface? Textual User Interface?) coming soon!

For full documentation visit [macnotesapp](https://rhettbull.github.io/macnotesapp/).

## Installation

If you just want to use the command line tool, the easiest option is to install via [pipx](https://pypa.github.io/pipx/).

If you use `pipx`, you will not need to create a python virtual environment as `pipx` takes care of this. The easiest way to do this on a Mac is to use [homebrew](https://brew.sh/):

* Open `Terminal` (search for `Terminal` in Spotlight or look in `Applications/Utilities`)
* Install `homebrew` according to instructions at [https://brew.sh/](https://brew.sh/)
* Type the following into Terminal: `brew install pipx`
* Then type this: `pipx install macnotesapp`
* `pipx` will install the `macnotesapp` command line interface (CLI) as an executable named `notes`
* Now you should be able to run `notes` by typing: `notes`

Once you've installed macnotesapp with pipx, to upgrade to the latest version:

    pipx upgrade macnotesapp

**Note**: Currently tested on MacOS 10.15.7/Catalina and 13.1/Ventura.
