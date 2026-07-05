import pytest


def test_save_and_read_roundtrip(local_storage):
    url = local_storage.save("candidate-1", "resume.pdf", b"%PDF-1.4 fake content")
    assert url.startswith("local://")
    assert local_storage.exists(url)
    assert local_storage.read(url) == b"%PDF-1.4 fake content"


def test_save_rejects_empty_content(local_storage):
    with pytest.raises(ValueError):
        local_storage.save("candidate-1", "resume.pdf", b"")


def test_read_missing_file_raises(local_storage):
    with pytest.raises(FileNotFoundError):
        local_storage.read("local://candidate-1/does-not-exist.pdf")


def test_filename_is_sanitized(local_storage):
    url = local_storage.save("candidate-1", "../../etc/passwd.pdf", b"content")
    # The traversal sequence must not survive into the stored path.
    assert ".." not in url


def test_exists_returns_false_for_traversal_attempt(local_storage):
    malicious_url = "local://../../../etc/passwd"
    assert local_storage.exists(malicious_url) is False


def test_two_uploads_same_filename_do_not_collide(local_storage):
    url1 = local_storage.save("candidate-1", "resume.pdf", b"version one")
    url2 = local_storage.save("candidate-1", "resume.pdf", b"version two")
    assert url1 != url2
    assert local_storage.read(url1) == b"version one"
    assert local_storage.read(url2) == b"version two"
