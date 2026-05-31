"""Hardware device probing — detects connected joysticks and their capabilities."""

import platform
from dataclasses import dataclass, field


@dataclass
class DeviceInfo:
    """Information about a connected joystick device."""
    name: str = ""
    path: str = ""
    num_buttons: int = 0
    num_axes: int = 0
    axes: list[dict[str, str]] = field(default_factory=list)  # [{id, description}]
    vendor_id: str = ""
    product_id: str = ""


def list_devices() -> list[DeviceInfo]:
    """List connected joystick devices with their capabilities."""
    system = platform.system()
    if system == "Linux":
        return _list_devices_linux()
    elif system == "Windows":
        return _list_devices_windows()
    else:
        raise RuntimeError(f"Device probing not supported on {system}")


def _list_devices_linux() -> list[DeviceInfo]:
    """Probe joystick devices on Linux via /dev/input/js* ioctl."""
    import struct
    import fcntl
    import os
    import glob

    # ioctl constants for joystick API
    JSIOCGAXES = 0x80016A11
    JSIOCGBUTTONS = 0x80016A12
    JSIOCGNAME = lambda length: 0x80006A13 + (length << 16)
    JSIOCGAXMAP = 0x80406A32

    # Standard Linux axis names
    AXIS_NAMES = {
        0x00: "X", 0x01: "Y", 0x02: "Z",
        0x03: "RX", 0x04: "RY", 0x05: "RZ",
        0x06: "Throttle", 0x07: "Rudder",
        0x08: "Wheel", 0x09: "Gas", 0x0A: "Brake",
        0x10: "HAT0X", 0x11: "HAT0Y",
        0x12: "HAT1X", 0x13: "HAT1Y",
        0x14: "HAT2X", 0x15: "HAT2Y",
        0x16: "HAT3X", 0x17: "HAT3Y",
        0x28: "Misc",
    }

    devices = []
    for js_path in sorted(glob.glob("/dev/input/js*")):
        try:
            fd = os.open(js_path, os.O_RDONLY | os.O_NONBLOCK)
            try:
                # Get device name
                name_buf = bytearray(256)
                fcntl.ioctl(fd, JSIOCGNAME(256), name_buf)
                name = name_buf.split(b'\x00', 1)[0].decode('utf-8', errors='replace')

                # Get axis count
                buf = bytearray(1)
                fcntl.ioctl(fd, JSIOCGAXES, buf)
                num_axes = buf[0]

                # Get button count
                fcntl.ioctl(fd, JSIOCGBUTTONS, buf)
                num_buttons = buf[0]

                # Get axis map
                axmap_buf = bytearray(64)
                fcntl.ioctl(fd, JSIOCGAXMAP, axmap_buf)
                axes = []
                for i in range(num_axes):
                    ax_id = axmap_buf[i]
                    ax_name = AXIS_NAMES.get(ax_id, f"ABS_{ax_id:#04x}")
                    axes.append({"id": f"JOY_AXIS_{ax_name}", "description": ax_name})

                # Get vendor/product from sysfs
                vendor_id = ""
                product_id = ""
                js_num = js_path.split("js")[-1]
                sysfs_path = f"/sys/class/input/js{js_num}/device/id"
                if os.path.isdir(sysfs_path):
                    try:
                        with open(f"{sysfs_path}/vendor") as f:
                            vendor_id = f.read().strip()
                        with open(f"{sysfs_path}/product") as f:
                            product_id = f.read().strip()
                    except OSError:
                        pass

                devices.append(DeviceInfo(
                    name=name,
                    path=js_path,
                    num_buttons=num_buttons,
                    num_axes=num_axes,
                    axes=axes,
                    vendor_id=vendor_id,
                    product_id=product_id,
                ))
            finally:
                os.close(fd)
        except OSError:
            continue

    return devices


def _list_devices_windows() -> list[DeviceInfo]:
    """Probe joystick devices on Windows via DirectInput/WinMM."""
    import ctypes
    from ctypes import wintypes

    # Use winmm.dll for basic joystick enumeration
    winmm = ctypes.WinDLL('winmm', use_last_error=True)

    MAXPNAMELEN = 32

    class JOYCAPS(ctypes.Structure):
        _fields_ = [
            ("wMid", wintypes.WORD),
            ("wPid", wintypes.WORD),
            ("szPname", ctypes.c_char * MAXPNAMELEN),
            ("wXmin", wintypes.UINT),
            ("wXmax", wintypes.UINT),
            ("wYmin", wintypes.UINT),
            ("wYmax", wintypes.UINT),
            ("wZmin", wintypes.UINT),
            ("wZmax", wintypes.UINT),
            ("wNumButtons", wintypes.UINT),
            ("wPeriodMin", wintypes.UINT),
            ("wPeriodMax", wintypes.UINT),
            ("wRmin", wintypes.UINT),
            ("wRmax", wintypes.UINT),
            ("wUmin", wintypes.UINT),
            ("wUmax", wintypes.UINT),
            ("wVmin", wintypes.UINT),
            ("wVmax", wintypes.UINT),
            ("wCaps", wintypes.UINT),
            ("wMaxAxes", wintypes.UINT),
            ("wNumAxes", wintypes.UINT),
            ("wMaxButtons", wintypes.UINT),
            ("szRegKey", ctypes.c_char * MAXPNAMELEN),
            ("szOEMVxD", ctypes.c_char * MAXPNAMELEN),
        ]

    JOYERR_NOERROR = 0
    joyGetNumDevs = winmm.joyGetNumDevs
    joyGetDevCapsA = winmm.joyGetDevCapsA

    num_devs = joyGetNumDevs()
    devices = []

    # Standard axis names for Windows joystick positions
    WIN_AXES = ["X", "Y", "Z", "R", "U", "V"]

    for joy_id in range(num_devs):
        caps = JOYCAPS()
        result = joyGetDevCapsA(joy_id, ctypes.byref(caps), ctypes.sizeof(JOYCAPS))
        if result != JOYERR_NOERROR:
            continue

        name = caps.szPname.decode('utf-8', errors='replace').rstrip('\x00')
        if not name:
            continue

        axes = []
        for i in range(min(caps.wNumAxes, len(WIN_AXES))):
            ax_name = WIN_AXES[i]
            axes.append({"id": f"JOY_{ax_name}", "description": ax_name})

        devices.append(DeviceInfo(
            name=name,
            path=f"joystick:{joy_id}",
            num_buttons=caps.wNumButtons,
            num_axes=caps.wNumAxes,
            axes=axes,
            vendor_id=f"{caps.wMid:#06x}",
            product_id=f"{caps.wPid:#06x}",
        ))

    return devices
