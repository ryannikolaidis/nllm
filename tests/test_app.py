"""Tests for main application logic."""

from unittest.mock import Mock, patch

from nllm.app import _build_cli_args, run


class TestRunNllm:
    """Test main nllm application function."""

    @patch("nllm.app.check_llm_available")
    @patch("nllm.app.NllmExecutor")
    @patch("nllm.app.load_config")
    @patch("nllm.app.asyncio.run")
    def test_run_success(
        self, mock_asyncio_run, mock_load_config, mock_executor_class, mock_check_llm
    ):
        """Test successful nllm run."""
        # Mock config loading
        from nllm.models import ModelConfig, NllmConfig

        config = NllmConfig(models=[ModelConfig(name="gpt-4", options=[])])
        mock_load_config.return_value = (config, [])

        # Mock llm availability
        mock_check_llm.return_value = (True, "0.10.0")

        # Mock executor
        mock_executor = Mock()
        mock_executor.execute_all.return_value = []
        mock_executor.get_exit_code.return_value = 0
        mock_executor.results = []  # Add results property
        mock_executor_class.return_value = mock_executor

        # Mock asyncio.run to return the mocked result
        mock_asyncio_run.return_value = []

        # Run prompter
        results = run(
            cli_models=["gpt-4"],
            llm_args=["Hello world"],
        )

        assert results.exit_code == 0
        assert results.success is True
        mock_asyncio_run.assert_called_once()
        mock_executor.print_summary.assert_called_once()

    @patch("nllm.app.load_config")
    def test_run_no_models(self, mock_load_config):
        """Test nllm run with no models specified."""
        from nllm.models import ModelConfig, NllmConfig
        from nllm.utils import ConfigError
        import pytest

        config = NllmConfig(models=[])
        mock_load_config.return_value = (config, [])

        with pytest.raises(ConfigError):
            run(quiet=True)

    @patch("nllm.app.check_llm_available")
    @patch("nllm.app.load_config")
    def test_run_llm_not_available(self, mock_load_config, mock_check_llm):
        """Test nllm run when llm command not available."""
        from nllm.models import ModelConfig, NllmConfig

        config = NllmConfig(models=[ModelConfig(name="gpt-4", options=[])])
        mock_load_config.return_value = (config, [])

        # Mock llm not available
        mock_check_llm.return_value = (False, None)

        from nllm.utils import ExecutionError
        import pytest

        with pytest.raises(ExecutionError):
            run(cli_models=["gpt-4"], quiet=True)

    @patch("nllm.app.check_llm_available")
    @patch("nllm.app.load_config")
    @patch("nllm.app.asyncio.run")
    def test_run_dry_run(self, mock_asyncio_run, mock_load_config, mock_check_llm):
        """Test nllm dry run mode."""
        from nllm.models import ModelConfig, NllmConfig

        config = NllmConfig(models=[ModelConfig(name="gpt-4", options=[])])
        mock_load_config.return_value = (config, [])

        # Should not check llm availability in dry run
        with patch("nllm.app.NllmExecutor") as mock_executor_class:
            mock_executor = Mock()
            mock_executor.execute_all.return_value = []
            mock_executor.get_exit_code.return_value = 0
            mock_executor.results = []  # Add results attribute
            mock_executor_class.return_value = mock_executor

            # Mock asyncio.run
            mock_asyncio_run.return_value = []

            results = run(
                cli_models=["gpt-4"],
                dry_run=True,
                llm_args=["test"],
            )

            assert results.exit_code == 0
            # Should not check llm in dry run
            mock_check_llm.assert_not_called()
            mock_asyncio_run.assert_called_once()

    @patch("nllm.app.load_config")
    def test_run_config_error(self, mock_load_config):
        """Test nllm run with configuration error."""
        from nllm.utils import ConfigError

        mock_load_config.side_effect = ConfigError("Invalid config")

        import pytest
        with pytest.raises(ConfigError):
            run(quiet=True)

    @patch("nllm.app.check_llm_available")
    @patch("nllm.app.NllmExecutor")
    @patch("nllm.app.load_config")
    def test_run_execution_error(
        self, mock_load_config, mock_executor_class, mock_check_llm
    ):
        """Test nllm run with execution error."""
        from nllm.models import ModelConfig, NllmConfig
        from nllm.utils import ExecutionError

        config = NllmConfig(models=[ModelConfig(name="gpt-4", options=[])])
        mock_load_config.return_value = (config, [])
        mock_check_llm.return_value = (True, "0.10.0")

        # Mock executor to raise error
        mock_executor = Mock()
        mock_executor.execute_all.side_effect = ExecutionError("Execution failed")
        mock_executor_class.return_value = mock_executor

        import pytest
        with pytest.raises(ExecutionError):
            run(cli_models=["gpt-4"], quiet=True)

    @patch("nllm.app.check_llm_available")
    @patch("nllm.app.NllmExecutor")
    @patch("nllm.app.load_config")
    def test_run_keyboard_interrupt(
        self, mock_load_config, mock_executor_class, mock_check_llm
    ):
        """Test nllm run with keyboard interrupt."""
        from nllm.models import ModelConfig, NllmConfig

        config = NllmConfig(models=[ModelConfig(name="gpt-4", options=[])])
        mock_load_config.return_value = (config, [])
        mock_check_llm.return_value = (True, "0.10.0")

        # Mock executor to raise KeyboardInterrupt
        mock_executor = Mock()
        mock_executor.execute_all.side_effect = KeyboardInterrupt()
        mock_executor_class.return_value = mock_executor

        exit_code = run(cli_models=["gpt-4"], quiet=True)

        assert exit_code == 1

    def test_run_with_all_options(self, tmp_path):
        """Test nllm run with all CLI options."""
        with (
            patch("nllm.app.load_config") as mock_load_config,
            patch("nllm.app.check_llm_available") as mock_check_llm,
            patch("nllm.app.NllmExecutor") as mock_executor_class,
            patch("nllm.app.asyncio.run") as mock_asyncio_run,
        ):
            from nllm.models import ModelConfig, NllmConfig

            config = NllmConfig()
            mock_load_config.return_value = (config, [])
            mock_check_llm.return_value = (True, "0.10.0")

            mock_executor = Mock()
            mock_executor.execute_all.return_value = []
            mock_executor.get_exit_code.return_value = 0
            mock_executor_class.return_value = mock_executor

            # Mock asyncio.run
            mock_asyncio_run.return_value = []

            exit_code = run(
                cli_models=["gpt-4", "claude-3-sonnet"],
                config_path=str(tmp_path / "config.yaml"),
                outdir=str(tmp_path / "output"),
                parallel=8,
                timeout=300,
                retries=2,
                stream=False,
                raw=True,
                dry_run=False,
                quiet=False,
                llm_args=["-t", "0.7", "Hello world"],
            )

            assert exit_code == 0

            # Check that config was merged with CLI args
            call_args = mock_executor_class.call_args[0][0]  # ExecutionContext
            assert call_args.config.parallel == 8
            assert call_args.config.timeout == 300
            assert call_args.config.retries == 2
            assert call_args.config.stream is False
            assert call_args.raw_output is True
            assert call_args.llm_args == ["-t", "0.7", "Hello world"]


