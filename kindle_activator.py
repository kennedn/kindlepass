#!/usr/bin/env python3
import os
import struct
import subprocess as shell
import audible_kennedn as audible
import httpx
from getpass import getpass
from tempfile import mkstemp
from sys import platform


class MenuItem:
    """Container for a simple menu item

    arguments:
    prompt:
        A simple string representing item
    action:
        A Description string to be displayed in menu"""
    def __init__(self, prompt, action):
        self.action = action
        self.prompt = prompt


class Kindle:
    """Represents a Kindle device, contianing necessary information to activate device

    arguments:
    serial:
        Serial number of kindle, required for activation
    mountpoint:
        Location of mounted usb storage for device

    methods:
    __local_activate():
        Attempt to retrieve activation from device
    activate():
        Request activation from Audible servers
    save(location=None):
        Save activation file to device or provided location

    properties:
    is_activated:
        Check if self.activation is set
    is_mounted:
        Check self.mountpoint is set
    remote_file_exists:
        Check if activation exists on device
    filepath:
        Return path to device activation
    bytes:
        Derive and return activation bytes from self.activation
    model:
        Lookup serial prefix in model_lookup table, return model string.
    """
    model_lookup = {'B001': 'Kindle 1',
                    'B101': 'Kindle 1',
                    'B002': 'Kindle 2',
                    'B003': 'Kindle 2',
                    'B004': 'Kindle DX',
                    'B005': 'Kindle DX',
                    'B009': 'Kindle DX Graphite',
                    'B008': 'Kindle 3 WiFi',
                    'B006': 'Kindle 3 3G',
                    'B00A': 'Kindle 3 3G',
                    'B00C': 'Kindle PaperWhite',
                    'B00E': 'Kindle 4',
                    'B00F': 'Kindle Touch 3G',
                    'B011': 'Kindle Touch WiFi',
                    'B010': 'Kindle Touch 3G',
                    'B023': 'Kindle 4',
                    '9023': 'Kindle 4'}
    default = None

    def __init__(self, serial: str, mountpoint=None):
        self.serial = serial
        self.mountpoint = mountpoint
        self.remote_file = "/system/AudibleActivation.sys"
        self.activation = None
        self.__local_activate()
        # Effectivly sets first Object invocation as default
        if self.default is None:
            Kindle.default = self

    def __local_activate(self):
        # Sanity check that local activation exists and is the right size
        if self.is_mounted and self.remote_file_exists and os.stat(self.filepath).st_size == 0x237:
            with open(self.filepath, 'rb') as activation:
                a = activation.read()
            # Further sanity check, make sure our serial number appears in the activation
            if (a.find(self.serial.encode())):
                self.activation = a

    def activate(self, auth):
        # Audible returns activation that contains metadata, extracting 0x237 bytes
        # from the end discards this metadata.
        self.activation = auth.get_activation(self.serial)[-0x237:]

    def save(self, location=None):
        # Save Activation bytes to device or passed location
        try:
            if location is None and self.is_mounted:
                location = f"{self.mountpoint}{self.remote_file}"
            elif location is None and not self.is_mounted:
                raise IOError("Not mounted")
            if not self.is_activated:
                raise ValueError("Not Activated")

            with open(location, 'wb') as token:
                token.write(self.activation)
            return True
        except IOError as e:
            print(f"Couldn't open {location} for writing:\n{e}")
            return False

    @property
    def is_activated(self):
        return self.activation is not None

    @property
    def is_mounted(self):
        return self.mountpoint is not None

    @property
    def remote_file_exists(self):
        return os.path.isfile(f"{self.mountpoint}{self.remote_file}")

    @property
    def filepath(self):
        if self.remote_file_exists:
            return f"{self.mountpoint}{self.remote_file}"

    @property
    def bytes(self):
        # Unpack first 4 bytes of activation and swap endiness to produce activation bytes
        if self.is_activated:
            return struct.pack('>I', struct.unpack('<I', self.activation[:4])[0]).hex()
        else:
            return None

    @property
    def model(self):
        # Lookup serial prefix to get a human readible device name
        return Kindle.model_lookup.get(self.serial[:4], "Unknown")


