import io
import json
import os
import re
import shutil
import subprocess
import threading
import zipfile
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, request, send_file


BASE_DIR = Path(__file__).resolve().parent
CODE_ROOT = BASE_DIR / "code"
STATIC_ROOT = BASE_DIR / "static"
TESTLIB_SOURCE = CODE_ROOT / "testlib.h"
REQUEST_TTL_SECONDS = 600
RUN_TIMEOUT_SECONDS = 2
EXECUTABLE_SUFFIX = ".exe" if os.name == "nt" else ""
UUID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
CASE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")
JUDGE_STATUS_LABELS = {
    0: "AC",
    1: "WA",
    2: "PE",
    3: "FAIL",
    7: "PARTIAL",
    8: "PE",
}

# serve static files at /spjmaker so the app works when hosted at /spjmaker
app = Flask(__name__, static_folder=str(STATIC_ROOT), static_url_path="/spjmaker")

CODE_ROOT.mkdir(exist_ok=True)

_cleanup_lock = threading.Lock()
_cleanup_timers: dict[str, threading.Timer] = {}



def find_cpp_compiler() -> str | None:
    for name in ("g++", "clang++", "c++"):
        compiler = shutil.which(name)
        if compiler:
            return compiler
    return None


CPP_COMPILER = find_cpp_compiler()


def validate_uuid(raw_uuid: str | None) -> str:
    if not raw_uuid or not UUID_PATTERN.fullmatch(raw_uuid):
        raise ValueError("uuid 不合法")
    return raw_uuid


def sanitize_case_name(raw_name: str | None, index: int) -> str:
    name = (raw_name or "").strip()
    if not name:
        return f"data{index}"

    normalized = CASE_NAME_PATTERN.sub("_", name).strip("._-")
    if not normalized:
        return f"data{index}"
    return normalized


def schedule_cleanup(uuid: str) -> None:
    def _delete_dir() -> None:
        shutil.rmtree(CODE_ROOT / uuid, ignore_errors=True)
        with _cleanup_lock:
            _cleanup_timers.pop(uuid, None)

    with _cleanup_lock:
        old_timer = _cleanup_timers.get(uuid)
        if old_timer:
            old_timer.cancel()

        timer = threading.Timer(REQUEST_TTL_SECONDS, _delete_dir)
        timer.daemon = True
        timer.start()
        _cleanup_timers[uuid] = timer


def prepare_uuid_dir(uuid: str) -> Path:
    uuid_dir = CODE_ROOT / uuid
    shutil.rmtree(uuid_dir, ignore_errors=True)
    uuid_dir.mkdir(parents=True, exist_ok=True)

    if not TESTLIB_SOURCE.exists():
        raise FileNotFoundError("code/testlib.h 不存在")

    shutil.copy2(TESTLIB_SOURCE, uuid_dir / "testlib.h")
    return uuid_dir


def write_text_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")

def write_judge_yaml(path: Path, spj_exists: bool, std_exists: bool, cases: list[dict[str, str]]) -> None:
    # simple YAML describing the package; mostly for download convenience
    lines = []
    if spj_exists:
        lines.append("spj: spj.cpp")
    else:
        lines.append("spj: null")
    if std_exists:
        lines.append("std: std.cpp")
    else:
        lines.append("std: null")
    lines.append("cases:")
    for c in cases:
        # include name if available
        name = c.get("name") or c.get("id") or ""
        lines.append(f"  - id: {c.get('id')}\n    name: {name}")
    content = "\n".join(lines) + "\n"
    write_text_file(path, content)


