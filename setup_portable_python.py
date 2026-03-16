#!/usr/bin/env python3
"""
Download and setup portable Python for plugins.
This script downloads a standalone Python build and prepares it for bundling.
"""

import os
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path


# Standalone Python builds from indygreg/python-build-standalone
# These are fully portable Python distributions
PYTHON_DOWNLOADS = {
    ("Darwin", "arm64"): {
        "url": "https://github.com/indygreg/python-build-standalone/releases/download/20240107/cpython-3.11.7+20240107-aarch64-apple-darwin-install_only.tar.gz",
        "filename": "python-darwin-arm64.tar.gz",
        "size": "~35 MB",
    },
    ("Darwin", "x86_64"): {
        "url": "https://github.com/indygreg/python-build-standalone/releases/download/20240107/cpython-3.11.7+20240107-x86_64-apple-darwin-install_only.tar.gz",
        "filename": "python-darwin-x64.tar.gz",
        "size": "~35 MB",
    },
    ("Windows", "AMD64"): {
        "url": "https://github.com/indygreg/python-build-standalone/releases/download/20240107/cpython-3.11.7+20240107-x86_64-pc-windows-msvc-install_only.tar.gz",
        "filename": "python-windows-x64.tar.gz",
        "size": "~40 MB",
    },
    ("Linux", "x86_64"): {
        "url": "https://github.com/indygreg/python-build-standalone/releases/download/20240107/cpython-3.11.7+20240107-x86_64-unknown-linux-gnu-install_only.tar.gz",
        "filename": "python-linux-x64.tar.gz",
        "size": "~40 MB",
    },
}


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.absolute()


def get_platform_key():
    """Get the current platform key for downloading Python."""
    system = platform.system()
    machine = platform.machine()
    
    # Normalize machine names
    if machine in ("amd64", "AMD64", "x86_64"):
        machine = "x86_64" if system != "Windows" else "AMD64"
    elif machine in ("arm64", "aarch64"):
        machine = "arm64" if system == "Darwin" else "aarch64"
    
    return (system, machine)


def download_file(url: str, dest: Path, chunk_size: int = 8192):
    """Download a file with progress."""
    print(f"Downloading from {url}...")
    print(f"Destination: {dest}")
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    with urllib.request.urlopen(url) as response:
        total_size = int(response.headers.get('Content-Length', 0))
        downloaded = 0
        
        with open(dest, 'wb') as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\rProgress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='')
    
    print(f"\nDownloaded: {dest.stat().st_size / (1024*1024):.2f} MB")


def extract_archive(archive_path: Path, extract_to: Path):
    """Extract tar.gz or zip archive."""
    print(f"Extracting {archive_path}...")
    extract_to.mkdir(parents=True, exist_ok=True)
    
    if archive_path.suffix == '.gz' or str(archive_path).endswith('.tar.gz'):
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(extract_to)
    elif archive_path.suffix == '.zip':
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    
    print(f"Extracted to: {extract_to}")


def setup_portable_python():
    """Download and setup portable Python for the current platform."""
    project_root = get_project_root()
    platform_key = get_platform_key()
    
    print("=" * 60)
    print("Portable Python Setup")
    print("=" * 60)
    print(f"Platform: {platform_key[0]} {platform_key[1]}")
    
    if platform_key not in PYTHON_DOWNLOADS:
        print(f"ERROR: Unsupported platform: {platform_key}")
        print("Supported platforms:")
        for key in PYTHON_DOWNLOADS.keys():
            print(f"  - {key[0]} {key[1]}")
        sys.exit(1)
    
    config = PYTHON_DOWNLOADS[platform_key]
    print(f"Expected size: {config['size']}")
    print()
    
    # Setup paths
    downloads_dir = project_root / "downloads"
    python_dir = project_root / "resources" / "python-portable"
    archive_path = downloads_dir / config['filename']
    
    # Download if not exists
    if not archive_path.exists():
        download_file(config['url'], archive_path)
    else:
        print(f"Using cached archive: {archive_path}")
    
    # Clean and extract
    if python_dir.exists():
        print(f"Cleaning existing directory: {python_dir}")
        shutil.rmtree(python_dir)
    
    extract_archive(archive_path, python_dir)
    
    # Verify installation
    python_exe = find_python_executable(python_dir)
    if python_exe:
        print(f"\n✅ Portable Python setup successful!")
        print(f"   Location: {python_dir}")
        print(f"   Python: {python_exe}")
        
        # Test Python
        import subprocess
        result = subprocess.run(
            [str(python_exe), "--version"],
            capture_output=True,
            text=True
        )
        print(f"   Version: {result.stdout.strip() or result.stderr.strip()}")
        
        # Install pip if needed
        ensure_pip(python_exe)
        
        return True
    else:
        print("\n❌ Failed to find Python executable after extraction")
        return False


def find_python_executable(python_dir: Path) -> Path | None:
    """Find the Python executable in the extracted directory."""
    system = platform.system()
    
    if system == "Windows":
        possible_paths = [
            python_dir / "python" / "python.exe",
            python_dir / "python.exe",
            python_dir / "bin" / "python.exe",
        ]
    else:
        possible_paths = [
            python_dir / "python" / "bin" / "python3",
            python_dir / "python" / "bin" / "python",
            python_dir / "bin" / "python3",
            python_dir / "bin" / "python",
            python_dir / "python3",
            python_dir / "python",
        ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    # Try to find any python executable
    for path in python_dir.rglob("python*"):
        if path.is_file() and os.access(path, os.X_OK):
            return path
    
    return None


def ensure_pip(python_exe: Path):
    """Ensure pip is installed in the portable Python."""
    import subprocess
    
    print("\nChecking pip...")
    result = subprocess.run(
        [str(python_exe), "-m", "pip", "--version"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"   ✅ pip is available: {result.stdout.strip()}")
    else:
        print("   Installing pip...")
        # Download get-pip.py
        get_pip_path = python_exe.parent / "get-pip.py"
        urllib.request.urlretrieve(
            "https://bootstrap.pypa.io/get-pip.py",
            get_pip_path
        )
        
        # Install pip
        subprocess.run(
            [str(python_exe), str(get_pip_path)],
            check=True
        )
        get_pip_path.unlink()
        print("   ✅ pip installed")


def get_portable_python_path() -> Path | None:
    """Get the path to the portable Python executable (for runtime use)."""
    project_root = get_project_root()
    python_dir = project_root / "resources" / "python-portable"
    
    return find_python_executable(python_dir)


def main():
    """Main entry point."""
    try:
        success = setup_portable_python()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
