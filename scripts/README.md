Scripts are little programs written in virtually any language that can send and receive directly to the Smoothieboard via Smoopi.
They are launched from a Macro button that is formatted so...

    [script some name]
    name= button label
    io= true
    # program/script to execute
    exec= program-name path-to-script
    # optional arguments which a dialog will prompt for and are passed to the script on the command line
    args=--width,--length,--tool-diameter

Where progam-name is the name of the scripting interpreter (eg ruby or python) and path-to-script is the path of the script to run.

When the script is running all communications with the Smoopi interface are turned off (so DRO will not update etc).

When the script writes to stdout that is sent directly to the smoothieboard, when the script reads from stdin it reads whatever the smootieboard has sent back, when the script writes to stderr it shows up in the console window.

The script must exit when done for smoopi to continue controlling the board.
