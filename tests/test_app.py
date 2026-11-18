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
    for page in ("app_pages/spending.py", "app_pages/roth.py", "app_pages/shadow.py",
                 "app_pages/risk.py", "app_pages/timing.py", "app_pages/proof.py"):
        at.switch_page(page).run()
        assert not at.exception, (page, at.exception)
        assert not at.error, (page, [e.value for e in at.error])


def test_lab_pages_alternate_paths():
    at = _loaded()
    at.switch_page("app_pages/risk.py").run()
    at.radio(key="risk_window").set_value("history").run()
    assert not at.exception and not at.error
    assert len(at.metric) >= 5
    at.switch_page("app_pages/roth.py").run()
    at.radio(key="mc_method").set_value("bootstrap").run()
    assert not at.exception and not at.error
    labels = [m.label for m in at.metric]
    assert any(lbl.startswith("Median at") for lbl in labels)


def test_proof_page_all_checks_pass_on_sample():
    at = _loaded()
    at.switch_page("app_pages/proof.py").run()
    assert not at.exception and not at.error
    assert any("10 of 10 checks pass" in m.value for m in at.markdown)


def test_roth_monte_carlo_mean_near_closed_form():
    # defaults: 21 -> 65, $200/mo, 7% APR, 15% vol, 5,000 runs; closed form $705,070.79
    at = _loaded()
    at.switch_page("app_pages/roth.py").run()
    check = [c.value for c in at.caption if "average of" in c.value][0]
    assert "705,071" in check


def test_empty_state_points_to_upload():
    at = AppTest.from_file("../streamlit_app.py").run()
    at.switch_page("app_pages/spending.py").run()
    assert not at.exception
    assert at.info
