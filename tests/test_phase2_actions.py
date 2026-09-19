from app import _chat_request_id, _pc_action_for_message


def test_normal_chat_does_not_create_pc_action():
    assert _pc_action_for_message("Hello") == (None, None)
    assert _pc_action_for_message("What is Notepad?") == (None, None)
    assert _pc_action_for_message("Tell me about batteries") == (None, None)


def test_supported_pc_actions_use_canonical_envelope():
    expected = {
        "Open Notepad": ("OPEN_APP", {"app": "notepad"}),
        "Close Notepad": ("CLOSE_APP", {"app": "notepad"}),
        "What time is it on my PC?": ("GET_PC_TIME", {}),
        "What is my PC battery?": ("GET_BATTERY", {}),
        "Show my active window": ("GET_ACTIVE_WINDOW", {}),
    }
    for message, (action_type, args) in expected.items():
        action, result = _pc_action_for_message(message)
        assert result is None
        assert action is not None
        assert action.protocol_version == "1.0"
        assert action.device.kind == "pc"
        assert action.device.id == "local-pc"
        assert action.type == action_type
        assert action.args == args
        assert action.request_id != _chat_request_id(None)


def test_disallowed_application_is_rejected_without_an_action():
    action, result = _pc_action_for_message("Open UnknownApp")
    assert action is None
    assert result is not None
    assert result.success is False
    assert result.error is not None
    assert result.error.code == "APP_NOT_ALLOWED"
