""" stand alone command line script for use with pyinstaller
    
    To build this into an executable:
    - install pyinstaller:
        python3 -m pip install pyinstaller
    - then use make_cli_exe.sh to run pyinstaller

    Resulting executable will be in "dist/notes"

    Note: This is *not* the cli that "python3 -m pip install macnotesapp" or "python setup.py install" would install;
    it's merely a wrapper around __main__.py to allow pyinstaller to work
    
"""

from macnotesapp.cli import cli_main

if __name__ == "__main__":
    cli_main()
