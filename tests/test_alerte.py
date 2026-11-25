import smtplib
from unittest.mock import patch

import pandas as pd
import pytest

from alerte import SMTP_ATTEMPTS, construire_html, envoyer_email


def make_forecast(rows):
    dates = pd.date_range("2026-11-22 06:00", periods=len(rows), freq="h", tz="Europe/Paris")
    return pd.DataFrame({
        "date": dates,
        "vent": [r[0] for r in rows],
        "rafales": [r[0] + 5 for r in rows],
        "direction": [r[1] for r in rows],
    })


def test_html_lists_only_good_slots():
    # 06:00 too early, 07:00 too early, 08:00 good, 09:00 not enough wind
    previsions = {"Berck": make_forecast([(20, 250), (20, 250), (21, 250), (10, 250)])}
    html = construire_html(previsions)

    assert "Berck" in html
    assert "Dimanche 22 novembre" in html
    assert "8h00" in html
    assert "9h00" not in html
    assert "9m²" in html


def test_no_email_when_no_session():
    previsions = {"Berck": make_forecast([(5, 250), (8, 90)])}
    assert construire_html(previsions) is None


# --- Email sending -----------------------------------------------------------


@pytest.fixture
def email_env(monkeypatch):
    monkeypatch.setenv("EMAIL_USER", "destinataire@example.com")
    monkeypatch.setenv("EMAIL_FROM", "expediteur@example.com")
    monkeypatch.setenv("MDP_EMAIL", "mot-de-passe-fictif")


def test_email_retries_after_a_temporary_error(email_env):
    with patch("alerte.smtplib.SMTP") as mock_smtp, patch("alerte.time.sleep") as mock_sleep:
        server = mock_smtp.return_value.__enter__.return_value
        server.login.side_effect = [smtplib.SMTPServerDisconnected("closed"), None]

        envoyer_email("<p>test</p>")

    assert server.login.call_count == 2
    server.send_message.assert_called_once()
    mock_sleep.assert_called_once()


def test_email_gives_up_after_all_attempts(email_env):
    with patch("alerte.smtplib.SMTP") as mock_smtp, patch("alerte.time.sleep"):
        server = mock_smtp.return_value.__enter__.return_value
        server.login.side_effect = smtplib.SMTPServerDisconnected("closed")

        with pytest.raises(RuntimeError, match="tentatives"):
            envoyer_email("<p>test</p>")

    assert server.login.call_count == SMTP_ATTEMPTS


def test_wrong_password_is_not_retried(email_env):
    with patch("alerte.smtplib.SMTP") as mock_smtp, patch("alerte.time.sleep") as mock_sleep:
        server = mock_smtp.return_value.__enter__.return_value
        server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad credentials")

        with pytest.raises(RuntimeError, match="MDP_EMAIL"):
            envoyer_email("<p>test</p>")

    assert server.login.call_count == 1
    mock_sleep.assert_not_called()
