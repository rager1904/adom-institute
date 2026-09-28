#!/usr/bin/env python3
"""
Interpreter and venv provisioning for the Colab load-test suite.

This lives in the repository, not in the notebook, for one specific reason.

The venv cell used to be inline in `adom_loadtest.ipynb`, so its logic was
frozen into whatever copy of the notebook the browser tab had loaded. A user
who re-ran an old tab re-ran the old bootstrap and got the identical failure,
however many times the fix had been pushed. Three rounds of that happened while
debugging the Python 3.13 / numpy 1.26.4 wheel problem.

Here, the notebook is a thin shim: it imports this module from the checkout,
which the notebook's own refresh step (`git fetch` + `reset --hard`) updates on
every run. A stale tab now gets fresh bootstrap logic, and the bootstrap reports
`BOOTSTRAP_VERSION` so a stale run is obvious in the output.

Why a venv at all, and why not the Colab default:

* `requirements.txt` pins `numpy==1.26.4` and `Django==4.2.7`. Those support
  Python 3.9-3.12 and publish no 3.13 wheels. Colab now ships Python 3.13, so
  installing the pins on the default interpreter falls back to a source build of
  NumPy that cannot succeed. The `Dockerfile` targets 3.11, confirming 3.13 is
  not the intended runtime.
* Installing into the system interpreter would also overwrite Colab's own NumPy
  and break unrelated runtime internals, so the venv is isolated regardless.

Why `uv`, and not `python -m venv`:

* Colab's CPython (the one `python3` resolves to, in `/usr/local`) ships without
  `ensurepip`, so the stdlib venv module cannot bootstrap pip. Debian's
  `python3-venv` does not help: it only provides `ensurepip` for *Debian's*
  interpreter, not the one in `/usr/local`.
* `uv venv` needs no `ensurepip`. It also seeds no pip at all, so the resulting
  venv has `bin/python` but no `bin/pip`; every install here goes through
  `<venv>/bin/python -m pip` for that reason.

The rule that took the most iterations to get right: a venv is judged by **the
version of the interpreter inside it**, never by whether the directory exists. A
venv left behind on the 3.13 default looks perfectly valid to an existence
check, and then fails minutes later with pip's `No matching distribution found
for numpy==1.26.4` -- which reads like a bad pin but is really a version
mismatch. `plan_venv` encodes that decision as a pure function so it can be
tested without provisioning anything.

Runnable standalone for debugging:

    python colab/harness/bootstrap.py --repo /content/adom-institute
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Bump whenever the provisioning logic changes. The notebook prints it, so a
# run using a stale bootstrap is identifiable from the log alone.
BOOTSTRAP_VERSION = 2

# The interpreter range the pins in requirements.txt support. 1.26.x of NumPy
# and Django 4.2 both stop at 3.12; NumPy 2.x is the first line with 3.13.
MIN_PY, REQUIRED_PY = (3, 9), (3, 12)
TARGET_PY = REQUIRED_PY
DOT = ".".join(map(str, REQUIRED_PY))
RANGE = f"{MIN_PY[0]}.{MIN_PY[1]}-{DOT}"

# The pin used as a canary: cheap, and decisive about the interpreter.
CANARY = "numpy==1.26.4"
EXTRA_PACKAGES = ("aiohttp", "websockets", "psutil", "redis")
VERIFY_IMPORTS = ("django", "numpy", "channels", "celery")


class BootstrapError(SystemExit):
    """A provisioning failure, reported as an actionable message.

    SystemExit so the notebook aborts loudly instead of continuing into cells
    that would fail in more confusing ways.
    """


def default_sh(cmd: str, **kw):
    """Run a shell command, printing output; raise on failure.

    Mirrors the notebook's own sh(). Output is printed *before* raising, because
    subprocess's own error message is just "returned non-zero exit status 1" and
    the real cause is in the output that was captured.
    """
    print(f"\n$ {cmd}", flush=True)
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True, **kw)
    if p.stdout:
        print(p.stdout, end="", flush=True)
    if p.returncode != 0:
        if p.stderr:
            print(p.stderr, file=sys.stderr, flush=True)
        raise BootstrapError(f"`{cmd}` failed with exit code {p.returncode}")
    if p.stderr:
        print(p.stderr, end="", flush=True)
    return p


def default_sh_ok(cmd: str):
    """Run a shell command, tolerate failure, return (rc, stdout, stderr)."""
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def ver_of(exe, sh_ok=None) -> tuple[int, int] | None:
    """Return (major, minor) for an interpreter path, or None if unusable."""
    sh_ok = sh_ok or default_sh_ok
    rc, out, _ = sh_ok(
        f'{exe} -c "import sys;print(sys.version_info[0], sys.version_info[1])"')
    try:
        maj, mnr = out.strip().split()
        return (int(maj), int(mnr))
    except Exception:
        return None


def supported(ver) -> bool:
    """True when an interpreter version can take the pins in requirements.txt."""
    return ver is not None and MIN_PY <= ver <= REQUIRED_PY


def plan_venv(venv_exists: bool, have) -> tuple[bool, str]:
    """Decide whether to reuse or rebuild a venv, and say why.

    Pure, so the decision is testable without provisioning anything. `have` is
    the version reported by the interpreter inside the venv, or None when the
    venv is absent or has no working interpreter.

    The failure this encodes: a venv created on the 3.13 default by a run that
    died in ensurepip. It has a working bin/python, so an existence check says
    it is fine, and it then cannot install the pins.
    """
    if have is None:
        return True, ("no working interpreter in it" if venv_exists
                      else "it does not exist yet")
    if not supported(have):
        return True, (f"it runs {have[0]}.{have[1]}, and the pins in "
                      f"requirements.txt need {RANGE}")
    return False, ""


def ensure_uv(sh, sh_ok) -> str:
    """Install uv if needed and return the resolved interpreter path.

    uv's installer is idempotent, and it is the only venv creator that works on
    Colab, so it is installed unconditionally rather than conditionally.
    """
    sh("curl -LsSf https://astral.sh/uv/install.sh | sh")
    os.environ["PATH"] = (
        os.path.expanduser("~/.local/bin") + os.pathsep + os.environ.get("PATH", ""))
    sh(f"uv python install {DOT}")
    rc, out, err = sh_ok(f"uv python find {DOT}")
    target = out.strip()
    if rc != 0 or not os.path.exists(target):
        raise BootstrapError(
            f"could not obtain a Python {DOT} interpreter:\n"
            + (err or out).strip())
    return target


def ensure_venv(repo: Path, target: str, sh, sh_ok) -> tuple[Path, str]:
    """Create the venv from `target`, or reuse it if its interpreter is usable."""
    venv = Path(repo) / ".venv"
    vpy = venv / "bin" / "python"
    have = ver_of(str(vpy), sh_ok) if vpy.exists() else None
    rebuild, reason = plan_venv(venv.exists(), have)
    if rebuild:
        # `uv venv` needs no ensurepip, which Colab's CPython lacks.
        sh(f"rm -rf {venv}")
        sh(f"uv venv --python {target} {venv}")
        print(f"rebuilding the venv: {reason}", flush=True)
    else:
        print(f"reusing venv on Python {have[0]}.{have[1]}", flush=True)
    if not os.path.exists(str(vpy)):
        raise BootstrapError(f"venv interpreter missing at {vpy} after creation")
    return venv, str(vpy)


def ensure_pip(py: str, sh, sh_ok) -> None:
    """Make `python -m pip` work inside the venv.

    `uv venv` seeds no pip, which is exactly what makes it usable here, so the
    venv has bin/python and no bin/pip. Both seeding paths are tried because a
    uv-managed interpreter may lack ensurepip too.
    """
    rc, _, err = sh_ok(f"{py} -m pip --version")
    if rc == 0:
        return
    print("seeding pip into the venv ...", flush=True)
    # Non-fatal: aborting here would skip the uv fallback below.
    sh_ok(f"{py} -m ensurepip --upgrade")
    rc, _, err = sh_ok(f"{py} -m pip --version")
    if rc == 0:
        return
    rc2, _, err2 = sh_ok(f"uv pip install --python {py} pip setuptools wheel")
    if rc2 != 0:
        raise BootstrapError(
            "could not bootstrap pip into the venv:\n" + (err or "").strip()
            + (("\nuv: " + err2.strip()) if err2 else "")
            + f"\n  The venv exists at {py} but has no usable pip.")
    sh(f"{py} -m pip install -q --upgrade pip setuptools wheel")


def vpip(py: str, *args, sh_ok=None, check: bool = True):
    """Run pip in the venv via the interpreter, so this works whether the venv
    has a bin/pip or was created by uv without one."""
    sh_ok = sh_ok or default_sh_ok
    r = sh_ok(f"{py} -m pip " + " ".join(args))
    if check and r[0] != 0:
        raise BootstrapError(
            f"pip {' '.join(args)} failed:\n" + (r[2] or r[1]).strip())
    return r


def install_requirements(repo: Path, py: str, sh, sh_ok) -> None:
    """Install the pins, wheel-only, with the canary first.

    `--only-binary=:all:` means an unsatisfiable pin fails in seconds with pip's
    own message instead of minutes of doomed source compilation.
    """
    req = Path(repo) / "requirements.txt"
    if not req.is_file():
        raise BootstrapError(f"requirements.txt not found at {req}")

    # Canary: decisive about the interpreter, and cheap.
    rc, out, err = vpip(py, "install", "-q", "--only-binary=:all:", CANARY,
                        sh_ok=sh_ok, check=False)
    if rc != 0:
        running = ver_of(py, sh_ok)
        raise BootstrapError(
            f"this venv cannot install {CANARY} as a wheel.\n"
            f"  venv interpreter : "
            f"{'.'.join(map(str, running)) if running else 'unknown'}"
            f" ({sh_ok(py + ' -V')[1].strip()})\n"
            f"  pins need        : {RANGE}\n"
            f"  venv path        : {Path(py).parent.parent}\n"
            f"  {CANARY.split('==')[0]} {CANARY.split('==')[1]} has no wheels "
            f"for Python > {DOT}, and plan_venv() should have rebuilt this venv.\n"
            f"  to recover:  rm -rf {Path(py).parent.parent}\n"
            "  last pip output:\n    "
            + "\n    ".join((out + err).strip().splitlines()[-6:]))

    print("installing project requirements ...", flush=True)
    rc, out, err = vpip(py, "install", "--only-binary=:all:", str(req),
                        sh_ok=sh_ok, check=False)
    if rc != 0:
        raise BootstrapError(
            "could not install requirements.txt as wheels.\n  "
            + "\n  ".join((out + err).strip().splitlines()[-15:])
            + "\n\nA pin in requirements.txt has no prebuilt wheel for this Python.")
    vpip(py, "install", "--only-binary=:all:", *EXTRA_PACKAGES, sh_ok=sh_ok)


def verify(py: str, sh, sh_ok) -> str:
    """Import-check the real dependencies and return the reported version line."""
    imports = ",".join(VERIFY_IMPORTS)
    rc, out, err = sh_ok(f'{py} -c "import {imports}"')
    if rc != 0:
        raise BootstrapError("the venv is missing a required package:\n" + err.strip())
    rc, out, err = sh_ok(
        f'{py} -c "import sys,django,numpy,channels;'
        f'print(sys.version.split()[0], django.get_version(), numpy.__version__)"')
    if rc != 0:
        raise BootstrapError("the venv interpreter is broken:\n" + err.strip())
    venv_py = out.split()[0]
    running = tuple(int(x) for x in venv_py.split(".")[:2])
    if not supported(running):
        raise BootstrapError(
            f"venv is on Python {venv_py} but requirements.txt pins packages\n"
            f"that support {RANGE} only. Remove {Path(py).parent.parent} and re-run.")
    return out.strip()


def ensure_env(repo, sh=None, sh_ok=None):
    """Provision the venv and return (python_path, venv_path, version_line).

    `repo` is the project root. `sh`/`sh_ok` are the caller's command runners, so
    the notebook keeps one consistent way of echoing and handling commands.
    """
    sh = sh or default_sh
    sh_ok = sh_ok or default_sh_ok
    repo = Path(repo)

    default = ver_of("python3", sh_ok)
    print(f"bootstrap v{BOOTSTRAP_VERSION} | colab default python: "
          f"{'.'.join(map(str, default)) if default else 'unknown'}", flush=True)

    target = ensure_uv(sh, sh_ok)
    print(f"interpreter: {target} "
          f"{'.'.join(map(str, ver_of(target, sh_ok) or ()))}", flush=True)

    venv, py = ensure_venv(repo, target, sh, sh_ok)
    ensure_pip(py, sh, sh_ok)
    sh(f"{py} -m pip install -q --upgrade pip setuptools wheel")
    install_requirements(repo, py, sh, sh_ok)
    line = verify(py, sh, sh_ok)
    print(f"venv ready: {line}", flush=True)
    return py, venv, line


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="project root")
    args = ap.parse_args()
    try:
        ensure_env(args.repo)
    except BootstrapError as e:
        print(f"\n{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
