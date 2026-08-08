from unittest.mock import MagicMock, patch

import pytest

from atlas.hands.desktop_hands import DesktopHands, DesktopHandsError


def _fake_completed(returncode=0, stdout=b"", stderr=b""):
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


def test_move_mouse_calls_real_powershell_with_the_real_coordinates():
    with patch("subprocess.run", return_value=_fake_completed()) as mock_run:
        hands = DesktopHands()
        result = hands.execute_steps([{"kind": "move_mouse", "params": {"x": 400, "y": 300}}])

    assert result[0]["success"] is True
    call_args = mock_run.call_args
    script = call_args[0][0][-1]
    assert "400" in script and "300" in script


def test_type_text_escapes_sendkeys_special_characters():
    with patch("subprocess.run", return_value=_fake_completed()) as mock_run:
        hands = DesktopHands()
        hands.execute_steps([{"kind": "type_text", "params": {"text": "price: $47 (special!)"}}])

    call_kwargs = mock_run.call_args
    stdin_text = call_kwargs.kwargs["input"].decode("utf-8")
    assert "{(}" in stdin_text and "{)}" in stdin_text  # real parens escaped for SendKeys


def test_send_keys_does_not_escape_raw_syntax():
    with patch("subprocess.run", return_value=_fake_completed()) as mock_run:
        hands = DesktopHands()
        hands.execute_steps([{"kind": "send_keys", "params": {"keys": "{ENTER}"}}])

    call_kwargs = mock_run.call_args
    stdin_text = call_kwargs.kwargs["input"].decode("utf-8")
    assert stdin_text == "{ENTER}"


def test_launch_app_returns_a_real_pid():
    fake_proc = MagicMock(pid=12345)
    with patch("subprocess.Popen", return_value=fake_proc):
        hands = DesktopHands()
        result = hands.execute_steps([{"kind": "launch_app", "params": {"path": "notepad.exe"}}])

    assert result[0]["success"] is True
    assert result[0]["pid"] == 12345


def test_launch_app_wraps_a_real_failure_loudly():
    with patch("subprocess.Popen", side_effect=OSError("real file not found")):
        hands = DesktopHands()
        with pytest.raises(DesktopHandsError, match="real file not found"):
            hands.execute_steps([{"kind": "launch_app", "params": {"path": "does-not-exist.exe"}}])


def test_close_app_raises_loudly_on_a_real_failure():
    with patch("subprocess.run", return_value=_fake_completed(returncode=1, stderr=b"real: no such process")):
        hands = DesktopHands()
        with pytest.raises(DesktopHandsError, match="real: no such process"):
            hands.execute_steps([{"kind": "close_app", "params": {"process_name": "notepad.exe"}}])


def test_close_app_succeeds_on_a_real_success():
    with patch("subprocess.run", return_value=_fake_completed(returncode=0, stdout=b"SUCCESS")):
        hands = DesktopHands()
        result = hands.execute_steps([{"kind": "close_app", "params": {"process_name": "notepad.exe"}}])

    assert result[0]["success"] is True


def test_click_mouse_rejects_an_unsupported_button():
    hands = DesktopHands()
    with pytest.raises(DesktopHandsError, match="unsupported mouse button"):
        hands.execute_steps([{"kind": "click_mouse", "params": {"button": "middle"}}])


def test_execute_steps_stops_at_the_first_real_failure():
    with patch("subprocess.run", return_value=_fake_completed(returncode=1, stderr=b"real powershell failure")):
        hands = DesktopHands()
        with pytest.raises(DesktopHandsError):
            hands.execute_steps([
                {"kind": "move_mouse", "params": {"x": 1, "y": 1}},
                {"kind": "type_text", "params": {"text": "should never run"}},
            ])


def test_name_is_desktop_hands():
    assert DesktopHands().name == "desktop_hands"
