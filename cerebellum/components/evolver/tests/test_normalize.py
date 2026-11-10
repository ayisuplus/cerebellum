from evolver.normalize import strip_noise, normalize_input


def test_strip_system_reminder_tags():
    text = "Before\n<system-reminder>some config</system-reminder>\nAfter"
    result = strip_noise(text)
    assert "system-reminder" not in result
    assert "Before" in result
    assert "After" in result


def test_strip_command_message_tags():
    text = "Hello\n<command-message>run tests</command-message>\nWorld"
    result = strip_noise(text)
    assert "command-message" not in result
    assert "Hello" in result
    assert "World" in result


def test_strip_hook_output_lines():
    text = "Content\nRan 2 Stop hook\nMore content"
    result = strip_noise(text)
    assert "Ran 2 Stop hook" not in result
    assert "Content" in result
    assert "More content" in result


def test_strip_collapsed_lines_marker():
    text = "Code\n… +42 lines\nEnd"
    result = strip_noise(text)
    assert "… +42 lines" not in result
    assert "Code" in result
    assert "End" in result


def test_strip_noise_preserves_user_prose():
    text = "I wrote a system-reminder handler for the app."
    result = strip_noise(text)
    assert "system-reminder handler" in result


def test_normalize_input_passes_clean_text():
    text = "Clean text with no noise."
    result = normalize_input(text)
    assert result == text


def test_normalize_input_strips_noise():
    text = "Before\n<system-reminder>noise</system-reminder>\nAfter"
    result = normalize_input(text)
    assert "noise" not in result
    assert "Before" in result
