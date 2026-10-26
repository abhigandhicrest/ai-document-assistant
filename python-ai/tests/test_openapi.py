"""API documentation tests.

The docs pages are how a local tester calls the API without writing a client.
"""


def test_openapi_document_lists_the_working_routes(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert document["info"]["title"] == "AI Document Assistant"
    assert "/api/health" in document["paths"]
    assert "get" in document["paths"]["/api/health"]
    assert "/api/documents/upload" in document["paths"]
    assert "post" in document["paths"]["/api/documents/upload"]
    assert "/api/documents/{document_id}/process" in document["paths"]
    assert "/api/chat/ask" in document["paths"]
    assert "/ask" in document["paths"]

    upload = document["paths"]["/api/documents/upload"]["post"]
    assert "400" in upload["responses"]
    assert "413" in upload["responses"]
    assert "200" in upload["responses"]


def test_swagger_and_redoc_pages_load(client) -> None:
    swagger = client.get("/docs")
    redoc = client.get("/redoc")

    assert swagger.status_code == 200
    assert "swagger" in swagger.text.lower()
    assert redoc.status_code == 200
    assert "redoc" in redoc.text.lower()
