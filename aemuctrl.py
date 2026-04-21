import subprocess
import time
import os
import re
import cv2
import pyautogui
import numpy as np
from typing import List, Optional

# ================== CONFIGURATION ==================
ADB_PATH = "adb"  # Ensure this is in your System PATH
FAILSAFE = False
__version__ = "0.1.5"

COMMON_PORTS = [
    5554, 5555, 5556, 5557,   # Generic / BlueStacks
    62001, 62025,             # Nox
    21503, 21513,             # MeMu
    7555,                     # Genymotion / MuMu
]

type ImageCroppingCoords = tuple[int,int,int,int]
type ColorRGB = tuple[int,int,int]

# ================== CORE EXECUTION ==================

def _run(cmd: str, wait: float = 0) -> str:
    """Executes an ADB command and returns stdout."""
    try:
        result = subprocess.run(
            f'{ADB_PATH} {cmd}',
            shell=True,
            capture_output=True,
            text=True
        )
        if wait > 0:
            time.sleep(wait)
        if result.stderr:
            print(f"ADB ERROR: {result.stderr.strip()}")
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {str(e)}"

# ================== CONNECTION ==================

def connect( ip="127.0.0.1", port=5555):
    """
    Connects to a specific ADB device.
    """
    return _run(f"connect {ip}:{port}")

def disconnect():
    """
    Disconnects all ADB devices.
    """
    return _run("disconnect")


def discover_services() -> List[str]:
    """
    Uses ADB mDNS to find active ADB services on the network/local machine.
    Returns a list of 'IP:PORT' strings.
    """
    output = _run("mdns services")
    # Regex to find patterns like 127.0.0.1:5555
    pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}:\d+\b'
    services = re.findall(pattern, output)
    return list(set(services))

def get_connected_devices() -> List[str]:
    """Returns a list of currently connected device IDs."""
    out = _run("devices")
    lines = out.splitlines()
    return [line.split("\t")[0] for line in lines if "\tdevice" in line]

def smart_connect() -> Optional[str]:
    """
    The 'Brain' of the connection:
    1. Checks for already active connections.
    2. Uses mDNS to discover services automatically.
    3. Falls back to scanning common emulator ports if discovery fails.
    """
    print("🔍 [SmartConnect] Checking existing connections...")
    active = get_connected_devices()
    if active:
        print(f"✅ Already connected to: {active[0]}")
        return active[0]

    print("📡 [SmartConnect] Discovering ADB services via mDNS...")
    services = discover_services()
    if services:
        for service in services:
            print(f"🔗 Found service! Attempting to connect: {service}")
            _run(f"connect {service}")
            time.sleep(0.5)
            if get_connected_devices():
                return service

    print("⚠️ [SmartConnect] No services found. Using fallback port scan...")
    for port in COMMON_PORTS:
        target = f"127.0.0.1:{port}"
        _run(f"connect {target}")
        if get_connected_devices():
            print(f"🎯 Connected to fallback: {target}")
            return target

    print("❌ [SmartConnect] Failed to find any device.")
    return None

def disconnect():
    """Disconnects all ADB devices."""
    return _run("disconnect")

# ================== INTERACTION ==================

def tap(x: int, y: int, wait: float = 0):
    """Taps the screen at (x, y)."""
    return _run(f"shell input tap {x} {y}", wait)

def hold_tap(x: int, y: int, wait: float = 0,duration=1000):
    swipe(x,y,x,y,duration)
    if wait > 0: time.sleep(wait)

def hold_or_tap(x: int, y: int, hold:bool= False,wait: float = 0,hold_duration=1000):
    hold_tap(x,y,wait,hold_duration) if hold else tap(x,y,wait)
    if wait > 0: time.sleep(wait)

def swipe(x1, y1, x2, y2, duration=300, wait=0):
    """Swipes from point A to point B."""
    return _run(f"shell input swipe {x1} {y1} {x2} {y2} {duration}", wait)

def text(msg: str, wait: float = 0):
    """Inputs text safely (replaces spaces with %s)."""
    safe = msg.replace(" ", "%s")
    return _run(f'shell input text "{safe}"', wait)

def press_key(keycode: str, wait: float = 0):
    """Sends a specific key event."""
    return _run(f"shell input keyevent {keycode}", wait)

def home(wait=0): return press_key("KEYCODE_HOME", wait)
def back(wait=0): return press_key("KEYCODE_BACK", wait)
def recent(wait=0): return press_key("KEYCODE_APP_SWITCH", wait)

# ================== APPS ==================

def list_apps(wait: float = 0):
    """Launches an app by package name."""
    return _run("shell pm list packages -3", wait)

