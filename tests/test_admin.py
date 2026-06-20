import app as appmod
from admin import fixtures as fx


def _client():
    appmod.app.config.update(TESTING=True)
    return appmod.app.test_client()


def test_fixtures_shapes():
    assert fx.TENANTS and fx.TENANTS[0]["name"] == "Northwind Retail"
    f = fx.FEASIBILITY
    assert f["score"] == 82 and f["verdict"] == "Go"
    assert len(f["factors"]) >= 6 and {"name","score","weight","evidence","confidence","status"} <= f["factors"][0].keys()
    assert len(fx.MODULES) == 11
    assert len(fx.SKILLS) == 6 and len(fx.SKILL_ROADMAP) == 5
    comps = fx.load_competitors()
    assert len(comps) >= 6 and "competitor" in comps[0]


def test_context_has_shell_keys():
    ctx = fx.context("feasibility")
    assert ctx["active"] == "feasibility" and ctx["tenant"]["name"] and ctx["modules"]


def test_admin_index_200():
    r = _client().get("/admin/")
    assert r.status_code == 200
    assert "超级管理员".encode() in r.data


def test_shell_renders_all_modules():
    body = _client().get("/admin/").data.decode()
    for label in ["平台管理", "SEO 策略", "权限与安全", "Northwind Retail", "Kai Lin"]:
        assert label in body


def test_feasibility_content():
    body = _client().get("/admin/").data.decode()
    assert "可解释评分模型" in body and "搜索需求" in body and "82" in body


def test_competitors_real_data():
    body = _client().get("/admin/competitors").data.decode()
    assert "Byword" in body and ("软肋" in body or "weakness" in body.lower())


def test_keyword_map():
    body = _client().get("/admin/keywords").data.decode()
    assert "comparison" in body or "对比类" in body


def test_transparency_honest():
    body = _client().get("/admin/transparency").data.decode()
    assert "automotive" in body and "未进标题" in body


def test_agent_skill_screen():
    body = _client().get("/admin/agent").data.decode()
    assert "seo-content" in body and "quality-rubric" in body and "Phase 2" in body


def test_stub_modules_reachable():
    c = _client()
    for key in ["platform", "projects", "cms", "content", "publish", "monitor", "data", "rbac", "settings"]:
        r = c.get("/admin/m/" + key)
        assert r.status_code == 200 and "demo 占位".encode() in r.data


def test_all_admin_routes_200():
    c = _client()
    for path in ["/admin/", "/admin/feasibility", "/admin/competitors", "/admin/keywords", "/admin/transparency", "/admin/agent"]:
        assert c.get(path).status_code == 200


def test_switch_tenant():
    body = _client().get("/admin/?tenant=herz").data.decode()
    assert "萌翻天食品" in body
