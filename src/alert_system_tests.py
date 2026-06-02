from pathlib import Path

from src.alert_system import Alert, evaluate_alerts, load_stream_batch, write_alert


def test_load_stream_batch_reads_latest_rows(tmp_path: Path) -> None:
    data_path = tmp_path / "stream.csv"
    data_path.write_text(
        "month_id,ind1_site,ind2_site,pair_sars,contacts,hcir\n"
        "202101,0,0,1,4,50\n"
        "202102,1,1,1,8,80\n"
        "202103,2,2,0,2,10\n",
        encoding="utf-8",
    )

    batch = load_stream_batch(data_path=data_path, batch_size=2)

    assert [row["month_id"] for row in batch] == ["202102", "202103"]


def test_evaluate_alerts_detects_repeated_pattern() -> None:
    records = [
        {"month_id": "202101", "ind1_site": "0", "ind2_site": "0", "pair_sars": "1", "contacts": "4", "hcir": "50"},
        {"month_id": "202101", "ind1_site": "0", "ind2_site": "0", "pair_sars": "1", "contacts": "5", "hcir": "60"},
        {"month_id": "202102", "ind1_site": "1", "ind2_site": "1", "pair_sars": "0", "contacts": "1", "hcir": "10"},
    ]

    alerts = evaluate_alerts(records, min_sup=2)

    assert alerts
    assert alerts[0].support >= 2
    assert alerts[0].min_sup == 2


def test_write_alert_appends_to_log(tmp_path: Path) -> None:
    log_path = tmp_path / "alerts.log"
    alert = Alert(
        message="High support pattern detected: location=0",
        support=3,
        min_sup=2,
        source="test",
        timestamp="2026-06-02T12:00:00",
    )

    write_alert(alert, log_path=log_path)

    assert "[ALERT] High support pattern detected" in log_path.read_text(encoding="utf-8")
