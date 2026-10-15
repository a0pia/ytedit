"""Bootstrap regressions using fake tools; never install packages or use a network."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not Path('/bin/bash').exists(), reason='Unix launcher requires Bash')


@pytest.fixture
def bootstrap(tmp_path, monkeypatch):
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'bin').mkdir()
    for name in ('setup.sh', 'Start-Hype-Studio.command', 'start.sh'):
        shutil.copyfile(ROOT / 'scripts' / name, tmp_path / 'scripts' / name)
    (tmp_path / '.env.example').write_text('HYPE_PORT=8787\n')
    (tmp_path / 'requirements.txt').write_text('')
    log = tmp_path / 'calls.log'

    def binary(name, body):
        executable = tmp_path / 'bin' / name
        executable.write_text('#!/bin/bash\nset -eu\n' + body)
        executable.chmod(0o755)
        return executable

    for name in ('python3', 'python3.14', 'python3.13', 'python3.11'):
        binary(name, 'echo "old-python:$0" >> "$HYPE_TEST_LOG"\nexit 1\n')
    binary('python3.12', '''echo "selected-python:$0 $*" >> "$HYPE_TEST_LOG"
if [[ "${1:-}" == '-m' && "${2:-}" == 'venv' ]]; then
  /bin/mkdir -p "$3/bin"
  /bin/cp "$0" "$3/bin/python"
fi
''')
    binary('node', 'echo "node:$*" >> "$HYPE_TEST_LOG"\n')
    binary('npm', 'echo "npm:$* PATH=$PATH" >> "$HYPE_TEST_LOG"\n')
    for name in ('ffmpeg', 'ffprobe'):
        binary(name, 'exit 0\n')
    binary('uname', 'echo Linux\n')
    monkeypatch.delenv('HYPE_PYTHON', raising=False)
    monkeypatch.delenv('BASH_ENV', raising=False)
    monkeypatch.setenv('PATH', f'{tmp_path}/bin:/usr/bin:/bin')
    monkeypatch.setenv('HYPE_TEST_LOG', str(log))

    def run(script='setup.sh', **changes):
        return subprocess.run(['/bin/bash', f'scripts/{script}'], cwd=tmp_path,
                              env={**os.environ, **changes}, text=True,
                              capture_output=True, timeout=10)

    return tmp_path, log, binary, run


def test_old_system_python_falls_back_to_supported_versioned_python(bootstrap):
    root, log, _, run = bootstrap
    result = run()
    assert result.returncode == 0, result.stderr
    calls = log.read_text()
    assert f'old-python:{root}/bin/python3' in calls
    assert f'selected-python:{root}/bin/python3.12 -m venv' in calls
    assert (root / '.venv/bin/python').is_file()


def test_explicit_unsupported_python_fails_without_installing(bootstrap):
    root, log, _, run = bootstrap
    result = run(HYPE_PYTHON=str(root / 'bin/python3'))
    assert result.returncode != 0
    assert 'HYPE_PYTHON' in result.stdout
    assert 'npm:' not in log.read_text()


def test_gui_launcher_adds_homebrew_paths(bootstrap):
    root, log, binary, run = bootstrap
    assert run().returncode == 0
    binary('uname', 'echo Darwin\n')
    electron = root / 'node_modules/electron'
    electron.mkdir(parents=True)
    (electron / 'path.txt').write_text('Electron.app/Contents/MacOS/Electron')
    # Intercept exec itself so this is safe even on a Mac with real Homebrew npm.
    bash_env = root / 'intercept-exec.sh'
    bash_env.write_text('exec() { echo "launch:$* PATH=$PATH" >> "$HYPE_TEST_LOG"; }\n')
    result = run('Start-Hype-Studio.command', BASH_ENV=str(bash_env))
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines()[-1].startswith(
        'launch:npm start PATH=/opt/homebrew/bin:/usr/local/bin:')


def test_repeated_setup_preserves_local_configuration(bootstrap):
    root, _, _, run = bootstrap
    (root / '.env').write_text('HYPE_PORT=9876\n')
    assert run().returncode == 0
    assert run().returncode == 0
    assert (root / '.env').read_text() == 'HYPE_PORT=9876\n'