def custom_captcha_callback(captcha_url: str) -> str:
    """Opens captcha image with eog, or default webbrowser as fallback"""
    captcha = httpx.get(captcha_url).content
    if (platform == "linux" or platform == "linux2") and shell.check_output(["which", "eog"]):
        fd, path = mkstemp()
        with os.fdopen(fd, 'wb') as file:
            file.write(captcha)
        shell.Popen(["eog", path])
        val = input("Enter Captcha: ")
        os.remove(path)
    else:
        import webbrowser
        webbrowser.open(captcha_url)
        val = input("Enter Captcha: ")
    return val


def auto_detect() -> list:
    """Queries pyudev and psutil to build a list of connected Kindle objects"""
    import pyudev
    from psutil import disk_partitions
    context = pyudev.Context()
    # Get all partitition devices
    devices = context.list_devices(subsystem='block', DEVTYPE='partition')
    # Filter down further to only those with Amazon as vendor
    devices = list(d for d in devices if d.properties.get('ID_VENDOR_ID') == '1949')
    kindles = []
    for device in devices:
        # Find related mountpoint by comparing /dev location with psutil
        point = next((d.mountpoint for d in disk_partitions() if d.device == device.properties.get('DEVNAME')), None)
        serial = device.properties.get('ID_SERIAL_SHORT')
        kindles.append(Kindle(serial, point))
    # Return a list of kindle objects
    return kindles


def login():
    """Present user challanges to generate a valid login with audible"""
    codes = ["uk", "us", "ca", "au", "fr", "de", "jp", "it", "in"]
    if DEBUG > 1:
        from creds import user, password, locale
    else:
        user = choice("Username: ")
        password = choice("Password: ", secret=True)
        locale = choice("Country Code (uk, us, ca, au, fr, de, jp, it, in): ", codes)

    return audible.LoginAuthenticator(user, password, locale=locale, captcha_callback=custom_captcha_callback)


def choice(prompt: str, item_list=[], secret=False) -> str:
    """Captures user input, repeating prompt if input not in item_list"""
    ret = None
    cmd = getpass if secret else input
    if len(item_list) > 0:
        while ret not in item_list:
            ret = cmd(prompt)
    else:
        while ret is None or ret == "":
            ret = cmd(prompt)
    return ret


def align_table(table: list) -> list:
    """Aligns each column in a list of lists.

    For each column, calculate the largest string in that column and
    pad each member such that their character count is identical (aligned).
    arguments:
    table -- A list of rows (containing list of strings)
    """
    # Flip list so that rows become columns for easier processing
    column_list = list(zip(*table))
    for i in range(len(column_list)):
        # Calculate max length for a given column
        max_length = max([len(r.expandtabs()) for r in column_list[i]])
        # overwrite column with padded members
        column_list[i] = [r.ljust(max_length, " ") for r in column_list[i]]
    # Flip list again to return rows to columns
    return list(zip(*column_list))


def generate_menu(object_list: list, menu_data: dict, display_index=False) -> None:
    """Builds and prints a menu out of a list of objects and passed data.

    arguments:
    object_list -- A list of objects
    menu_data -- A Dictionary whose Keys are Menu headings and whose values are
                 Object Properties to be extracted from each object passed in object_list
    display_index -- Indicates whether an index be displayed to the left of menu table"""
    table = []

    # Generate Heading row from keys in menu_data dict
    if display_index:
        table.append(["# ", *(k for k in menu_data)])
    else:
        table.append([k for k in menu_data])

    # Generate a row for each object, resolving properties defined in menu_data
    for i, item in enumerate(object_list):
        if display_index:
            table.append([f"{str(i + 1)} ", *(str(getattr(item, v)) for v in menu_data.values())])
        else:
            table.append([str(getattr(item, v)) for v in menu_data.values()])

    # Align columns in table
    table = align_table(table)

    for item in table:
        print(*item)


