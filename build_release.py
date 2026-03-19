"""Build script: compiles the exe and creates the distributable zip."""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT, "dist")
RELEASE_DIR = os.path.join(ROOT, "release")
PACKAGE_NAME = "EromeDownloader"


def main():
    print("=== Building EromeDownloader release ===\n")

    # 1. Build exe
    print("[1/3] Building executable...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "EromeDownloader.spec", "--noconfirm"],
        cwd=ROOT,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("BUILD FAILED:")
        print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
        sys.exit(1)
    print("  Exe built successfully.")

    exe_path = os.path.join(DIST_DIR, f"{PACKAGE_NAME}.exe")
    if not os.path.exists(exe_path):
        print(f"ERROR: {exe_path} not found")
        sys.exit(1)

    exe_size = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"  Size: {exe_size:.1f} MB")

    # 2. Assemble release folder
    print("\n[2/3] Assembling release package...")
    if os.path.exists(RELEASE_DIR):
        shutil.rmtree(RELEASE_DIR)

    pkg_dir = os.path.join(RELEASE_DIR, PACKAGE_NAME)
    os.makedirs(pkg_dir)

    shutil.copy2(exe_path, pkg_dir)
    print(f"  Copied {PACKAGE_NAME}.exe")

    icon_src = os.path.join(ROOT, "src", "assets", "icon.ico")
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, pkg_dir)
        print("  Copied icon.ico")

    installer_dir = os.path.join(ROOT, "installer")
    for bat in ["instalar.bat", "desinstalar.bat"]:
        src = os.path.join(installer_dir, bat)
        if os.path.exists(src):
            shutil.copy2(src, pkg_dir)
            print(f"  Copied {bat}")

    # 3. Create zip
    print("\n[3/3] Creating zip...")
    zip_path = os.path.join(RELEASE_DIR, PACKAGE_NAME)
    shutil.make_archive(zip_path, "zip", RELEASE_DIR, PACKAGE_NAME)
    zip_file = zip_path + ".zip"
    zip_size = os.path.getsize(zip_file) / (1024 * 1024)
    print(f"  Created: {zip_file}")
    print(f"  Size: {zip_size:.1f} MB")

    print(f"\n=== Release ready! ===")
    print(f"Zip: {zip_file}")
    print(f"\nSeu amigo so precisa:")
    print(f"  1. Extrair o zip")
    print(f"  2. Rodar 'instalar.bat' (cria atalho no desktop)")
    print(f"  3. Ou abrir EromeDownloader.exe direto")


if __name__ == "__main__":
    main()
