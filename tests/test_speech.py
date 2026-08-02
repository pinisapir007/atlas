from unittest.mock import MagicMock, patch

from atlas.speech import listen, speak


def test_speak_returns_false_for_empty_text():
    assert speak("") is False


def test_speak_passes_text_via_stdin_not_command_interpolation():
    with patch("atlas.speech.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        result = speak("hello with 'quotes' and \"double quotes\" and $(injection attempt)")

        assert result is True
        _, kwargs = mock_run.call_args
        # The text must travel via stdin, never embedded into the command
        # string itself — that's what makes injection impossible here.
        assert kwargs["input"] == "hello with 'quotes' and \"double quotes\" and $(injection attempt)".encode("utf-8")
        command = mock_run.call_args[0][0]
        assert "injection attempt" not in " ".join(command)


def test_speak_returns_false_when_subprocess_unavailable():
    with patch("atlas.speech.subprocess.run", side_effect=FileNotFoundError("no powershell")):
        assert speak("hello") is False


def test_speak_returns_false_on_nonzero_exit(tmp_path):
    with patch("atlas.speech.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert speak("hello") is False


def test_speak_returns_false_on_timeout():
    import subprocess as sp

    with patch("atlas.speech.subprocess.run", side_effect=sp.TimeoutExpired(cmd="powershell", timeout=30)):
        assert speak("hello") is False


def test_speak_never_raises_on_unexpected_error():
    with patch("atlas.speech.subprocess.run", side_effect=RuntimeError("something odd")):
        assert speak("hello") is False


def test_listen_returns_recognized_text_on_success():
    with patch("atlas.speech.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="show me the approvals".encode("utf-8"))

        result = listen(timeout_seconds=5)

        assert result == "show me the approvals"


def test_listen_returns_none_when_nothing_was_captured():
    with patch("atlas.speech.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"")
        assert listen() is None


def test_listen_returns_none_when_powershell_unavailable():
    with patch("atlas.speech.subprocess.run", side_effect=FileNotFoundError("no powershell")):
        assert listen() is None


def test_listen_returns_none_on_timeout():
    import subprocess as sp

    with patch("atlas.speech.subprocess.run", side_effect=sp.TimeoutExpired(cmd="powershell", timeout=8)):
        assert listen() is None


def test_listen_never_raises_on_unexpected_error():
    with patch("atlas.speech.subprocess.run", side_effect=RuntimeError("odd")):
        assert listen() is None


def test_listen_passes_timeout_into_the_script():
    with patch("atlas.speech.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"")
        listen(timeout_seconds=12)
        script = mock_run.call_args[0][0][-1]
        assert "FromSeconds(12)" in script
        assert "__TIMEOUT__" not in script
