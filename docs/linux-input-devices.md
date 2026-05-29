# Linux Input Device Summary

System: Nobara 43, Kernel 7.0.9-200.nobara.fc43.x86_64

## Devices

| js# | Event | Name | VID:PID | Buttons | Axes |
|-----|-------|------|---------|---------|------|
| js0 | event30 | VIRPIL Controls 20260105 VPC Rudder Pedals | 3344:01f8 | 0 | 3 |
| js1 | event31 | Winwing WINCTRL Orion Throttle Base II + F18 HANDLE | 4098:be62 | 80 | 8 |
| js2 | event256 | Winwing WINCTRL Orion Joystick Base Metal 2 + JGRIP-F16 | 4098:bea8 | 42 | 8 |

---

## Stick — Winwing WINCTRL Orion Joystick Base Metal 2 + JGRIP-F16

Product ID: 0xbea8

### Buttons (42 total)

| jstest index | evtest code | evtest name | DCS ID |
|---|---|---|---|
| 0 | 288 | BTN_TRIGGER | JOY_BTN1 |
| 1 | 289 | BTN_THUMB | JOY_BTN2 |
| 2 | 290 | BTN_THUMB2 | JOY_BTN3 |
| 3 | 291 | BTN_TOP | JOY_BTN4 |
| 4 | 292 | BTN_TOP2 | JOY_BTN5 |
| 5 | 293 | BTN_PINKIE | JOY_BTN6 |
| 6 | 294 | BTN_BASE | JOY_BTN7 |
| 7 | 295 | BTN_BASE2 | JOY_BTN8 |
| 8 | 296 | BTN_BASE3 | JOY_BTN9 |
| 9 | 297 | BTN_BASE4 | JOY_BTN10 |
| 10 | 298 | BTN_BASE5 | JOY_BTN11 |
| 11 | 299 | BTN_BASE6 | JOY_BTN12 |
| 12 | 300 | ? | JOY_BTN13 |
| 13 | 301 | ? | JOY_BTN14 |
| 14 | 302 | ? | JOY_BTN15 |
| 15 | 303 | BTN_DEAD | JOY_BTN16 |
| 16 | 704 | BTN_TRIGGER_HAPPY1 | JOY_BTN17 |
| 17 | 705 | BTN_TRIGGER_HAPPY2 | JOY_BTN18 |
| 18 | 706 | BTN_TRIGGER_HAPPY3 | JOY_BTN19 |
| 19 | 707 | BTN_TRIGGER_HAPPY4 | JOY_BTN20 |
| 20 | 708 | BTN_TRIGGER_HAPPY5 | JOY_BTN21 |
| 21 | 709 | BTN_TRIGGER_HAPPY6 | JOY_BTN22 |
| 22 | 710 | BTN_TRIGGER_HAPPY7 | JOY_BTN23 |
| 23 | 711 | BTN_TRIGGER_HAPPY8 | JOY_BTN24 |
| 24 | 712 | BTN_TRIGGER_HAPPY9 | JOY_BTN25 |
| 25 | 713 | BTN_TRIGGER_HAPPY10 | JOY_BTN26 |
| 26 | 714 | BTN_TRIGGER_HAPPY11 | JOY_BTN27 |
| 27 | 715 | BTN_TRIGGER_HAPPY12 | JOY_BTN28 |
| 28 | 716 | BTN_TRIGGER_HAPPY13 | JOY_BTN29 |
| 29 | 717 | BTN_TRIGGER_HAPPY14 | JOY_BTN30 |
| 30 | 718 | BTN_TRIGGER_HAPPY15 | JOY_BTN31 |
| 31 | 719 | BTN_TRIGGER_HAPPY16 | JOY_BTN32 |
| 32 | 720 | BTN_TRIGGER_HAPPY17 | JOY_BTN33 |
| 33 | 721 | BTN_TRIGGER_HAPPY18 | JOY_BTN34 |
| 34 | 722 | BTN_TRIGGER_HAPPY19 | JOY_BTN35 |
| 35 | 723 | BTN_TRIGGER_HAPPY20 | JOY_BTN36 |
| 36 | 724 | BTN_TRIGGER_HAPPY21 | JOY_BTN37 |
| 37 | 725 | BTN_TRIGGER_HAPPY22 | JOY_BTN38 |
| 38 | 726 | BTN_TRIGGER_HAPPY23 | JOY_BTN39 |
| 39 | 727 | BTN_TRIGGER_HAPPY24 | JOY_BTN40 |
| 40 | 728 | BTN_TRIGGER_HAPPY25 | JOY_BTN41 |
| 41 | 729 | BTN_TRIGGER_HAPPY26 | JOY_BTN42 |

### Axes (8 total)

