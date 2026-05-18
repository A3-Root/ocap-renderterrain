import subprocess
import threading
from pathlib import Path

_jobs = {}
_lock = threading.Lock()


def _result(status, **values):
    data = [["status", status]]
    for key, value in values.items():
        data.append([key, "" if value is None else str(value)])
    return data


def _mod_root():
    return Path(__file__).resolve().parents[1]


def _arma_root():
    return Path.cwd()


def _key(world_name):
    return str(world_name).lower()


def _run(world_name):
    key = _key(world_name)
    arma_root = _arma_root()
    mod_root = _mod_root()
    docker_context = mod_root / "ocap_renderterrain"
    input_dir = arma_root / "ocap_exporter"
    output_dir = arma_root / "ocap_renderterrain_output"
    temp_dir = arma_root / "ocap_renderterrain_temp"

    try:
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        if not docker_context.exists():
            raise RuntimeError(f"Docker context not found: {docker_context}")

        with _lock:
            _jobs[key] = {"status": "building", "error": "", "output": output_dir}
        subprocess.run(
            ["docker", "build", "-t", "ocap-renderterrain:latest", str(docker_context)],
            cwd=str(mod_root),
            check=True,
        )

        with _lock:
            _jobs[key] = {"status": "running", "error": "", "output": output_dir}
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                f"ocap-renderterrain-{key}",
                "--mount",
                f"type=bind,src={input_dir},target=/app/input",
                "--mount",
                f"type=bind,src={output_dir},target=/app/output",
                "--mount",
                f"type=bind,src={temp_dir},target=/app/temp",
                "--env",
                f"OCAP_RENDER_WORLDS={key}",
                "--memory=36g",
                "ocap-renderterrain:latest",
            ],
            cwd=str(mod_root),
            check=True,
        )

        with _lock:
            _jobs[key] = {"status": "done", "error": "", "output": output_dir / key}
    except Exception as exc:
        with _lock:
            _jobs[key] = {"status": "error", "error": exc, "output": output_dir / key}


def process_world(world_name):
    key = _key(world_name)
    with _lock:
        current = _jobs.get(key)
        if current and current.get("status") in {"queued", "building", "running"}:
            return _result(current["status"], error="", output=current.get("output", ""))
        _jobs[key] = {"status": "queued", "error": "", "output": ""}

    threading.Thread(target=_run, args=(key,), daemon=True).start()
    return _result("queued", error="", output="")


def get_status(world_name):
    key = _key(world_name)
    with _lock:
        current = _jobs.get(key, {"status": "idle", "error": "", "output": ""})
        return _result(
            current.get("status", "idle"),
            error=current.get("error", ""),
            output=current.get("output", ""),
        )
