from usr.plugins.realtime_voice.helpers.config import DEFAULT_CONFIG, normalize_config


def test_defaults_when_config_missing():
    assert normalize_config(None) == DEFAULT_CONFIG
    assert normalize_config({}) == DEFAULT_CONFIG


def test_invalid_values_fall_back_to_defaults():
    cfg = normalize_config(
        {
            "model": "   ",
            "voice": "robot",
            "turn_detection": "push_to_talk",
            "vad_eagerness": "extreme",
            "history_messages": "lots",
            "max_result_chars": -5,
        }
    )
    assert cfg["model"] == DEFAULT_CONFIG["model"]
    assert cfg["voice"] == DEFAULT_CONFIG["voice"]
    assert cfg["turn_detection"] == "semantic_vad"
    assert cfg["vad_eagerness"] == "auto"
    assert cfg["history_messages"] == DEFAULT_CONFIG["history_messages"]
    assert cfg["max_result_chars"] == 500  # clamped to the minimum


def test_valid_values_are_kept_and_normalized():
    cfg = normalize_config(
        {
            "model": "gpt-realtime-mini",
            "voice": "Cedar",
            "turn_detection": "server_vad",
            "transcription_language": "AUTO",
            "history_messages": 100,
        }
    )
    assert cfg["model"] == "gpt-realtime-mini"
    assert cfg["voice"] == "cedar"
    assert cfg["turn_detection"] == "server_vad"
    assert cfg["transcription_language"] == ""
    assert cfg["history_messages"] == 50


def test_empty_transcription_model_disables_captions():
    assert normalize_config({"transcription_model": ""})["transcription_model"] == ""
    assert normalize_config({})["transcription_model"] == DEFAULT_CONFIG["transcription_model"]
