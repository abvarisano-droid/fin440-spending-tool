"""Headless smoke test of every page. The shadow page needs network for prices."""
from streamlit.testing.v1 import AppTest


def _loaded():
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60).run()
    at.button(key="use_sample").click().run()
    assert not at.exception
    return at


def test_pages_render_with_sample():
    at = _loaded()
    assert "transactions" in at.session_state
    for page in ("app_pages/spending.py", "app_pages/roth.py", "app_pages/shadow.py", "app_pages/proof.py"):
        at.switch_page(page).run()
        assert not at.exception, (page, at.exception)
        assert not at.error, (page, [e.value for e in at.error])


def test_lab_pages_alternate_paths():
    at = _loaded()
    at.switch_page("app_pages/roth.py").run()
    at.radio(key="mc_method").set_value("bootstrap").run()
    assert not at.exception and not at.error
    labels = [m.label for m in at.metric]
    assert any(lbl.startswith("Median at") for lbl in labels)


def test_proof_page_all_checks_pass_on_sample():
    at = _loaded()
    at.switch_page("app_pages/proof.py").run()
    assert not at.exception and not at.error
    assert any("8 of 8 checks pass" in m.value for m in at.markdown)


def test_roth_funds_from_spending_on_sample():
    # sample wants: $3,684.72 over 6 months = $614.12/month -> heavy tier, 25% -> $153.53 -> $150
    at = _loaded()
    at.switch_page("app_pages/roth.py").run()
    assert not at.exception and not at.error
    assert at.radio(key="roth_mode").value == "My spending"
    assert at.radio(key="roth_invest_mode").value == "Percent of wants"   # percent is the default
    assert at.slider(key="roth_pct").value == 25
    assert at.number_input(key="roth_start_sp").value == 3684.72
    assert any("$150/month" in c.value and "614.12/month" in c.value for c in at.caption)
    assert any("614.12/month" in m.value for m in at.markdown)
    at.radio(key="roth_mode").set_value("Enter my own").run()
    assert not at.exception and not at.error
    # coming back (mode switch or another page) refills the start instead of resetting it to $0
    at.radio(key="roth_mode").set_value("My spending").run()
    assert at.number_input(key="roth_start_sp").value == 3684.72
    at.switch_page("app_pages/spending.py").run()
    at.switch_page("app_pages/roth.py").run()
    assert at.number_input(key="roth_start_sp").value == 3684.72
    assert at.metric[0].value == "$608,262"


def test_roth_percent_slider_drives_monthly():
    # 50% of $614.12 = $307.06 -> $300/month; 7,500 - 3,600 leaves $3,900, so the $3,684.72 start fits
    at = _loaded()
    at.switch_page("app_pages/roth.py").run()
    at.slider(key="roth_pct").set_value(50).run()
    assert not at.exception and not at.error
    assert any("$300/month" in c.value for c in at.caption)
    assert at.number_input(key="roth_start_sp").value == 3684.72
    # 100% = $614.12 -> $625, the whole yearly limit, so no room is left for a starting balance
    at.slider(key="roth_pct").set_value(100).run()
    assert any("$625/month" in c.value for c in at.caption)
    assert at.number_input(key="roth_start_sp").value == 0


def test_roth_start_keeps_first_year_within_ira_limit():
    # every category on the sample: $6,963.81 spent, $1,160.64/month -> $300 suggested,
    # so the start is trimmed to 7,500 - 12 x 300 = $3,900
    at = _loaded()
    at.switch_page("app_pages/roth.py").run()
    at.multiselect(key="roth_cats").set_value(list(at.multiselect(key="roth_cats").options)).run()
    assert any("$300/month" in c.value for c in at.caption)
    assert at.number_input(key="roth_start_sp").value == 3900
    assert not at.warning
    at.number_input(key="roth_start_sp").set_value(5000).run()
    assert at.warning


def test_exact_dollars_drive_roth_and_shadow():
    # "Exact $ per month" picked on the Roth page carries to the Shadow page with the same amount
    at = _loaded()
    at.switch_page("app_pages/roth.py").run()
    at.radio(key="roth_invest_mode").set_value("Exact $ per month").run()
    assert not at.exception and not at.error
    assert at.number_input(key="roth_invest_dollars").value == 150          # starts at the suggestion
    assert at.metric[0].value == "$608,262"                                  # same plan as 25%
    at.number_input(key="roth_invest_dollars").set_value(200).run()
    # $3,684.72 start (7,500 - 2,400 = 5,100 room, so no trim) + $200/month, 21 -> 65 at 7% APR
    assert at.number_input(key="roth_start_sp").value == 3684.72
    assert at.metric[0].value != "$608,262"
    at.switch_page("app_pages/shadow.py").run()
    assert not at.exception and not at.error
    assert at.radio(key="shadow_invest_mode").value == "Exact $ per month"
    assert at.number_input(key="shadow_invest_dollars").value == 200
    # sample spans May to October: six buys of $200
    assert at.metric[0].label == "You put in" and at.metric[0].value == "$1,200.00"


