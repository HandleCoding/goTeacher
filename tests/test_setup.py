from goteacher.setup import resolve_latest_katago_asset_url


def test_resolve_latest_katago_asset_url_prefers_darwin_arm(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"assets":[{"name":"katago-linux-x64.zip","browser_download_url":"linux"},{"name":"katago-macos-arm64.zip","browser_download_url":"mac-arm"}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda url: FakeResponse())
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("platform.machine", lambda: "arm64")
    assert resolve_latest_katago_asset_url() == "mac-arm"
