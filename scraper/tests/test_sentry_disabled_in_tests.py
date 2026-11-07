import os


def test_sentry_dsn_is_empty_under_pytest():
    assert os.environ.get("SENTRY_DSN") == ""


def test_load_dotenv_does_not_restore_dsn(tmp_path):
    from dotenv import load_dotenv

    env = tmp_path / ".env"
    env.write_text("SENTRY_DSN=https://example.invalid/1\n")
    load_dotenv(str(env))
    assert os.environ.get("SENTRY_DSN") == ""