def test_shadow_percent_of_each_want():
    at = _loaded()
    at.switch_page("app_pages/shadow.py").run()
    assert at.radio(key="shadow_invest_mode").value == "Percent of wants"
    assert at.metric[0].label == "You spent" and at.metric[0].value == "$3,684.72"   # 100% default
    at.slider(key="shadow_pct").set_value(50).run()
    assert not at.exception and not at.error
    assert at.metric[0].label == "You put in" and at.metric[0].value == "$1,842.36"


def test_monte_carlo_target_follows_the_balance():
    # the target used to keep $608,000 from "My spending" after switching to "Enter my own"
    at = _loaded()
    at.switch_page("app_pages/roth.py").run()
    assert at.number_input(key="mc_target").value == 608_000
    at.radio(key="roth_mode").set_value("Enter my own").run()
    assert at.number_input(key="mc_target").value == 705_000


def test_roth_monte_carlo_mean_near_closed_form():
    # defaults: 21 -> 65, $200/mo, 7% APR, 15% vol, 5,000 runs; closed form $705,070.79
    at = _loaded()
    at.switch_page("app_pages/roth.py").run()
    at.radio(key="roth_mode").set_value("Enter my own").run()
    check = [c.value for c in at.caption if "average of" in c.value][0]
    assert "705,071" in check


def test_empty_state_points_to_upload():
    at = AppTest.from_file("../streamlit_app.py").run()
    at.switch_page("app_pages/spending.py").run()
    assert not at.exception
    assert at.info


def test_split_shopping_into_a_need_leaves_the_shadow():
    # sample Shopping = Amazon $1,425.82 + Target $626.29; Target -> "Home" (a need)
    at = _loaded()
    at.switch_page("app_pages/spending.py").run()
    assert at.selectbox(key="split_source").value == "Shopping"
    at.multiselect(key="split_merchants").set_value(["TARGET 00012"])
    at.text_input(key="split_name").set_value("Home")
    at.toggle(key="split_want").set_value(False)
    at.button(key="split_btn").click().run()
    assert not at.exception and not at.error
    assert any("into Home" in s.value for s in at.success)
    assert at.metric[2].value == "$3,058.43"                       # wants: 3,684.72 - 626.29
    at.switch_page("app_pages/shadow.py").run()
    assert "Home" not in at.multiselect(key="shadow_cats").options
    assert at.metric[0].value == "$3,058.43"


def test_split_into_a_want_and_rename():
    at = _loaded()
    at.switch_page("app_pages/spending.py").run()
    at.multiselect(key="split_merchants").set_value(["TARGET 00012"])
    at.text_input(key="split_name").set_value("Home")
    at.button(key="split_btn").click().run()                       # flag defaults to Shopping's: a want
    at.selectbox(key="rename_old").set_value("Shopping")
    at.text_input(key="rename_new").set_value("Online")
    at.button(key="rename_btn").click().run()
    assert not at.exception and not at.error
    at.switch_page("app_pages/shadow.py").run()
    opts = at.multiselect(key="shadow_cats").options
    assert "Home" in opts and "Online" in opts and "Shopping" not in opts
    assert at.metric[0].value == "$3,684.72"                       # same wants, new names


def test_split_rejects_an_existing_name():
    at = _loaded()
    at.switch_page("app_pages/spending.py").run()
    at.multiselect(key="split_merchants").set_value(["TARGET 00012"])
    at.text_input(key="split_name").set_value("dining")
    at.button(key="split_btn").click().run()
    assert any("already exists" in e.value for e in at.error)


def test_ignored_purchase_leaves_every_total():
    at = _loaded()
    tx = at.session_state["transactions"].copy()
    tx["ignored"] = False
    first_amazon = tx.index[tx["description"] == "AMAZON.COM*MK12"][0]
    tx.loc[first_amazon, "ignored"] = True
    amt = float(tx.loc[first_amazon, "amount"])
    at.session_state["transactions"] = tx
    at.switch_page("app_pages/spending.py").run()
    assert not at.exception and not at.error
    assert at.metric[0].value == f"${6963.81 - amt:,.2f}"
    assert any("1 ignored purchase" in c.value for c in at.caption)
    at.switch_page("app_pages/shadow.py").run()
    assert at.metric[0].value == f"${3684.72 - amt:,.2f}"


def test_no_course_line_under_titles_and_links_on_proof():
    at = _loaded()
    for page in ("app_pages/spending.py", "app_pages/shadow.py", "app_pages/roth.py"):
        at.switch_page(page).run()
        assert not any("FIN 440 link" in c.value for c in at.caption), page
    at.switch_page("app_pages/proof.py").run()
    assert any("Ch 7" in m.value and "Shadow portfolio" in m.value for m in at.markdown)


def test_sample_csv_can_be_downloaded():
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60).run()
    assert not at.exception
    assert at.get("download_button")   # next to "Use sample data", before anything is loaded