def open_app(package: str, wait: float = 0):
    """Launches an app by package name."""
    return _run(f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1", wait)

def close_app(package: str, wait: float = 0):
    """Force-stops an app."""
    return _run(f"shell am force-stop {package}", wait)

# ================== SCREENSHOT ==================

def screenshot(path: str = "screen.png", wait: float = 0) -> str:
    """Takes a screenshot using exec-out (fast)."""
    with open(path, "wb") as f:
        subprocess.run(f'{ADB_PATH} exec-out screencap -p', shell=True, stdout=f)
    if wait > 0: time.sleep(wait)
    return path

def crop_screenshot(coords:ImageCroppingCoords,path:str):
    """Crop a screenshot."""
    x1, y1, x2, y2 = coords
    img = cv2.imread(path)
    return img[y1:y2, x1:x2]

def save_crop_screenshot(coords:ImageCroppingCoords,path:str,saved_path:str):
    """Save a cropped screenshot."""
    cv2.imwrite(saved_path, crop_screenshot(coords,path))
    return saved_path

def screencap(coords:ImageCroppingCoords, path="crop.png"):
    """Takes a screenshot and crop it."""
    temp_img_name="bro_don't_delete_me.png"
    cv2.imwrite(path, crop_screenshot(coords,screenshot(temp_img_name)))
    if os.path.exists(temp_img_name) : os.remove(temp_img_name)
    return path

# ================== VISUAL ==================

def __get_dominant_color_from_rgb_array(a):
    """Return a tuple with RGB value of the dominant color in image"""
    a2D = a.reshape(-1,a.shape[-1])
    col_range = (256, 256, 256) # generically : a2D.max(0)+1
    a1D = np.ravel_multi_index(a2D.T, col_range)
    return tuple(map(int, np.unravel_index(np.bincount(a1D).argmax(), col_range)))

def locate_on_screen_and_tap_on_center(template_path: str, confidence: float = 0.8,croppedCoords:ImageCroppingCoords | None = None,force_img_path:str | None = None ):
    """Finds image on screen and taps its center if confidence is high enough."""
    success, coords = locate_image_on_screen(template_path,confidence,croppedCoords,force_img_path)
    if success != False:
        x, y = coords
        tap(x, y)
    return success

def locate_image_on_screen(template_path: str, confidence: float = 0.8,croppedCoords:ImageCroppingCoords | None = None,force_img_path:str | None = None):
    """Finds image on screen and give its center if confidence is high enough."""
    if force_img_path == None:
        temp_img_name="temp_view.png"
        img_path = screenshot(temp_img_name) if croppedCoords == None else screencap(croppedCoords,temp_img_name)
        time.sleep(0.1)
        img = cv2.imread(img_path)
        if os.path.exists(img_path): os.remove(img_path)
        time.sleep(0.2)
    else:
        img = cv2.imread(force_img_path)
    template = cv2.imread(template_path)
    if img is None or template is None:
        return False, None

    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= confidence:
        h, w, _ = template.shape
        cx = max_loc[0] + (w // 2)
        cy = max_loc[1] + (h // 2)
        return True, (cx, cy)
    return False, None
    
def get_image_color_from_path(image_path: str):
    return get_image_color_from_image(cv2.imread(image_path))

def get_image_color_from_image(image: cv2.MatLike | None):
    return __get_dominant_color_from_rgb_array(image[...,::-1])
    
def get_color_on_screen(croppedCoords:ImageCroppingCoords):
    return get_image_color_from_path(screencap(croppedCoords,"temp_get_color_on_screen.png"))

def get_color_from_image(croppedCoords:ImageCroppingCoords,image_path: str):
    return get_image_color_from_image(crop_screenshot(croppedCoords,image_path))

def compare_two_colors(current_color: ColorRGB,compared_color:ColorRGB):
    return np.array_equal(current_color,compared_color)

def compare_color_on_screen(compared_color: ColorRGB,croppedCoords:ImageCroppingCoords):
    """Finds the dominant color on screen and compare it with a known color."""
    temp_img_name="temp_crop.png"
    img_path = screencap(croppedCoords,temp_img_name)
    current_color = get_image_color_from_path(temp_img_name)
    if os.path.exists(temp_img_name): os.remove(img_path)
    return compare_two_colors(current_color,compared_color)

def compare_color_on_screen_and_tap(compared_color: ColorRGB,croppedCoords:ImageCroppingCoords,on_same:bool=True):
    """Finds the dominant color on screen and compare it with a known color and tap on its center if bool equals."""
    return compare_color_on_screen_and_tap_or_hold(compared_color,croppedCoords,on_same,False)

def compare_color_on_screen_and_hold(compared_color: ColorRGB,croppedCoords:ImageCroppingCoords,on_same:bool=True,hold_duration:int|None=None):
    """Finds the dominant color on screen and compare it with a known color and hold on its center if bool equals."""
    return compare_color_on_screen_and_tap_or_hold(compared_color,croppedCoords,on_same,True,hold_duration)

def compare_color_on_screen_and_tap_or_hold(compared_color: ColorRGB,croppedCoords:ImageCroppingCoords,on_same:bool=True,hold:bool=False,hold_duration:int|None=None):
    """Finds the dominant color on screen and compare it with a known color and tap or hold on its center if bool equals."""
    temp_img_name="compare_color_on_screen_and_tap_or_hold.png"
    img_path = screenshot(temp_img_name)
    compare_result = compare_color_from_screenshot_and_tap_or_hold(compared_color,croppedCoords,img_path,on_same,hold,hold_duration)
    if os.path.exists(temp_img_name): os.remove(img_path)
    return compare_result


def compare_color_from_screenshot_and_tap(compared_color: ColorRGB,croppedCoords:ImageCroppingCoords,force_img_path:str,on_same:bool=True):
    """Finds the dominant color from screenshot and compare it with a known color and tap on its center if bool equals."""
    return compare_color_from_screenshot_and_tap_or_hold(compared_color,croppedCoords,force_img_path,on_same,False)

def compare_color_from_screenshot_and_hold(compared_color: ColorRGB,croppedCoords:ImageCroppingCoords,force_img_path:str,on_same:bool=True,hold_duration:int|None=None):
    """Finds the dominant color from screenshot and compare it with a known color and hold on its center if bool equals."""
    return compare_color_from_screenshot_and_tap_or_hold(compared_color,croppedCoords,force_img_path,on_same,True,hold_duration)

def compare_color_from_screenshot_and_tap_or_hold(compared_color: ColorRGB,croppedCoords:ImageCroppingCoords,force_img_path:str,on_same:bool=True,hold:bool=False,hold_duration:int|None=None):
    """Finds the dominant color from screenshot and compare it with a known color and tap or hold on its center if bool equals."""
    compare_result=compare_color_from_screenshot(compared_color,croppedCoords,force_img_path) == on_same
    if compare_result:
        x=croppedCoords[0]+((croppedCoords[2]-croppedCoords[0])//2)
        y=croppedCoords[3]+((croppedCoords[1]-croppedCoords[3])//2)
        hold_or_tap(x,y,hold,0,hold_duration)
    return compare_result

def compare_color_from_screenshot(compared_color: ColorRGB,croppedCoords:ImageCroppingCoords,screenshot_path:str):
    return compare_two_colors(get_color_from_image(croppedCoords,screenshot_path),compared_color)

def compare_colors_from_same_screenshot(compared_colors: dict[str, ColorRGB],croppedCoords:ImageCroppingCoords,screenshot_path:str,on_same:bool=True)->tuple(bool,str|None):
    for compared_color_key in compared_colors:
        if compare_two_colors(get_color_from_image(croppedCoords,screenshot_path),compared_colors[compared_color_key]) == on_same:
            return (True,compared_color_key)
    return (False,None)

def compare_colors_on_same_screen_and_tap_if_same(compared_color_and_coords: list[tuple[ColorRGB,ImageCroppingCoords]],force_img_path:str| None =None)-> tuple(bool,list[int]):
    return compare_colors_on_same_screen_and_tap(compared_color_and_coords,True,force_img_path)
    
def compare_colors_on_same_screen_and_tap_not_same(compared_color_and_coords: list[tuple[ColorRGB,ImageCroppingCoords]],force_img_path:str| None =None)-> tuple(bool,list[int]):
    return compare_colors_on_same_screen_and_tap(compared_color_and_coords,False,force_img_path)

def compare_colors_on_same_screen_and_tap(compared_color_and_coords: list[tuple[ColorRGB,ImageCroppingCoords]],on_same:bool,force_img_path:str| None =None)-> tuple(bool,list[int]):
    """Compare colors on screen and compare it with a known color and tap on its center if bool equals."""
    temp_img_name="temp_compare_colors_on_same_screen.png"
    ids = list()
    if force_img_path == None: 
        img_path = screenshot(temp_img_name)
    else:
        img_path = force_img_path
    for index,color_coords_pair in enumerate(compared_color_and_coords):
        if compare_color_from_screenshot_and_tap(color_coords_pair[0],color_coords_pair[1],force_img_path,on_same):
            ids.append(index)
    if os.path.exists(temp_img_name) and force_img_path == None: os.remove(img_path)
    return [len(ids)>0,ids]

# ================== ZOOM (BOT FRIENDLY) ==================

def zoom_out(key="S", hold=0.7):
    """Standard zoom out."""
    pyautogui.keyDown(key)
    time.sleep(hold)
    pyautogui.keyUp(key)

def zoom_in(key="B", hold=0.7):
    """Standard zoom in."""
    pyautogui.keyDown(key)
    time.sleep(hold)
    pyautogui.keyUp(key)

def human_zoom_out(key="S"):
    """Human-like multi-tap zoom out."""
    for t in (0.4, 0.3):
        pyautogui.keyDown(key)
        time.sleep(t)
        pyautogui.keyUp(key)
        time.sleep(0.2)

def human_zoom_in(key="B"):
    """Human-like multi-tap zoom in."""
    for t in (0.4, 0.3):
        pyautogui.keyDown(key)
        time.sleep(t)
        pyautogui.keyUp(key)
        time.sleep(0.2)

# ================== SERVER CONTROL ==================

def kill_server(): return _run("kill-server")
def start_server(): return _run("start-server")
def adb_reconnect(): return _run("reconnect")
def adb_reconnect_device(): return _run("reconnect device")