def compile_cpp(source: Path, output: Path, cwd: Path) -> tuple[bool, str]:
    if not CPP_COMPILER:
        return False, "未找到可用的 C++ 编译器（g++ / clang++ / c++）"

    result = subprocess.run(
        [CPP_COMPILER, source.name, "-std=c++17", "-O2", "-o", output.name],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    message = (result.stderr or result.stdout or "").strip()
    return result.returncode == 0, message


def run_solution(executable: Path, input_file: Path, output_file: Path, cwd: Path) -> str:
    with input_file.open("r", encoding="utf-8") as stdin_handle, output_file.open("w", encoding="utf-8") as stdout_handle:
        try:
            result = subprocess.run(
                [str(executable)],
                cwd=str(cwd),
                stdin=stdin_handle,
                stdout=stdout_handle,
                stderr=subprocess.PIPE,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "TLE"

    if result.returncode != 0:
        return "RE"
    return "OK"


def run_checker(checker: Path, input_file: Path, user_output_file: Path, answer_file: Path, cwd: Path) -> str:
    try:
        result = subprocess.run(
            [str(checker), input_file.name, user_output_file.name, answer_file.name],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "TLE"

    return JUDGE_STATUS_LABELS.get(result.returncode, "RE")


def normalize_cases(raw_cases: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(raw_cases, start=1):
        normalized.append(
            {
                "id": str(item.get("id") or f"case-{index}"),
                "name": str(item.get("name") or f"data{index}"),
                "input": str(item.get("input") or ""),
                "output": str(item.get("output") or ""),
            }
        )
    return normalized


def judge_cases(uuid_dir: Path, cases: list[dict[str, str]]) -> tuple[list[dict[str, str]], str, bool]:
    spj_source = uuid_dir / "spj.cpp"
    std_source = uuid_dir / "std.cpp"
    spj_executable = uuid_dir / f"spj{EXECUTABLE_SUFFIX}"
    std_executable = uuid_dir / f"std{EXECUTABLE_SUFFIX}"

    spj_ok, spj_message = compile_cpp(spj_source, spj_executable, uuid_dir)
    if not spj_ok:
        return (
            [{"id": case["id"], "status": "SPJ_CE"} for case in cases],
            f"SPJ 编译失败：{spj_message}" if spj_message else "SPJ 编译失败",
            False,
        )

    if not cases:
        return [], "文件已生成，当前没有测试点可执行", True

    std_ok, std_message = compile_cpp(std_source, std_executable, uuid_dir)
    if not std_ok:
        return (
            [{"id": case["id"], "status": "STD_CE"} for case in cases],
            f"STD 编译失败：{std_message}" if std_message else "STD 编译失败",
            False,
        )

    results: list[dict[str, str]] = []
    ac_count = 0

    used_case_names: set[str] = set()

    for index, case in enumerate(cases, start=1):
        base_name = sanitize_case_name(case.get("name"), index)
        original_base_name = base_name
        suffix = 2
        while base_name in used_case_names:
            base_name = f"{original_base_name}_{suffix}"
            suffix += 1
        used_case_names.add(base_name)

        input_file = uuid_dir / f"{base_name}.in"
        answer_file = uuid_dir / f"{base_name}.out"
        user_output_file = uuid_dir / f"{base_name}.user.out"

        write_text_file(input_file, case["input"])
        write_text_file(answer_file, case["output"])

        solution_status = run_solution(std_executable, input_file, user_output_file, uuid_dir)
        if solution_status != "OK":
            results.append({"id": case["id"], "status": solution_status})
            continue

        judge_status = run_checker(spj_executable, input_file, user_output_file, answer_file, uuid_dir)
        if judge_status == "AC":
            ac_count += 1
        results.append({"id": case["id"], "status": judge_status})

    success = ac_count == len(cases)
    message = f"共 {len(cases)} 个测试点，AC {ac_count} 个，未通过 {len(cases) - ac_count} 个"
    return results, message, success


def is_downloadable_file(path: Path) -> bool:
    if not path.is_file():
        return False
    # exclude std source and judge results (but keep judge.yaml)
    if path.name in {"std.cpp", "judge_results.json", "std", "std.exe"}:
        return False
    return True


def list_downloadable_files(uuid: str | None = None) -> list[str]:
    files: list[str] = []
    root = CODE_ROOT / uuid if uuid else CODE_ROOT
    if uuid and not root.exists():
        return []

    for path in root.rglob("*"):
        if is_downloadable_file(path):
            files.append(path.name)
    return sorted(files)


def build_uuid_zip(uuid_dir: Path) -> None:
    zip_path = uuid_dir / "all.zip"
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(uuid_dir.rglob("*")):
            print(f"Adding {path} to zip")
            # filter using is_downloadable_file, which now excludes std.cpp, judge_results.json, etc.
            if path == zip_path or not is_downloadable_file(path):
                continue
            archive.write(path, path.relative_to(uuid_dir).as_posix())


def build_global_zip(uuid: str | None = None) -> io.BytesIO:
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative_path in list_downloadable_files(uuid):
            if relative_path.endswith("/all.zip") or relative_path == "all.zip":
                continue
            path = CODE_ROOT / relative_path
            # for global zip include the full relative path (includes uuid folder)
            archive.write(path, relative_path)
    memory_file.seek(0)
    return memory_file


@app.post("/spjmaker/api/submit-data")
def submit_data() -> Any:
    payload = request.get_json(silent=True) or {}

    try:
        uuid = validate_uuid(payload.get("uuid"))
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc), "cases": []}), 400

    spj_code = str(payload.get("spjCode") or "")
    std_code = str(payload.get("stdCode") or "")
    cases = normalize_cases(payload.get("cases") or [])

    if not spj_code.strip():
        return jsonify({"success": False, "message": "SPJ 代码不能为空", "cases": []}), 400

    try:
        uuid_dir = prepare_uuid_dir(uuid)
        write_text_file(uuid_dir / "spj.cpp", spj_code)
        if std_code.strip():
            write_text_file(uuid_dir / "std.cpp", std_code)
        else:
            write_text_file(uuid_dir / "std.cpp", "int main(){return 0;}\n")

        results, message, success = judge_cases(uuid_dir, cases)
        write_text_file(uuid_dir / "judge_results.json", json.dumps(results, ensure_ascii=False, indent=2))
        # also output a simple YAML manifest
        write_judge_yaml(uuid_dir / "judge.yaml", True, bool(std_code.strip()), cases)
        build_uuid_zip(uuid_dir)
        schedule_cleanup(uuid)

        return jsonify(
            {
                "success": success,
                "message": message,
                "cases": results,
                "fileCount": len(list_downloadable_files()),
            }
        )
    except FileNotFoundError as exc:
        return jsonify({"success": False, "message": str(exc), "cases": []}), 500
    except Exception as exc:  # noqa: BLE001
        return jsonify({"success": False, "message": f"后端处理失败：{exc}", "cases": []}), 500


@app.post("/spjmaker/api/process")
def process_cases_api() -> Any:
    payload = request.get_json(silent=True) or {}
    cases = normalize_cases(payload.get("cases") or [])
    return jsonify([{"id": case["id"], "status": "PENDING"} for case in cases])


@app.get("/spjmaker/api/files")
def list_files_api() -> Any:
    raw_uuid = request.args.get("uuid")
    uuid = validate_uuid(raw_uuid) if raw_uuid else None
    return jsonify(list_downloadable_files(uuid))


@app.get("/spjmaker/api/download/<path:name>")
def download_file_api(name: str) -> Any:
    print(f"Download request for {name}")
    raw_uuid = request.args.get("uuid")
    uuid = validate_uuid(raw_uuid) if raw_uuid else None
    # print(uuid, name)
    target = (CODE_ROOT / uuid / name).resolve()
    try:
        target.relative_to(CODE_ROOT.resolve())
    except ValueError:
        abort(400)

    
    if not target.exists() or not target.is_file():
        app.logger.info("download failed, target missing: %s", target)
        abort(404)

    # if the file exists but is empty, Flask/send_file may return a 204 No
    # Content which the frontend considers an error.  Treat zero-byte files as
    # not-found so the client gets a 404 instead and can surface a message.
    size = target.stat().st_size
    app.logger.info("target = %s size=%d", target, size)
    if size == 0:
        app.logger.warning("file %s is zero bytes, returning 404 to avoid 204", target)
        abort(404)

    if uuid:
        if UUID_PATTERN.fullmatch(uuid):
            schedule_cleanup(uuid)

    return send_file(target, as_attachment=True, download_name=target.name, conditional=False)


@app.get("/spjmaker/api/health")
def health_check() -> Any:
    return jsonify({"ok": True, "compiler": CPP_COMPILER is not None})


# catch-all for client-side routing; serve index for unknown paths
@app.get("/spjmaker")
def serve_spa() -> Any:
    return app.send_static_file("index.html")


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host=host, port=port)
