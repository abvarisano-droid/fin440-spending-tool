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
    for page in ("app_pages/spending.py", "app_pages/roth.py", "app_pages/shadow.py"):
        at.switch_page(page).run()
        assert not at.exception, (page, at.exception)
        assert not at.error, (page, [e.value for e in at.error])


def test_empty_state_points_to_upload():
    at = AppTest.from_file("../streamlit_app.py").run()
    at.switch_page("app_pages/spending.py").run()
    assert not at.exception
    assert at.info
