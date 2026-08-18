"""在全新虚拟环境中验证发布 wheel 与完整运行时 wheelhouse。"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shlex
import subprocess
import sys
import venv
from pathlib import Path
from urllib.request import Request, urlopen

_PYGHDL_VERSION = "6.0.0"
_PROJECT_VERSION = "0.1.1"
_PYGHDL_ASSETS = {
    ("linux", "x86_64", (3, 13)): (
        "pyghdl-6.0.0-cp313-cp313-linux_x86_64.whl",
        "d402d0cf73ecbec89cfe8ee3dd029f87b45ab6c8a99f954506d66d071049e797",
    ),
    ("win32", "amd64", (3, 13)): (
        "pyghdl-6.0.0-cp313-cp313-win_amd64.whl",
        "624ce2fcb3163c16215e7d0390caaf91bd0ae50a77dcb2b60e2eae35a5ebe839",
    ),
}
_RELEASE_BASE_URL = "https://github.com/ghdl/ghdl/releases/download/v6.0.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(arguments: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print(f"+ {shlex.join(arguments)}", flush=True)
    subprocess.run(arguments, cwd=cwd, env=env, check=True)


def _download(url: str, destination: Path, expected_sha256: str) -> None:
    request = Request(url, headers={"User-Agent": f"HDL-X-release-smoke/{_PROJECT_VERSION}"})
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Downloading official asset: {url}", flush=True)
    with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    actual = _sha256(temporary)
    if actual != expected_sha256:
        raise RuntimeError(
            f"pyGHDL wheel SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )
    temporary.replace(destination)


def _venv_python(venv_directory: Path) -> Path:
    if os.name == "nt":
        return venv_directory / "Scripts" / "python.exe"
    return venv_directory / "bin" / "python"


def _venv_cli(venv_directory: Path) -> Path:
    if os.name == "nt":
        return venv_directory / "Scripts" / "hdl-x.exe"
    return venv_directory / "bin" / "hdl-x"


def _asset_for_runtime() -> tuple[str, str]:
    key = (sys.platform, platform.machine().lower(), sys.version_info[:2])
    try:
        return _PYGHDL_ASSETS[key]
    except KeyError as error:
        raise RuntimeError(
            "No audited pyGHDL wheel for runtime "
            f"platform={sys.platform}, machine={platform.machine()}, "
            f"python={sys.version_info.major}.{sys.version_info.minor}"
        ) from error


def _write_wheelhouse_manifest(wheelhouse: Path) -> Path:
    manifest = wheelhouse / "SHA256SUMS.txt"
    lines = [f"{_sha256(path)}  {path.name}" for path in sorted(wheelhouse.glob("*.whl"))]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return manifest


def run_smoke(workspace: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    if workspace.exists():
        raise RuntimeError(f"Refusing to reuse wheel smoke workspace: {workspace}")
    workspace.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir()

    artifacts = workspace / "artifacts"
    official = workspace / "official"
    wheelhouse = workspace / "wheelhouse"
    smoke_work = workspace / "work"
    venv_directory = workspace / "venv"
    for directory in (artifacts, official, wheelhouse, smoke_work):
        directory.mkdir()

    asset_name, asset_sha256 = _asset_for_runtime()
    pyghdl_wheel = official / asset_name
    _download(
        f"{_RELEASE_BASE_URL}/{asset_name}",
        pyghdl_wheel,
        asset_sha256,
    )

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    _run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(artifacts), "."],
        cwd=repository,
        env=environment,
    )
    project_wheels = tuple(artifacts.glob(f"hdl_x-{_PROJECT_VERSION}-*.whl"))
    if len(project_wheels) != 1:
        raise RuntimeError(f"Expected one HDL-X wheel, found {len(project_wheels)}")
    project_wheel = project_wheels[0]

    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(wheelhouse),
            "--only-binary=:all:",
            str(project_wheel),
            str(pyghdl_wheel),
        ],
        cwd=smoke_work,
        env=environment,
    )
    manifest = _write_wheelhouse_manifest(wheelhouse)

    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(venv_directory)
    venv_python = _venv_python(venv_directory)
    venv_cli = _venv_cli(venv_directory)
    configuration = (venv_directory / "pyvenv.cfg").read_text(encoding="utf-8")
    if "include-system-site-packages = false" not in configuration.lower():
        raise RuntimeError("Smoke virtualenv unexpectedly exposes system site packages")

    _run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            f"hdl-x=={_PROJECT_VERSION}",
        ],
        cwd=smoke_work,
        env=environment,
    )
    _run([str(venv_python), "-m", "pip", "check"], cwd=smoke_work, env=environment)
    _run(
        [
            str(venv_python),
            "-c",
            "from importlib.metadata import version; "
            f"assert version('hdl-x') == '{_PROJECT_VERSION}'; "
            f"assert version('pyGHDL') == '{_PYGHDL_VERSION}'",
        ],
        cwd=smoke_work,
        env=environment,
    )
    _run([str(venv_cli), "--help"], cwd=smoke_work, env=environment)
    _run([str(venv_cli), "doctor"], cwd=smoke_work, env=environment)

    fixture = repository / "tests" / "fixtures" / "vhdl" / "m2_simple_and.vhd"
    golden = repository / "tests" / "golden" / "m2_simple_and.v"
    generated = smoke_work / "m2_simple_and.v"
    _run(
        [
            str(venv_cli),
            "convert",
            str(fixture),
            "--from",
            "vhdl",
            "--to",
            "verilog",
            "-o",
            str(generated),
            "--strict",
        ],
        cwd=smoke_work,
        env=environment,
    )
    if generated.read_bytes() != golden.read_bytes():
        raise RuntimeError("Installed-wheel output is not byte-identical to committed golden")

    print(manifest.read_text(encoding="utf-8"), end="")
    print(f"HDL_X_WHEEL_SHA256={_sha256(project_wheel)}")
    print(f"PYGHDL_WHEEL_SHA256={_sha256(pyghdl_wheel)}")
    print(f"GENERATED_SHA256={_sha256(generated)}")
    print(f"GOLDEN_SHA256={_sha256(golden)}")
    print("ISOLATED_WHEELHOUSE_SMOKE=PASSED")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    arguments = parser.parse_args()
    run_smoke(arguments.workspace.expanduser().resolve())


if __name__ == "__main__":
    main()
