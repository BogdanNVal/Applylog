import csv
import io
from datetime import date, timedelta

TODAY = date.today()


def payload(**overrides):
    base = {
        "company": "Northwind Labs",
        "role": "Junior Backend Developer",
        "link": "https://example.com/jobs/1",
        "location": "Remote",
        "notes": "Referred by a friend.",
        "status": "applied",
        "applied_on": TODAY.isoformat(),
    }
    base.update(overrides)
    return base


def create(client, **overrides):
    response = client.post("/api/applications", json=payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_applications_require_authentication(client):
    assert client.get("/api/applications").status_code == 401
    assert client.post("/api/applications", json=payload()).status_code == 401
    assert client.get("/api/applications/stats").status_code == 401


def test_create_then_list(signed_in):
    created = create(signed_in)
    assert created["company"] == "Northwind Labs"
    assert created["status"] == "applied"

    listed = signed_in.get("/api/applications").json()
    assert [item["id"] for item in listed] == [created["id"]]


def test_list_is_sorted_by_applied_date_descending(signed_in):
    create(signed_in, company="Older", applied_on=(TODAY - timedelta(days=10)).isoformat())
    create(signed_in, company="Newer", applied_on=TODAY.isoformat())

    companies = [item["company"] for item in signed_in.get("/api/applications").json()]
    assert companies == ["Newer", "Older"]


def test_create_trims_whitespace(signed_in):
    created = create(signed_in, company="  Spaced Out  ")
    assert created["company"] == "Spaced Out"


def test_create_rejects_invalid_input(signed_in):
    assert signed_in.post("/api/applications", json=payload(company="")).status_code == 422
    assert signed_in.post("/api/applications", json=payload(status="ghosted")).status_code == 422

    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    assert signed_in.post("/api/applications", json=payload(applied_on=tomorrow)).status_code == 422


def test_filter_by_status(signed_in):
    create(signed_in, company="Waiting", status="applied")
    create(signed_in, company="Talking", status="interview")

    filtered = signed_in.get("/api/applications", params={"status": "interview"}).json()
    assert [item["company"] for item in filtered] == ["Talking"]


def test_search_matches_company_role_location_and_notes(signed_in):
    create(signed_in, company="Litware", location="Berlin", notes="Team lead call")
    create(signed_in, company="Fabrikam", location="Dublin", notes="Offer pending")

    for term, expected in [
        ("litware", "Litware"),
        ("berlin", "Litware"),
        ("team lead", "Litware"),
        ("dublin", "Fabrikam"),
    ]:
        found = signed_in.get("/api/applications", params={"q": term}).json()
        assert [item["company"] for item in found] == [expected], term


def test_search_treats_wildcards_as_literal_text(signed_in):
    create(signed_in, company="Percent % Co")
    create(signed_in, company="Regular Co")

    found = signed_in.get("/api/applications", params={"q": "%"}).json()
    assert [item["company"] for item in found] == ["Percent % Co"]


def test_filter_by_date_range(signed_in):
    create(signed_in, company="Old", applied_on=(TODAY - timedelta(days=30)).isoformat())
    create(signed_in, company="Recent", applied_on=(TODAY - timedelta(days=2)).isoformat())

    found = signed_in.get(
        "/api/applications",
        params={"from": (TODAY - timedelta(days=7)).isoformat(), "to": TODAY.isoformat()},
    ).json()
    assert [item["company"] for item in found] == ["Recent"]


def test_update_changes_the_stored_values(signed_in):
    created = create(signed_in)

    response = signed_in.put(
        f"/api/applications/{created['id']}",
        json=payload(status="interview", notes="Call booked"),
    )
    assert response.status_code == 200

    updated = response.json()
    assert updated["status"] == "interview"
    assert updated["notes"] == "Call booked"
    assert signed_in.get(f"/api/applications/{created['id']}").json()["status"] == "interview"


def test_delete_removes_the_application(signed_in):
    created = create(signed_in)

    assert signed_in.delete(f"/api/applications/{created['id']}").status_code == 204
    assert signed_in.get(f"/api/applications/{created['id']}").status_code == 404
    assert signed_in.get("/api/applications").json() == []


def test_missing_application_returns_404(signed_in):
    assert signed_in.get("/api/applications/999").status_code == 404
    assert signed_in.put("/api/applications/999", json=payload()).status_code == 404
    assert signed_in.delete("/api/applications/999").status_code == 404


def test_users_cannot_reach_each_others_applications(signed_in, other_user):
    created = create(signed_in)

    assert other_user.get("/api/applications").json() == []
    assert other_user.get(f"/api/applications/{created['id']}").status_code == 404
    assert other_user.put(f"/api/applications/{created['id']}", json=payload()).status_code == 404
    assert other_user.delete(f"/api/applications/{created['id']}").status_code == 404

    assert signed_in.get(f"/api/applications/{created['id']}").status_code == 200


def test_stats_count_statuses_and_rates(signed_in):
    create(signed_in, status="applied")
    create(signed_in, status="applied")
    create(signed_in, status="interview")
    create(signed_in, status="offer")

    stats = signed_in.get("/api/applications/stats").json()
    assert stats["total"] == 4
    assert stats["applied"] == 2
    assert stats["interview"] == 1
    assert stats["offer"] == 1
    assert stats["rejected"] == 0
    assert stats["response_rate"] == 50.0
    assert stats["offer_rate"] == 25.0
    assert stats["last_7_days"] == 4


def test_stats_are_zero_without_applications(signed_in):
    stats = signed_in.get("/api/applications/stats").json()
    assert stats["total"] == 0
    assert stats["response_rate"] == 0.0


def test_stats_last_7_days_ignores_older_entries(signed_in):
    create(signed_in, applied_on=(TODAY - timedelta(days=2)).isoformat())
    create(signed_in, applied_on=(TODAY - timedelta(days=20)).isoformat())

    assert signed_in.get("/api/applications/stats").json()["last_7_days"] == 1


def test_csv_export_returns_the_filtered_rows(signed_in):
    create(signed_in, company="Waiting", status="applied")
    create(signed_in, company="Talking", status="interview")

    response = signed_in.get("/api/applications/export.csv", params={"status": "interview"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [row["company"] for row in rows] == ["Talking"]
    assert rows[0]["status"] == "interview"
