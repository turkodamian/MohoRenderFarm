"""Windows context menu (right-click) integration for Moho files."""
import sys
import os
import winreg
from pathlib import Path


APP_NAME = "MohoRenderFarm"
MENU_RENDER = "Render with Moho Render Farm"
MENU_ADD_QUEUE = "Add to Moho Render Farm Queue"


def get_app_path():
    """Get the path to the main application script."""
    return str(Path(__file__).parent.parent.parent / "main.py")


def get_python_path():
    """Get the Python executable path (windowless version)."""
    exe_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(exe_dir, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return sys.executable


def _get_existing_progids(ext):
    """Find all ProgIDs currently associated with a file extension."""
    progids = set()

    # Check HKEY_CLASSES_ROOT (merged HKLM + HKCU view)
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext) as key:
            val = winreg.QueryValue(key, "")
            if val:
                progids.add(val)
    except OSError:
        pass

    # Check HKCU UserChoice (highest priority on modern Windows)
    try:
        uc_path = f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{ext}\\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uc_path) as key:
            val, _ = winreg.QueryValueEx(key, "ProgId")
            if val:
                progids.add(val)
    except OSError:
        pass

    # Check OpenWithProgids
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{ext}\\OpenWithProgids") as key:
            i = 0
            while True:
                try:
                    name, _, _ = winreg.EnumValue(key, i)
                    if name:
                        progids.add(name)
                    i += 1
                except OSError:
                    break
    except OSError:
        pass

    return progids


def _register_shell_commands(type_key_path, python, app_path):
    """Register the two shell commands under a given registry path."""
    # Shell - Render command
    shell_render = f"{type_key_path}\\shell\\MohoRenderFarm"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_render) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, MENU_RENDER)
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, f'"{python}"')

    cmd_render = f"{shell_render}\\command"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_render) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ,
                          f'"{python}" "{app_path}" --render "%1"')

    # Shell - Add to queue command
    shell_queue = f"{type_key_path}\\shell\\MohoRenderFarmQueue"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_queue) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, MENU_ADD_QUEUE)
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, f'"{python}"')

    cmd_queue = f"{shell_queue}\\command"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_queue) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ,
                          f'"{python}" "{app_path}" --add-to-queue "%1"')


def register_context_menu():
    """Register right-click context menu entries for .moho files.

    IMPORTANT: Never creates or modifies HKCU\\Software\\Classes\\.moho (or .anime/.anme)
    to avoid overriding the system-level file association with Moho software.
    Uses only existing ProgIDs and SystemFileAssociations.
    """
    python = get_python_path()
    app_path = get_app_path()
    extensions = [".moho", ".anime", ".anme"]
    registered_paths = []

    for ext in extensions:
        try:
            # 1) Register under all existing ProgIDs (works when Moho is installed)
            existing = _get_existing_progids(ext)
            for progid in existing:
                path = f"Software\\Classes\\{progid}"
                _register_shell_commands(path, python, app_path)
                registered_paths.append(path)

            # 2) Register under SystemFileAssociations (reliable, never affects file association)
            sfa_path = f"Software\\Classes\\SystemFileAssociations\\{ext}"
            _register_shell_commands(sfa_path, python, app_path)
            registered_paths.append(sfa_path)

        except OSError as e:
            print(f"Error registering context menu for {ext}: {e}")
            return False

    print(f"Context menu registered for .moho, .anime, .anme files ({len(registered_paths)} entries)")
    return True


def unregister_context_menu():
    """Remove right-click context menu entries.

    Also cleans up any HKCU extension key overrides left by previous versions
    that may have broken the system-level Moho file association.
    """
    extensions = [".moho", ".anime", ".anme"]

    for ext in extensions:
        our_progid = f"MohoProject{ext}"

        # Clean up HKCU extension key if it points to our ProgID (left by old versions)
        _cleanup_hkcu_extension_key(ext, our_progid)

        # Remove our custom ProgID entirely
        _delete_key_recursive(winreg.HKEY_CURRENT_USER,
                              f"Software\\Classes\\{our_progid}")

        # Remove our shell commands from all existing ProgIDs
        for progid in _get_existing_progids(ext):
            _delete_shell_commands(winreg.HKEY_CURRENT_USER,
                                   f"Software\\Classes\\{progid}")

        # Remove from SystemFileAssociations
        _delete_shell_commands(winreg.HKEY_CURRENT_USER,
                               f"Software\\Classes\\SystemFileAssociations\\{ext}")

    print("Context menu entries removed")
    return True


def _cleanup_hkcu_extension_key(ext, our_progid):
    """Remove HKCU extension key override if it was created by us.

    Previous versions created HKCU\\Software\\Classes\\.moho which shadows the
    system-level (HKLM) file association. Remove it if it points to our ProgID
    or is empty, restoring the original Moho association.
    """
    hkcu_ext_path = f"Software\\Classes\\{ext}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, hkcu_ext_path, 0,
                            winreg.KEY_READ) as key:
            try:
                default_val = winreg.QueryValue(key, "")
            except OSError:
                default_val = ""

            # Only delete if it points to our ProgID or is empty
            if default_val in (our_progid, ""):
                _delete_key_recursive(winreg.HKEY_CURRENT_USER, hkcu_ext_path)
    except OSError:
        pass


def _delete_shell_commands(root, base_path):
    """Remove only our MohoRenderFarm shell commands from a registry path."""
    for cmd_name in ("MohoRenderFarm", "MohoRenderFarmQueue"):
        _delete_key_recursive(root, f"{base_path}\\shell\\{cmd_name}")


def _delete_key_recursive(root, path):
    """Recursively delete a registry key and all its subkeys."""
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    subkey = winreg.EnumKey(key, 0)
                    _delete_key_recursive(root, f"{path}\\{subkey}")
                except OSError:
                    break
        winreg.DeleteKey(root, path)
    except OSError:
        pass


def is_context_menu_registered():
    """Check if context menu is already registered."""
    # Check SystemFileAssociations (primary method)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            "Software\\Classes\\SystemFileAssociations\\.moho\\shell\\MohoRenderFarm"):
            return True
    except OSError:
        pass

    # Check existing ProgIDs
    for progid in _get_existing_progids(".moho"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                f"Software\\Classes\\{progid}\\shell\\MohoRenderFarm"):
                return True
        except OSError:
            pass

    return False
