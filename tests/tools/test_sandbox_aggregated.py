"""Tests for aggregated sandbox tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools.sandbox_aggregated import AggregatedSandboxToolKit


class TestAggregatedSandboxToolKit:
    """Test the aggregated sandbox tool kit."""
    
    @pytest.fixture
    def mock_sandbox(self):
        """Create a mock sandbox for testing."""
        sandbox = MagicMock()
        
        # Mock list_files to return a directory structure
        async def mock_list_files(path):
            if "/workspace" in path:
                return {
                    "success": True,
                    "files": [
                        {"name": "README.md", "type": "file", "size": 1000},
                        {"name": "pyproject.toml", "type": "file", "size": 500},
                        {"name": "src", "type": "directory"},
                        {"name": ".git", "type": "directory"},
                    ]
                }
            elif "/src" in path:
                return {
                    "success": True,
                    "files": [
                        {"name": "main.py", "type": "file", "size": 2000},
                        {"name": "__init__.py", "type": "file", "size": 100},
                    ]
                }
            return {"success": True, "files": []}
        
        # Mock read_file to return file content
        async def mock_read_file(path):
            key_files = {
                "/workspace/README.md": "# Test Project\n\nThis is a test project.",
                "/workspace/pyproject.toml": "[tool.poetry]\nname = \"test\"",
                "/workspace/src/main.py": "def main():\n    pass",
            }
            content = key_files.get(path)
            if content:
                return {"success": True, "content": content}
            return {"success": False, "error": "File not found"}
        
        sandbox.list_files = AsyncMock(side_effect=mock_list_files)
        sandbox.read_file = AsyncMock(side_effect=mock_read_file)
        
        async def mock_run_shell(cmd):
            if "find" in cmd and "*.py" in cmd:
                return {
                    "success": True,
                    "stdout": "/workspace/src/main.py\n/workspace/src/__init__.py"
                }
            return {"success": False, "stderr": "Command failed"}
        
        sandbox.run_shell = AsyncMock(side_effect=mock_run_shell)
        
        return sandbox
    
    @pytest.fixture
    def toolkit(self, mock_sandbox):
        """Create an AggregatedSandboxToolKit instance."""
        return AggregatedSandboxToolKit(mock_sandbox)
    
    @pytest.mark.asyncio
    async def test_get_repo_context(self, toolkit, mock_sandbox):
        """Test getting comprehensive repository context."""
        result = await toolkit.get_repo_context(
            repo_path="/workspace",
            max_depth=2,
            include_content=True,
        )
        
        assert result["success"] is True or "tree" in result
        assert "tree" in result
        assert "key_files" in result
        assert "stats" in result
        
        # Check tree structure
        tree = result["tree"]
        assert tree["name"] == "/workspace"
        assert tree["type"] == "directory"
        
        # Check stats
        stats = result["stats"]
        assert "total_files" in stats
        assert "total_dirs" in stats
        assert "file_types" in stats
        
        # Verify list_files was called
        assert mock_sandbox.list_files.called
    
    @pytest.mark.asyncio
    async def test_get_repo_context_exclude_patterns(self, toolkit, mock_sandbox):
        """Test that exclude patterns work correctly."""
        result = await toolkit.get_repo_context(
            repo_path="/workspace",
            exclude_patterns=[".git", "__pycache__"],
        )
        
        tree = result["tree"]
        child_names = [c["name"] for c in tree.get("children", [])]
        
        # .git should be excluded
        assert ".git" not in child_names
        # README should still be there
        assert "README.md" in child_names or "pyproject.toml" in child_names
    
    @pytest.mark.asyncio
    async def test_get_repo_context_no_content(self, toolkit, mock_sandbox):
        """Test getting repo context without file content."""
        result = await toolkit.get_repo_context(
            repo_path="/workspace",
            include_content=False,
        )
        
        # key_files should be empty when include_content=False
        assert result["key_files"] == {}
    
    @pytest.mark.asyncio
    async def test_batch_read_files(self, toolkit, mock_sandbox):
        """Test reading multiple files in a batch."""
        paths = [
            "/workspace/README.md",
            "/workspace/pyproject.toml",
            "/workspace/nonexistent.py",
        ]
        
        result = await toolkit.batch_read_files(paths)
        
        assert result["success_count"] == 2
        assert result["failed_count"] == 1
        assert len(result["files"]) == 3
        
        # Check successful reads
        assert result["files"]["/workspace/README.md"]["success"] is True
        assert "# Test Project" in result["files"]["/workspace/README.md"]["content"]
        
        # Check failed reads
        assert result["files"]["/workspace/nonexistent.py"]["success"] is False
    
    @pytest.mark.asyncio
    async def test_batch_read_files_truncation(self, toolkit, mock_sandbox):
        """Test that large files are truncated."""
        # Mock a large file
        large_content = "x" * 100000
        
        async def mock_read_large(path):
            return {"success": True, "content": large_content}
        
        mock_sandbox.read_file = AsyncMock(side_effect=mock_read_large)
        
        result = await toolkit.batch_read_files(
            ["/workspace/large_file.py"],
            max_file_size=1000,
        )
        
        content = result["files"]["/workspace/large_file.py"]["content"]
        assert "truncated" in content
        assert len(content) < len(large_content)
    
    @pytest.mark.asyncio
    async def test_find_files_by_pattern(self, toolkit, mock_sandbox):
        """Test finding files by pattern."""
        result = await toolkit.find_files_by_pattern(
            repo_path="/workspace",
            pattern="*.py",
        )
        
        assert result["success"] is True
        assert result["pattern"] == "*.py"
        assert len(result["matches"]) == 2
        assert all(m.endswith(".py") for m in result["matches"])
    
    @pytest.mark.asyncio
    async def test_find_files_fallback(self, toolkit, mock_sandbox):
        """Test that fallback search works when find command fails."""
        # Make find command fail
        mock_sandbox.run_shell = AsyncMock(return_value={
            "success": False,
            "stderr": "find: command not found"
        })
        
        result = await toolkit.find_files_by_pattern(
            repo_path="/workspace",
            pattern="*.py",
        )
        
        # Should still succeed using fallback
        assert result["success"] is True
        assert "matches" in result
    
    @pytest.mark.asyncio
    async def test_should_exclude(self, toolkit):
        """Test the exclude pattern matching."""
        patterns = [".git", "__pycache__", "*.pyc"]
        
        assert toolkit._should_exclude(".git", patterns) is True
        assert toolkit._should_exclude("__pycache__", patterns) is True
        assert toolkit._should_exclude("test.pyc", patterns) is True
        assert toolkit._should_exclude("main.py", patterns) is False
    
    def test_as_tool_kits(self, toolkit):
        """Test that tool kit mapping is correct."""
        kits = toolkit.as_tool_kits()
        
        assert "GetRepoContext" in kits
        assert "BatchReadFiles" in kits
        assert "FindFilesByPattern" in kits
        
        # Verify callables
        assert callable(kits["GetRepoContext"])
        assert callable(kits["BatchReadFiles"])
        assert callable(kits["FindFilesByPattern"])


class TestAggregatedToolsIntegration:
    """Integration tests for aggregated tools."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test a complete workflow using aggregated tools."""
        sandbox = MagicMock()
        
        # Set up realistic responses
        async def list_files(path):
            structures = {
                "/workspace": {
                    "success": True,
                    "files": [
                        {"name": "README.md", "type": "file", "size": 100},
                        {"name": "src", "type": "directory"},
                    ]
                },
                "/workspace/src": {
                    "success": True,
                    "files": [
                        {"name": "main.py", "type": "file", "size": 200},
                    ]
                }
            }
            return structures.get(path, {"success": True, "files": []})
        
        async def read_file(path):
            files = {
                "/workspace/README.md": {"success": True, "content": "# Project"},
                "/workspace/src/main.py": {"success": True, "content": "print('hello')"},
            }
            return files.get(path, {"success": False, "error": "Not found"})
        
        sandbox.list_files = AsyncMock(side_effect=list_files)
        sandbox.read_file = AsyncMock(side_effect=read_file)
        sandbox.run_shell = AsyncMock(return_value={
            "success": True,
            "stdout": "/workspace/src/main.py"
        })
        
        toolkit = AggregatedSandboxToolKit(sandbox)
        
        # Get repo context
        context = await toolkit.get_repo_context("/workspace")
        assert "tree" in context
        
        # Find Python files
        py_files = await toolkit.find_files_by_pattern("/workspace", "*.py")
        assert py_files["count"] > 0
        
        # Read found files
        if py_files["matches"]:
            batch_result = await toolkit.batch_read_files(py_files["matches"])
            assert batch_result["success_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