| Axis | evtest code | evtest name | Range | Notes |
|---|---|---|---|---|
| 0 | 0 | ABS_X | 0–65535 | Stick Roll |
| 1 | 1 | ABS_Y | 0–65535 | Stick Pitch |
| 2 | 3 | ABS_RX | 0–4095 | Mini-joystick X |
| 3 | 4 | ABS_RY | 0–4095 | Mini-joystick Y |
| 4 | 5 | ABS_RZ | 0–4095 | |
| 5 | 6 | ABS_THROTTLE | 0–4095 | |
| 6 | 16 | ABS_HAT0X | -1 to 1 | POV Hat X |
| 7 | 17 | ABS_HAT0Y | -1 to 1 | POV Hat Y |

### Notes
- The stick has one POV hat reported as axes (HAT0X/HAT0Y). DCS maps this to `JOY_BTN_POV1_U/D/L/R`.
- All other hats are reported as regular buttons.
- The stick does NOT use the winwing kernel module (product 0xbea8 is not in the module's device table). It uses the generic HID joystick driver.

---

## Throttle — Winwing WINCTRL Orion Throttle Base II + F18 HANDLE

Product ID: 0xbe62 (TGRIP-18, handled by winwing kernel module)

### Buttons (80 total)

| jstest index | evtest code | evtest name | DCS ID |
|---|---|---|---|
| 0 | 288 | BTN_TRIGGER | JOY_BTN1 |
| 1 | 289 | BTN_THUMB | JOY_BTN2 |
| 2 | 290 | BTN_THUMB2 | JOY_BTN3 |
| 3 | 291 | BTN_TOP | JOY_BTN4 |
| 4 | 292 | BTN_TOP2 | JOY_BTN5 |
| 5 | 293 | BTN_PINKIE | JOY_BTN6 |
| 6 | 294 | BTN_BASE | JOY_BTN7 |
| 7 | 295 | BTN_BASE2 | JOY_BTN8 |
| 8 | 296 | BTN_BASE3 | JOY_BTN9 |
| 9 | 297 | BTN_BASE4 | JOY_BTN10 |
| 10 | 298 | BTN_BASE5 | JOY_BTN11 |
| 11 | 299 | BTN_BASE6 | JOY_BTN12 |
| 12 | 300 | ? | JOY_BTN13 |
| 13 | 301 | ? | JOY_BTN14 |
| 14 | 302 | ? | JOY_BTN15 |
| 15 | 303 | BTN_DEAD | JOY_BTN16 |
| 16 | 704 | BTN_TRIGGER_HAPPY1 | JOY_BTN17 |
| 17 | 705 | BTN_TRIGGER_HAPPY2 | JOY_BTN18 |
| 18 | 706 | BTN_TRIGGER_HAPPY3 | JOY_BTN19 |
| 19 | 707 | BTN_TRIGGER_HAPPY4 | JOY_BTN20 |
| 20 | 708 | BTN_TRIGGER_HAPPY5 | JOY_BTN21 |
| 21 | 709 | BTN_TRIGGER_HAPPY6 | JOY_BTN22 |
| 22 | 710 | BTN_TRIGGER_HAPPY7 | JOY_BTN23 |
| 23 | 711 | BTN_TRIGGER_HAPPY8 | JOY_BTN24 |
| 24 | 712 | BTN_TRIGGER_HAPPY9 | JOY_BTN25 |
| 25 | 713 | BTN_TRIGGER_HAPPY10 | JOY_BTN26 |
| 26 | 714 | BTN_TRIGGER_HAPPY11 | JOY_BTN27 |
| 27 | 715 | BTN_TRIGGER_HAPPY12 | JOY_BTN28 |
| 28 | 716 | BTN_TRIGGER_HAPPY13 | JOY_BTN29 |
| 29 | 717 | BTN_TRIGGER_HAPPY14 | JOY_BTN30 |
| 30 | 718 | BTN_TRIGGER_HAPPY15 | JOY_BTN31 |
| 31 | 719 | BTN_TRIGGER_HAPPY16 | JOY_BTN32 |
| 32 | 720 | BTN_TRIGGER_HAPPY17 | JOY_BTN33 |
| 33 | 721 | BTN_TRIGGER_HAPPY18 | JOY_BTN34 |
| 34 | 722 | BTN_TRIGGER_HAPPY19 | JOY_BTN35 |
| 35 | 723 | BTN_TRIGGER_HAPPY20 | JOY_BTN36 |
| 36 | 724 | BTN_TRIGGER_HAPPY21 | JOY_BTN37 |
| 37 | 725 | BTN_TRIGGER_HAPPY22 | JOY_BTN38 |
| 38 | 726 | BTN_TRIGGER_HAPPY23 | JOY_BTN39 |
| 39 | 727 | BTN_TRIGGER_HAPPY24 | JOY_BTN40 |
| 40 | 728 | BTN_TRIGGER_HAPPY25 | JOY_BTN41 |
| 41 | 729 | BTN_TRIGGER_HAPPY26 | JOY_BTN42 |
| 42 | 730 | BTN_TRIGGER_HAPPY27 | JOY_BTN43 |
| 43 | 731 | BTN_TRIGGER_HAPPY28 | JOY_BTN44 |
| 44 | 732 | BTN_TRIGGER_HAPPY29 | JOY_BTN45 |
| 45 | 733 | BTN_TRIGGER_HAPPY30 | JOY_BTN46 |
| 46 | 734 | BTN_TRIGGER_HAPPY31 | JOY_BTN47 |
| 47 | 735 | BTN_TRIGGER_HAPPY32 | JOY_BTN48 |
| 48 | 736 | BTN_TRIGGER_HAPPY33 | JOY_BTN49 |
| 49 | 737 | BTN_TRIGGER_HAPPY34 | JOY_BTN50 |
| 50 | 738 | BTN_TRIGGER_HAPPY35 | JOY_BTN51 |
| 51 | 739 | BTN_TRIGGER_HAPPY36 | JOY_BTN52 |
| 52 | 740 | BTN_TRIGGER_HAPPY37 | JOY_BTN53 |
| 53 | 741 | BTN_TRIGGER_HAPPY38 | JOY_BTN54 |
| 54 | 742 | BTN_TRIGGER_HAPPY39 | JOY_BTN55 |
| 55 | 743 | BTN_TRIGGER_HAPPY40 | JOY_BTN56 |
| 56 | 744 | ? | JOY_BTN57 |
| 57 | 745 | ? | JOY_BTN58 |
| 58 | 746 | ? | JOY_BTN59 |
| 59 | 747 | ? | JOY_BTN60 |
| 60 | 748 | ? | JOY_BTN61 |
| 61 | 749 | ? | JOY_BTN62 |
| 62 | 750 | ? | JOY_BTN63 |
| 63 | 751 | ? | JOY_BTN64 |
| 64 | 752 | ? | JOY_BTN65 |
| 65 | 753 | ? | JOY_BTN66 |
| 66 | 754 | ? | JOY_BTN67 |
| 67 | 755 | ? | JOY_BTN68 |
| 68 | 756 | ? | JOY_BTN69 |
| 69 | 757 | ? | JOY_BTN70 |
| 70 | 758 | ? | JOY_BTN71 |
| 71 | 759 | ? | JOY_BTN72 |
| 72 | 760 | ? | JOY_BTN73 |
| 73 | 761 | ? | JOY_BTN74 |
| 74 | 762 | ? | JOY_BTN75 |
| 75 | 763 | ? | JOY_BTN76 |
| 76 | 764 | ? | JOY_BTN77 |
| 77 | 765 | ? | JOY_BTN78 |
| 78 | 766 | ? | JOY_BTN79 |
| 79 | 767 | ? | JOY_BTN80 |

### Axes (8 total)

| Axis | evtest code | evtest name | Range | Notes |
|---|---|---|---|---|
| 0 | 0 | ABS_X | 0–4095 | |
| 1 | 1 | ABS_Y | 0–4095 | |
| 2 | 2 | ABS_Z | 0–4095 | |
| 3 | 3 | ABS_RX | 0–65535 | |
| 4 | 4 | ABS_RY | 0–65535 | |
| 5 | 5 | ABS_RZ | 0–65535 | |
| 6 | 6 | ABS_THROTTLE | 0–65535 | |
| 7 | 7 | ABS_RUDDER | 0–65535 | |

### Notes
- Product 0xbe62 = TGRIP-18 grip, handled by the winwing kernel module.
- Kernel module mapping (from `hid-winwing2.c`, `grip_buttons=31`):
  - Hardware buttons 0–15 → event codes 288–303 (BTN_JOYSTICK range) → DCS JOY_BTN1–16
  - Hardware buttons 16–31 → event codes 704–719 (BTN_TRIGGER_HAPPY1–16) → DCS JOY_BTN17–32
  - Hardware buttons 64–110 → event codes 720–766 (BTN_TRIGGER_HAPPY17–63) → DCS JOY_BTN33–79
- No POV hats on this device.

---

## Rudder Pedals — VIRPIL Controls 20260105 VPC Rudder Pedals

Product ID: 3344:01f8

### Buttons
None.

### Axes (3 total)

| Axis | evtest code | evtest name | Range | Notes |
|---|---|---|---|---|
| 0 | 2 | ABS_Z | 0–60000 | |
| 1 | 6 | ABS_THROTTLE | 0–60000 | |
| 2 | 7 | ABS_RUDDER | 0–60000 | |

---

## DCS Button ID Mapping

DCS (via Proton/Wine) uses the jstest button index + 1 for `JOY_BTN` numbering:

```
JOY_BTN<N> = jstest button index (N-1)
```

The POV hat on the stick (HAT0X/HAT0Y) is mapped by DCS to:
- `JOY_BTN_POV1_U` (hat Y = -1)
- `JOY_BTN_POV1_D` (hat Y = +1)
- `JOY_BTN_POV1_L` (hat X = -1)
- `JOY_BTN_POV1_R` (hat X = +1)
- `JOY_BTN_POV1_UL`, `JOY_BTN_POV1_UR`, `JOY_BTN_POV1_DL`, `JOY_BTN_POV1_DR` (diagonals)
