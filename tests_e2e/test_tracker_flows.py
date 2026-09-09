import csv
import io

from playwright.sync_api import Page, expect


def add_application(page: Page, company: str, role: str, status: str = "applied", **fields):
    page.get_by_role("button", name="Add application").click()

    # Stay inside the dialog — "Status" also matches the filter dropdown.
    dialog = page.locator("#app-dialog")
    dialog.get_by_label("Company *").fill(company)
    dialog.get_by_label("Role *").fill(role)
    dialog.get_by_label("Status").select_option(status)
    for label, value in fields.items():
        dialog.get_by_label(label).fill(value)

    dialog.get_by_role("button", name="Save").click()
    expect(dialog).not_to_be_visible()


def rows(page: Page):
    return page.locator("#rows tr")


def test_a_new_account_starts_empty(signed_in_page: Page):
    expect(signed_in_page.locator("#empty-state")).to_have_text(
        "No applications yet. Add the first one to start tracking."
    )
    expect(signed_in_page.locator("#stat-total")).to_have_text("0")


def test_adding_an_application_shows_it_in_the_table(signed_in_page: Page):
    add_application(signed_in_page, "Northwind Labs", "Junior Backend Developer", Location="Remote")

    expect(rows(signed_in_page)).to_have_count(1)
    expect(rows(signed_in_page).first).to_contain_text("Northwind Labs")
    expect(rows(signed_in_page).first).to_contain_text("Junior Backend Developer")
    expect(rows(signed_in_page).first).to_contain_text("Remote")
    expect(signed_in_page.locator("#stat-total")).to_have_text("1")


def test_signing_up_with_a_short_password_is_rejected(page: Page, base_url):
    page.goto("/")
    page.get_by_role("tab", name="Create account").click()
    page.get_by_label("Email").fill("too-short@example.com")
    page.get_by_label("Password").fill("short")
    page.get_by_role("button", name="Create account").click()

    expect(page.locator("#auth-error")).to_be_visible()
    expect(page.locator("#app-view")).not_to_be_visible()


def test_status_filter_and_search_narrow_the_list(signed_in_page: Page):
    add_application(signed_in_page, "Litware", "Associate Engineer", "interview", Location="Berlin")
    add_application(signed_in_page, "Contoso", "Graduate Engineer", "applied", Location="Manchester")

    signed_in_page.get_by_label("Filter by status").select_option("interview")
    expect(rows(signed_in_page)).to_have_count(1)
    expect(rows(signed_in_page).first).to_contain_text("Litware")

    signed_in_page.get_by_label("Search").fill("manchester")
    expect(signed_in_page.locator("#empty-state")).to_have_text(
        "No applications match these filters."
    )

    signed_in_page.get_by_role("button", name="Clear").click()
    expect(rows(signed_in_page)).to_have_count(2)


def test_editing_a_status_updates_the_summary(signed_in_page: Page):
    add_application(signed_in_page, "Fabrikam", "Junior Python Developer")
    expect(signed_in_page.locator("#stat-interview")).to_have_text("0")

    signed_in_page.get_by_role("button", name="Edit").click()
    dialog = signed_in_page.locator("#app-dialog")
    expect(signed_in_page.locator("#dialog-title")).to_have_text("Edit application")
    dialog.get_by_label("Status").select_option("interview")
    dialog.get_by_role("button", name="Save").click()

    expect(rows(signed_in_page).first).to_contain_text("interview")
    expect(signed_in_page.locator("#stat-interview")).to_have_text("1")
    expect(signed_in_page.locator("#stat-response")).to_have_text("100%")


def test_deleting_an_application_removes_it(signed_in_page: Page):
    add_application(signed_in_page, "Proseware", "Junior Developer")
    expect(rows(signed_in_page)).to_have_count(1)

    signed_in_page.on("dialog", lambda dialog: dialog.accept())
    signed_in_page.get_by_role("button", name="Delete").click()

    expect(rows(signed_in_page)).to_have_count(0)
    expect(signed_in_page.locator("#stat-total")).to_have_text("0")


def test_cancelling_a_delete_keeps_the_application(signed_in_page: Page):
    add_application(signed_in_page, "Tailwind Traders", "Data Analyst Intern")

    signed_in_page.on("dialog", lambda dialog: dialog.dismiss())
    signed_in_page.get_by_role("button", name="Delete").click()

    expect(rows(signed_in_page)).to_have_count(1)


def test_export_csv_downloads_the_filtered_rows(signed_in_page: Page):
    add_application(signed_in_page, "Litware", "Associate Engineer", "interview")
    add_application(signed_in_page, "Contoso", "Graduate Engineer", "applied")

    signed_in_page.get_by_label("Filter by status").select_option("interview")
    expect(rows(signed_in_page)).to_have_count(1)

    with signed_in_page.expect_download() as download_info:
        signed_in_page.get_by_role("button", name="Export CSV").click()
    download = download_info.value

    assert download.suggested_filename.endswith(".csv")
    content = download.path().read_text(encoding="utf-8")
    exported = list(csv.DictReader(io.StringIO(content)))

    assert [row["company"] for row in exported] == ["Litware"]
    assert exported[0]["status"] == "interview"


def test_sign_out_hides_the_dashboard_and_survives_a_reload(signed_in_page: Page):
    signed_in_page.get_by_role("button", name="Sign out").click()

    expect(signed_in_page.locator("#auth-view")).to_be_visible()
    expect(signed_in_page.locator("#app-view")).not_to_be_visible()

    signed_in_page.reload()
    expect(signed_in_page.locator("#auth-view")).to_be_visible()
    expect(signed_in_page.locator("#app-view")).not_to_be_visible()
