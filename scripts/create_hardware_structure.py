from pathlib import Path

BASE_DIR = Path.cwd() / "src" / "hardware"

structure = {
    "__init__.py": None,
    "hardware_manager.py": None,
    "config.py": None,
    "requirements.txt": None,
    "interfaces": {
        "__init__.py": None,
        "biometric_interface.py": None,
        "fingerprint_scanner.py": None,
        "facial_recognition.py": None,
        "camera_controller.py": None,
    },
    "drivers": {
        "__init__.py": None,
        "zkteco": {},
        "suprema": {},
        "hikvision": {},
    },
    "utils": {
        "__init__.py": None,
        "device_discovery.py": None,
        "image_processing.py": None,
        "diagnostics.py": None,
    },
    "configs": {
        "devices.yaml": None,
        "camera_settings.yaml": None,
    },
    "tests": {
        "test_fingerprint.py": None,
        "test_facial_recognition.py": None,
    },
}


def create_structure(base_path: Path, tree: dict):
    for name, content in tree.items():
        path = base_path / name
        if content is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
            create_structure(path, content)


if __name__ == "__main__":
    create_structure(BASE_DIR, structure)
    print("[OK] src/hardware folder structure created")
