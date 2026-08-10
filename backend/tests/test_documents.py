"""/upload 与 /documents 端点的 API 测试。"""


def _upload(app_env, name, content, mime="text/plain"):
    return app_env.client.post("/upload", files={"file": (name, content, mime)})


def test_upload_txt_success(app_env):
    resp = _upload(app_env, "a.txt", b"hello world")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "upload"
    assert data["chunks"] >= 1
    assert (app_env.data_dir / "a.txt").exists()


def test_upload_empty_file(app_env):
    resp = _upload(app_env, "empty.txt", b"")
    assert resp.json()["status"] == "empty"


def test_upload_bad_extension(app_env):
    resp = _upload(app_env, "evil.exe", b"x", "application/octet-stream")
    data = resp.json()
    assert data["status"] == "error"
    assert not (app_env.data_dir / "evil.exe").exists()


def test_upload_corrupt_pdf_not_saved(app_env):
    resp = _upload(app_env, "bad.pdf", b"not a pdf", "application/pdf")
    assert resp.json()["status"] == "error"
    assert not (app_env.data_dir / "bad.pdf").exists()


def test_upload_idempotent(app_env):
    _upload(app_env, "a.txt", b"hello world")
    _upload(app_env, "a.txt", b"hello world")
    # 同名重传不叠加向量：fake 向量库里只有一份
    assert len(app_env.vector_store.sources["a.txt"]) == 1


def test_list_documents(app_env):
    _upload(app_env, "a.txt", b"hello")
    resp = app_env.client.get("/documents")
    assert resp.json()["documents"] == ["a.txt"]


def test_get_document_content(app_env):
    _upload(app_env, "a.txt", b"hello content")
    resp = app_env.client.get("/documents/a.txt")
    assert resp.status_code == 200
    assert resp.json()["content"] == "hello content"


def test_get_document_not_allowed_returns_404(app_env):
    # conversations.db 等运行时文件不应被文档接口读到
    resp = app_env.client.get("/documents/conversations.db")
    assert resp.status_code == 404


def test_get_document_missing(app_env):
    resp = app_env.client.get("/documents/nope.txt")
    assert resp.status_code == 200
    assert resp.json().get("error")


def test_delete_document_removes_file_and_vector(app_env):
    _upload(app_env, "a.txt", b"hello")
    resp = app_env.client.delete("/documents/a.txt")
    assert resp.json()["status"] == "delete"
    assert not (app_env.data_dir / "a.txt").exists()
    assert "a.txt" not in app_env.vector_store.sources


def test_delete_document_not_allowed_returns_404(app_env):
    resp = app_env.client.delete("/documents/conversations.db")
    assert resp.status_code == 404