class TestBuildCliArgs:
    """Test CLI argument reconstruction."""

    def test_build_cli_args_minimal(self):
        """Test building CLI args with minimal options."""
        args = _build_cli_args(
            cli_models=None,
            cli_model_options=None,
            config_path=None,
            outdir=None,
            parallel=None,
            timeout=None,
            retries=None,
            stream=None,
            raw=False,
            dry_run=False,
            quiet=False,
            llm_args=[],
        )

        assert args == ["nllm"]

    def test_build_cli_args_with_models(self):
        """Test building CLI args with models."""
        args = _build_cli_args(
            cli_models=["gpt-4", "claude-3-sonnet"],
            cli_model_options=None,
            config_path=None,
            outdir=None,
            parallel=None,
            timeout=None,
            retries=None,
            stream=None,
            raw=False,
            dry_run=False,
            quiet=False,
            llm_args=[],
        )

        expected = ["nllm", "-m", "gpt-4", "-m", "claude-3-sonnet"]
        assert args == expected

    def test_build_cli_args_with_all_options(self):
        """Test building CLI args with all options."""
        args = _build_cli_args(
            cli_models=["gpt-4"],
            config_path="/path/to/config.yaml",
            outdir="/output",
            parallel=8,
            timeout=300,
            retries=2,
            stream=True,
            raw=True,
            dry_run=True,
            quiet=True,
            llm_args=["Hello", "world"],
        )

        expected = [
            "nllm",
            "-m",
            "gpt-4",
            "-c",
            "/path/to/config.yaml",
            "-o",
            "/output",
            "--parallel",
            "8",
            "--timeout",
            "300",
            "--retries",
            "2",
            "--stream",
            "--raw",
            "--dry-run",
            "-q",
            "--",
            "Hello",
            "world",
        ]
        assert args == expected

    def test_build_cli_args_no_stream(self):
        """Test building CLI args with stream disabled."""
        args = _build_cli_args(
            cli_models=None,
            cli_model_options=None,
            config_path=None,
            outdir=None,
            parallel=None,
            timeout=None,
            retries=None,
            stream=False,
            raw=False,
            dry_run=False,
            quiet=False,
            llm_args=[],
        )

        expected = ["nllm", "--no-stream"]
        assert args == expected

    def test_build_cli_args_with_llm_args_only(self):
        """Test building CLI args with only llm arguments."""
        args = _build_cli_args(
            cli_models=None,
            cli_model_options=None,
            config_path=None,
            outdir=None,
            parallel=None,
            timeout=None,
            retries=None,
            stream=None,
            raw=False,
            dry_run=False,
            quiet=False,
            llm_args=["-t", "0.7", "Write a haiku"],
        )

        expected = ["nllm", "--", "-t", "0.7", "Write a haiku"]
        assert args == expected
