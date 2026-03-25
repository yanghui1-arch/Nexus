import pytest

from src.sandbox import CodeSandbox, SandboxConfig, PYTHON_312, NODE_20, JAVA_21


# ── Python ────────────────────────────────────────────────────────────────────

@pytest.fixture
async def py_sandbox():
    async with CodeSandbox(PYTHON_312) as sbx:
        yield sbx


@pytest.mark.integration
async def test_python_run_code(py_sandbox):
    result = await py_sandbox.run_code("print('hello from python')")

    assert result["success"] is True
    assert "hello from python" in result["stdout"]


@pytest.mark.integration
async def test_python_run_code_multiline(py_sandbox):
    result = await py_sandbox.run_code("x = 6\ny = 7\nprint(x * y)")

    assert result["success"] is True
    assert "42" in result["stdout"]


@pytest.mark.integration
async def test_python_run_code_error(py_sandbox):
    result = await py_sandbox.run_code("raise ValueError('boom')")

    assert result["success"] is False
    assert "ValueError" in result["error"] or "boom" in result["error"]


# ── Node.js ───────────────────────────────────────────────────────────────────

@pytest.fixture
async def node_sandbox():
    async with CodeSandbox(NODE_20) as sbx:
        yield sbx


@pytest.mark.integration
async def test_node_run_code(node_sandbox):
    result = await node_sandbox.run_code("console.log('hello from node')")

    assert result["success"] is True
    assert "hello from node" in result["stdout"]


@pytest.mark.integration
async def test_node_run_code_error(node_sandbox):
    result = await node_sandbox.run_code("throw new Error('boom')")

    assert result["success"] is False
    assert result["error"] is not None


# ── Java ──────────────────────────────────────────────────────────────────────

@pytest.fixture
async def java_sandbox():
    async with CodeSandbox(JAVA_21) as sbx:
        yield sbx


@pytest.mark.integration
async def test_java_run_code(java_sandbox):
    code = 'class _nexus_exec { public static void main(String[] a) { System.out.println("hello from java"); } }'
    result = await java_sandbox.run_code(code)

    assert result["success"] is True
    assert "hello from java" in result["stdout"]


# ── Custom image ──────────────────────────────────────────────────────────────

@pytest.mark.integration
async def test_custom_config():
    cfg = SandboxConfig(image="python:3.11-slim", code_runner="python", code_ext=".py")
    async with CodeSandbox(cfg) as sandbox:
        result = await sandbox.run_code("import sys; print(sys.version)")

    assert result["success"] is True
    assert "3.11" in result["stdout"]


# ── Shared operations (file I/O, commands) ────────────────────────────────────

@pytest.fixture
async def sandbox():
    async with CodeSandbox(PYTHON_312) as sbx:
        yield sbx


@pytest.mark.integration
async def test_run_command(sandbox):
    result = await sandbox.run_command("echo 'nexus sandbox'")

    assert result["success"] is True
    assert "nexus sandbox" in result["stdout"]
    assert result["exit_code"] == 0


@pytest.mark.integration
async def test_run_command_failure(sandbox):
    result = await sandbox.run_command("exit 1")

    assert result["success"] is False
    assert result["exit_code"] != 0


@pytest.mark.integration
async def test_append_file(sandbox):
    await sandbox.write_file("/workspace/log.txt", "line1\n")
    await sandbox.append_file("/workspace/log.txt", "line2\n")
    await sandbox.append_file("/workspace/log.txt", "line3\n")
    result = await sandbox.read_file("/workspace/log.txt")

    assert result["success"] is True
    assert result["content"] == "line1\nline2\nline3\n"


@pytest.mark.integration
async def test_append_creates_file_if_missing(sandbox):
    result = await sandbox.append_file("/workspace/new.txt", "hello\n")

    assert result["success"] is True
    read = await sandbox.read_file("/workspace/new.txt")
    assert read["content"] == "hello\n"


@pytest.mark.integration
async def test_edit_file_change_line(sandbox):
    await sandbox.write_file("/workspace/cfg.py", "x = 1\ny = 2\n")
    result = await sandbox.edit_file("/workspace/cfg.py", "x = 1", "x = 99")

    assert result["success"] is True
    assert result["replaced"] is True
    read = await sandbox.read_file("/workspace/cfg.py")
    assert "x = 99" in read["content"]
    assert "x = 1" not in read["content"]


@pytest.mark.integration
async def test_edit_file_remove_line(sandbox):
    await sandbox.write_file("/workspace/cfg.py", "x = 1\ny = 2\n")
    await sandbox.edit_file("/workspace/cfg.py", "x = 1\n", "")
    read = await sandbox.read_file("/workspace/cfg.py")

    assert "x = 1" not in read["content"]
    assert "y = 2" in read["content"]


@pytest.mark.integration
async def test_edit_file_insert_after(sandbox):
    await sandbox.write_file("/workspace/cfg.py", "def foo():\n    pass\n")
    await sandbox.edit_file("/workspace/cfg.py", "def foo():\n", "def foo():\n    # inserted\n")
    read = await sandbox.read_file("/workspace/cfg.py")

    assert "# inserted" in read["content"]


@pytest.mark.integration
async def test_edit_file_old_str_not_found(sandbox):
    await sandbox.write_file("/workspace/cfg.py", "x = 1\n")
    result = await sandbox.edit_file("/workspace/cfg.py", "z = 99", "z = 0")

    assert result["success"] is False
    assert result["replaced"] is False



@pytest.mark.integration
async def test_write_and_read_file(sandbox):
    content = "print('written by nexus agent')"
    await sandbox.write_file("/workspace/agent.py", content)
    result = await sandbox.read_file("/workspace/agent.py")

    assert result["success"] is True
    assert result["content"] == content


@pytest.mark.integration
async def test_write_then_execute(sandbox):
    await sandbox.write_file("/workspace/add.py", "print(1 + 2)")
    result = await sandbox.run_command("python /workspace/add.py")

    assert result["success"] is True
    assert "3" in result["stdout"]


@pytest.mark.integration
async def test_list_files(sandbox):
    await sandbox.write_file("/workspace/foo.py", "x = 1")
    await sandbox.write_file("/workspace/bar.py", "x = 2")
    result = await sandbox.list_files("/workspace")

    assert result["success"] is True
    names = [f["name"] for f in result["files"]]
    assert "foo.py" in names
    assert "bar.py" in names


@pytest.mark.integration
async def test_state_persists_across_calls(sandbox):
    await sandbox.write_file("/workspace/state.py", "VALUE = 99")
    result = await sandbox.run_code(
        "import sys\nsys.path.insert(0, '/workspace')\nimport state\nprint(state.VALUE)"
    )

    assert result["success"] is True
    assert "99" in result["stdout"]
