import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import notifier


def _job(title="Backend Engineer", relocation=True, score=15.5, is_remote=False, is_junior_labeled=False):
    return {
        "title": title,
        "company": "Acme Corp",
        "country": "Germany",
        "relocation_required": relocation,
        "score": score,
        "is_remote": is_remote,
        "is_junior_labeled": is_junior_labeled,
        "url": "https://example.com/job/1",
    }


def test_format_job_includes_all_required_fields():
    text = notifier.format_job(_job())
    assert "Backend Engineer" in text
    assert "Acme Corp" in text
    assert "Germany" in text
    assert "Score: 15.5" in text
    assert "https://example.com/job/1" in text
    assert "Relocation/visa sponsorship offered" in text


def test_format_job_pakistan_job_shows_no_relocation_note():
    text = notifier.format_job(_job(relocation=False))
    assert "No relocation needed" in text


def test_format_job_remote_job_shows_remote_note_even_if_relocation_required():
    """A remote job listed under a target country would otherwise say
    "Relocation/visa sponsorship offered", which is misleading - remote work
    doesn't require relocating anywhere."""
    text = notifier.format_job(_job(relocation=True, is_remote=True))
    assert "Remote - no relocation needed" in text
    assert "Relocation/visa sponsorship offered" not in text


def test_format_job_shows_junior_labeled_note_when_flagged():
    text = notifier.format_job(_job(is_junior_labeled=True))
    assert "Junior-labeled" in text


def test_format_job_omits_junior_labeled_note_when_not_flagged():
    text = notifier.format_job(_job(is_junior_labeled=False))
    assert "Junior-labeled" not in text


def test_format_job_escapes_html_special_characters():
    job = _job(title="C++ Engineer <Senior>")
    text = notifier.format_job(job)
    assert "<Senior>" not in text
    assert "&lt;Senior&gt;" in text


def test_build_digest_chunks_returns_empty_list_for_no_jobs():
    assert notifier.build_digest_chunks([]) == []


def test_build_digest_chunks_splits_large_batches_across_messages():
    jobs = [_job(title=f"Job {i}") for i in range(50)]
    chunks = notifier.build_digest_chunks(jobs)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= notifier.MAX_MESSAGE_CHARS


@patch("notifier.requests.post")
def test_send_telegram_message_posts_to_correct_url_with_payload(mock_post):
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"ok": True})
    notifier.send_telegram_message("hello", bot_token="TOKEN123", chat_id="999")

    called_url = mock_post.call_args.args[0]
    called_payload = mock_post.call_args.kwargs["data"]
    assert called_url == "https://api.telegram.org/botTOKEN123/sendMessage"
    assert called_payload["chat_id"] == "999"
    assert called_payload["text"] == "hello"
    assert called_payload["parse_mode"] == "HTML"


@patch("notifier.send_telegram_message")
def test_send_digest_sends_one_message_per_chunk(mock_send):
    jobs = [_job()]
    sent_count = notifier.send_digest(jobs, bot_token="TOKEN", chat_id="999")
    assert sent_count == 1
    assert mock_send.call_count == 1


@patch("notifier.send_telegram_message")
def test_send_digest_sends_nothing_for_empty_job_list(mock_send):
    sent_count = notifier.send_digest([], bot_token="TOKEN", chat_id="999")
    assert sent_count == 0
    mock_send.assert_not_called()
