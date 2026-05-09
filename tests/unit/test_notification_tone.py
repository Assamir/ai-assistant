import io
import wave

from backend.core.notification_tone import generate_ping_wav


def _parse_wav(data: bytes):
    buf = io.BytesIO(data)
    with wave.open(buf, "rb") as wf:
        return {
            "channels": wf.getnchannels(),
            "sampwidth": wf.getsampwidth(),
            "framerate": wf.getframerate(),
            "nframes": wf.getnframes(),
        }


def test_returns_bytes():
    result = generate_ping_wav()
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_valid_wav_header():
    result = generate_ping_wav()
    info = _parse_wav(result)
    assert info["channels"] == 1
    assert info["sampwidth"] == 2


def test_duration_matches_ms():
    sample_rate = 22050
    duration_ms = 200
    result = generate_ping_wav(duration_ms=duration_ms, sample_rate=sample_rate)
    info = _parse_wav(result)
    expected_frames = int(sample_rate * duration_ms / 1000)
    assert abs(info["nframes"] - expected_frames) <= 1


def test_sample_rate_propagated():
    result = generate_ping_wav(sample_rate=16000)
    info = _parse_wav(result)
    assert info["framerate"] == 16000


def test_short_duration():
    result = generate_ping_wav(duration_ms=50)
    info = _parse_wav(result)
    assert info["nframes"] > 0


def test_different_freq_same_format():
    r440 = generate_ping_wav(freq=440.0)
    r880 = generate_ping_wav(freq=880.0)
    i440 = _parse_wav(r440)
    i880 = _parse_wav(r880)
    assert i440["channels"] == i880["channels"]
    assert i440["nframes"] == i880["nframes"]
