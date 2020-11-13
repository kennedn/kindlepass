#!/usr/bin/env python
import os
from tempfile import mkstemp
import struct
import Audible.src.audible as audible
import httpx
import subprocess as shell
from datetime import datetime
from getpass import getpass
from sys import platform


class MenuItem:
    def __init__(self, prompt, action):
        self.action = action
        self.prompt = prompt


class Kindle:
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

    def __init__(self, serial, mountpoint=None):
        self.serial = serial
        self.mountpoint = mountpoint
        self.remote_file = "/system/AudibleActivation.sys"
        self.activation = None
        self.local_activate()
        if self.default is None:
            Kindle.default = self

    def local_activate(self):
        if self.is_mounted and self.remote_file_exists and os.stat(self.filepath).st_size == 0x237:
            with open(self.filepath, 'rb') as activation:
                a = activation.read()
            if (a.find(self.serial.encode())):
                self.activation = a

    def activate(self, auth):
        self.activation = auth.get_activation(self.serial)[-0x237:]

    def save(self, location=None):
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
        if self.is_activated:
            return struct.pack('>I', struct.unpack('<I', self.activation[:4])[0]).hex()
        else:
            return None

    @property
    def model(self):
        return Kindle.model_lookup.get(self.serial[:4], "Unknown")


def custom_captcha_callback(captcha_url):
    captcha = httpx.get(captcha_url).content
    if shell.check_output(["which", "eog"]):
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


def auto_detect():
    import pyudev
    from psutil import disk_partitions
    context = pyudev.Context()
    devices = context.list_devices(subsystem='block', DEVTYPE='partition')
    devices = list(d for d in devices if d.properties.get('ID_VENDOR_ID') == '1949')
    kindles = []
    for device in devices:
        point = next((d.mountpoint for d in disk_partitions() if d.device == device.properties.get('DEVNAME')), None)
        serial = device.properties.get('ID_SERIAL_SHORT')
        kindles.append(Kindle(serial, point))
    return kindles


def login():
    auth = None
    token_path = f"{os.path.dirname(os.path.realpath(__file__))}/.auth.token"

    if os.path.isfile(token_path):
        auth = audible.FileAuthenticator(token_path)
        if auth.expires > datetime.now().timestamp():
            return auth
    if DEBUG > 1:
        from creds import *
    else:
        user = choice("Username: ")
        password = choice("Password: ", secret=True)
        codes = ["uk", "us", "ca", "au", "fr", "de", "jp", "it", "in"]
        locale = choice("Country Code (uk, us, ca, au, fr, de, jp, it, in): ", codes)

    # Login normally if token login failed
    auth = audible.LoginAuthenticator(user, password, locale=locale, captcha_callback=custom_captcha_callback)
    auth.to_file(token_path)
    return auth


def choice(prompt, item_list=[], secret=False):
    ret = None
    cmd = getpass if secret else input
    if len(item_list) > 0:
        while ret not in item_list:
            ret = cmd(prompt)
    else:
        while ret is None or ret == "":
            ret = cmd(prompt)
    return ret


def maximize_list(item_list):
    column_list = list(zip(*item_list))
    for i in range(len(column_list)):
        max_length = max([len(r.expandtabs()) for r in column_list[i]])
        column_list[i] = [r.ljust(max_length, " ") for r in column_list[i]]
    return list(zip(*column_list))


# Generates a pretty menu
def generate_menu(item_list, menu_data, display_index=False):
    items = []

    if display_index:
        items.append(["# ", *(k for k in menu_data)])
    else:
        items.append([k for k in menu_data])

    for i, item in enumerate(item_list):
        if display_index:
            items.append([f"{str(i + 1)} ", *(str(getattr(item, v)) for v in menu_data.values())])
        else:
            items.append([str(getattr(item, v)) for v in menu_data.values()])

    items = maximize_list(items)

    for item in items:
        print(*item)


# Attempt to derive a sink object by prompting user with interactive menu
def prompt_user(kindle_list, menu_data):
    selection = None
    # Rerun until we have a sink
    while selection is None:
        # print a list of sinks and prompt for a selection
        generate_menu(kindle_list, menu_data, True)
        response = input("Enter #: ")

        # If the selection is valid, set the sink object
        if response.isdigit() and int(response) - 1 in range(len(kindle_list)):
            selection = kindle_list[int(response) - 1]
        else:
            # Print error before repeat
            input("Please enter a value between 1 and {}.\nPress any key to continue.\n".format(len(kindle_list)))
    return selection


if __name__ == "__main__":
    DEBUG = 2
    kindle = []
    if platform == "linux" or platform == "linux2":
        kindle = auto_detect()

    kindle_menu = {'MODEL': 'model',
                   'SERIAL': 'serial',
                   'MOUNTED': 'is_mounted',
                   'ACTIVATED': 'is_activated'}

    if len(kindle) == 0:
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
        print("Found multiple Kindles, please select:")
        kindle = prompt_user(kindle, kindle_menu)
    elif len(kindle) == 1:
        print("Found Kindle:")
        generate_menu(kindle, kindle_menu)
        kindle = kindle[0]
    print()

    prompt = None
    while prompt != "exit":
        selection_menu = []
        selection_menu.append(MenuItem('activate', "Activate device", ))
        if kindle.is_mounted and kindle.is_activated:
            selection_menu.append(MenuItem('device', "Save to Device", ))
        if kindle.is_activated:
            selection_menu.append(MenuItem('save', "Save to file",))
            selection_menu.append(MenuItem('print', "Print activation bytes"))
        selection_menu.append(MenuItem('exit', "Exit Program"))

        prompt = prompt_user(selection_menu, {'ACTION': 'action'}).prompt
        if prompt == "device":
            kindle.save()
            input("Saved to device")
        if prompt == "activate":
            if kindle.is_activated:
                prompt = choice("Kindle appears to be activated.\nDo you want to ask audible for a new activation? (y/n) ",
                                ["y", "n"])
                if prompt == 'n':
                    continue
            kindle.activate(login())
            input("Kindle activated successfully (remember to save it).")
        elif prompt == "save":
            path = f"{os.path.dirname(os.path.realpath(__file__))}/{kindle.serial}"
            location = f"{path}/AudibleActivation.sys"
            if not os.path.exists(path):
                os.makedirs(path)
            user_location = input(f"Enter Location (Default ./{kindle.serial}/AudibleActivation.sys): ")
            if user_location != "":
                location = user_location
            if kindle.save(location):
                input(f"Saved to {location}.\nThis file can now be placed manually under KINDLEROOT:/system/AudibleActivation.sys")
        elif prompt == "print":
            input(f"Activation Bytes: {kindle.bytes}")
            print()