def prompt_user(object_list: list, menu_data: dict) -> object:
    """Present a prompt to select from items listed in a selection menu

    arguments:
    object_list -- A list of objects
    menu_data -- A Dictionary whose Keys are Menu headings and whose values are
                 Object Properties to be extracted from each object passed in object_list
    display_index -- Indicates whether an index be displayed to the left of menu table"""

    selected_object = None
    while selected_object is None:
        generate_menu(object_list, menu_data, True)
        response = input("Enter #: ")

        # Sanity check that user input is in range of list
        if response.isdigit() and int(response) - 1 in range(len(object_list)):
            selected_object = object_list[int(response) - 1]
        else:
            input("Please enter a value between 1 and {}.\nPress any key to continue.\n".format(len(object_list)))
    return selected_object


if __name__ == "__main__":
    DEBUG = 2
    kindle = []
    # Run auto detect if we are on linux (using udev)
    if platform == "linux" or platform == "linux2":
        kindle = auto_detect()

    # Build simple menu for kindle display
    kindle_menu = {'MODEL': 'model',
                   'SERIAL': 'serial',
                   'MOUNTED': 'is_mounted',
                   'ACTIVATED': 'is_activated'}

    if len(kindle) == 0:
        """ Create a dummy Kindle object from a provided serial if none were auto-detected """
        prompt = choice("No Kindles Detected.\nEnter Serial Number manually? (y/n) ", ["y", "n"])
        if prompt == "y":
            print("Serial Number can be obtained from Settings --> Device Info --> Serial Number on device.\n")
            valid_serial = None
            while valid_serial is None:
                serial = input("Enter Serial Number: ").replace(" ", "").upper()
                if len(serial) >= 16 and len(serial) < 20:
                    valid_serial = serial
            kindle = Kindle(valid_serial)
        else:
            exit(1)
    elif len(kindle) > 1:
        """ Prompt user to select desired kindle object if more than one auto-detected """
        print("Found multiple Kindles, please select:")
        kindle = prompt_user(kindle, kindle_menu)
    elif len(kindle) == 1:
        """ If only one device auto-detected then just use as is with no further prompts """
        print("Found Kindle:")
        generate_menu(kindle, kindle_menu)
        kindle = kindle[0]
    print()

    """ Main menu loop """
    prompt = None
    while prompt != "exit":
        # Build menu objects list for each desired action
        selection_menu = []

        selection_menu.append(MenuItem('activate', "Activate device (Will require login to Amazon)", ))
        if kindle.is_mounted and kindle.is_activated:
            selection_menu.append(MenuItem('device', "Save to Device", ))
        if kindle.is_activated:
            selection_menu.append(MenuItem('save', "Save to file",))
            selection_menu.append(MenuItem('print', "Print activation bytes"))
        selection_menu.append(MenuItem('exit', "Exit Program"))

        # Display menu and prompt user for a selection
        prompt = prompt_user(selection_menu, {'ACTION': 'action'}).prompt

        if prompt == "activate":
            """ Attempt to activate kindle """
            if kindle.is_activated:
                prompt = choice("Kindle appears to be activated.\nDo you want to ask audible for a new activation? (y/n) ",
                                ["y", "n"])
                if prompt == 'n':
                    continue
            kindle.activate(login())
            input("Kindle activated successfully (remember to save it).")
        elif prompt == "device":
            """ Save to Device """
            kindle.save()
            input("Saved to device! Audible content should now play without an activation prompt")
        elif prompt == "save":
            """ Save to location, providing hints for next steps """
            path = f"{os.path.dirname(os.path.realpath(__file__))}/{kindle.serial}"
            location = f"{path}/AudibleActivation.sys"
            if not os.path.exists(path):
                os.makedirs(path)
            user_location = input(f"Enter Location (Default ./{kindle.serial}/AudibleActivation.sys): ")
            if user_location != "":
                location = user_location
            if kindle.save(location):
                input(f"Saved to {location}.\n\nThis file can now be placed manually under KINDLEROOT:/system/AudibleActivation.sys")
        elif prompt == "print":
            """ Print activation bytes """
            input(f"Activation Bytes: {kindle.bytes}")
            print()
