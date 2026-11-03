import json
import os
from pathlib import Path

import pytest

TEST_DB = "test.db"
BASE_DIR = Path(__file__).resolve().parent.parent

# Flask-SQLAlchemy 3.x creates its engine as soon as `db = SQLAlchemy(app)` runs,
# so changing SQLALCHEMY_DATABASE_URI inside the fixture is too late: the tests
# would silently use (and drop_all() would wipe) the real flaskr.db / Postgres DB.
# Point the app at the test database BEFORE importing it instead.
os.environ["DATABASE_URL"] = f"sqlite:///{BASE_DIR.joinpath(TEST_DB)}"

from project.app import app, db  # noqa: E402
from project.models import Post  # noqa: E402


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.app_context():
        db.create_all()  # setup
        yield app.test_client()  # tests run here
        db.drop_all()  # teardown


def login(client, username, password):
    """Login helper function"""
    return client.post(
        "/login",
        data=dict(username=username, password=password),
        follow_redirects=True,
    )


def logout(client):
    """Logout helper function"""
    return client.get("/logout", follow_redirects=True)


def add_post(client, title, text):
    """Add-post helper function (caller must already be logged in)"""
    return client.post(
        "/add",
        data=dict(title=title, text=text),
        follow_redirects=True,
    )


def test_index(client):
    response = client.get("/", content_type="html/text")
    assert response.status_code == 200


def test_database(client):
    """initial test. ensure that the database exists"""
    tester = Path("test.db").is_file()
    assert tester


def test_empty_db(client):
    """Ensure database is blank"""
    rv = client.get("/")
    assert b"No entries yet. Add some!" in rv.data


def test_login_logout(client):
    """Test login and logout using helper functions"""
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"])
    assert b"You were logged in" in rv.data
    rv = logout(client)
    assert b"You were logged out" in rv.data
    rv = login(client, app.config["USERNAME"] + "x", app.config["PASSWORD"])
    assert b"Invalid username" in rv.data
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"] + "x")
    assert b"Invalid password" in rv.data


def test_messages(client):
    """Ensure that user can post messages"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = add_post(client, "<Hello>", "<strong>HTML</strong> allowed here")
    assert b"No entries here so far" not in rv.data
    assert b"&lt;Hello&gt;" in rv.data
    assert b"<strong>HTML</strong> allowed here" in rv.data


def test_delete_message(client):
    """Ensure the messages are being deleted"""
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 0
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 1


# ---------------------------------------------------------------------------
# Tests I designed for the "Search Page" and "Login Required" sections
# ---------------------------------------------------------------------------


def test_search_page_loads_without_query(client):
    """The search page renders (with the search form) when no query is given"""
    rv = client.get("/search/")
    assert rv.status_code == 200
    assert b"Search:" in rv.data
    assert b'name="query"' in rv.data


def test_search_finds_matching_posts(client):
    """A query returns posts whose title or text matches, case-insensitively"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    add_post(client, "Flask tips", "Use blueprints for big apps")
    add_post(client, "Cooking", "How to make PASTA")
    add_post(client, "Gardening", "Water the tomatoes")

    # match on title
    rv = client.get("/search/?query=flask")
    assert b"Flask tips" in rv.data
    assert b"Cooking" not in rv.data
    assert b"Gardening" not in rv.data

    # match on text, different case than stored
    rv = client.get("/search/?query=pasta")
    assert b"Cooking" in rv.data
    assert b"Flask tips" not in rv.data


def test_search_no_results(client):
    """A query that matches nothing shows no posts"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    add_post(client, "Flask tips", "Use blueprints for big apps")
    rv = client.get("/search/?query=zzz-not-there")
    assert rv.status_code == 200
    assert b"Flask tips" not in rv.data


def test_delete_requires_login(client):
    """Logged-out users get a 401 and the post is NOT removed from the database"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    add_post(client, "Keep me", "should survive")
    logout(client)

    rv = client.get("/delete/1")
    assert rv.status_code == 401
    assert json.loads(rv.data) == {"status": 0, "message": "Please log in."}
    assert db.session.query(Post).count() == 1


def test_delete_when_logged_in_removes_post(client):
    """Logged-in users can delete, and the post is actually gone afterwards"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    add_post(client, "Delete me", "bye")
    assert db.session.query(Post).count() == 1

    rv = client.get("/delete/1")
    assert rv.status_code == 200
    assert json.loads(rv.data)["status"] == 1
    assert db.session.query(Post).count() == 0


def test_add_requires_login(client):
    """Posting a new entry while logged out is rejected with 401"""
    rv = add_post(client, "Sneaky", "should not be saved")
    assert rv.status_code == 401
    assert db.session.query(Post).count() == 0
