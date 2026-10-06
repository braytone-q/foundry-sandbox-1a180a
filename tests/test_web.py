def test_browser_assets_are_served_without_azure(app_bundle):
    client, _, gateway, _ = app_bundle
    page = client.get("/")
    assert page.status_code == 200
    assert "Submit Activity" in page.text and "Review Queue" in page.text
    assert 'src="/static/app.js"' in page.text
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert gateway.descriptions == []
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]


def test_source_script_markup_round_trips_as_data(client):
    source = '<script>alert("untrusted")</script>'
    response = client.post("/api/submissions", json={"description": source})
    assert response.json()["description"] == source
    assert source not in client.get("/").text
