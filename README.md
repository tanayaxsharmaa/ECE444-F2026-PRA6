# ECE444 PRA6 – Flaskr (TDD + Deployment)

A small Flask blog app built test-first, following
[shuruizUofT/flaskr-tdd](https://github.com/shuruizUofT/flaskr-tdd), deployed on Render.

**Live app:** _<paste your Render URL here>_

Login: `admin` / `admin`

## Run locally (Windows PowerShell)

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
python create_db.py            # creates project/flaskr.db
python -m pytest -v            # 12 tests
$env:FLASK_APP="project/app.py"; python -m flask run -p 5001
```

Open http://localhost:5001.

## Project layout

```
create_db.py            creates the tables (db.create_all)
requirements.txt
project/
  app.py                config, routes, login_required decorator
  models.py             Post table (id, title, text)
  templates/            index.html, login.html, search.html (Jinja + Bootstrap)
  static/main.js        click a post -> fetch /delete/<id> -> reload
tests/app_test.py       pytest suite
```

## Routes

| Route | Method | What it does |
|---|---|---|
| `/` | GET | Lists all posts; shows the add form when logged in |
| `/login` | GET/POST | GET shows the form; POST checks username/password, sets `session["logged_in"]` |
| `/logout` | GET | Removes `logged_in` from the session |
| `/add` | POST | Adds a post (401 if not logged in) |
| `/delete/<id>` | GET | Deletes a post, returns JSON `{status, message}`; protected by `@login_required` |
| `/search/?query=` | GET | Shows posts whose title or text contains the query (case-insensitive) |

## The test suite

`client` is a **pytest fixture**. Before each test it creates empty tables in
`test.db` (`db.create_all()`), hands the test a Flask test client, and afterwards
drops the tables (`db.drop_all()`). So every test starts from a clean, known state
and tests can't affect each other.

`login()`, `logout()` and `add_post()` are helpers that send the same HTTP requests a browser would.

### Tests from the tutorial

| Test | Checks |
|---|---|
| `test_index` | `/` returns 200 |
| `test_database` | the test DB file exists after setup |
| `test_empty_db` | a fresh DB shows "No entries yet. Add some!" |
| `test_login_logout` | correct login and logout flash the right messages; wrong username and wrong password give the matching errors |
| `test_messages` | logged-in user can post; the **title is HTML-escaped** (`<Hello>` becomes `&lt;Hello&gt;`, so Jinja autoescape works) but the **text is rendered as HTML** because of `|safe` |
| `test_delete_message` | delete while logged out returns status 0; after login it returns status 1 |

### Tests I designed (Search Page + Login Required)

| Test | Checks | Why |
|---|---|---|
| `test_search_page_loads_without_query` | `/search/` with no query returns 200 and shows the search form | covers the `if query:` false branch |
| `test_search_finds_matching_posts` | matches on **title** and on **text**, case-insensitive; non-matching posts are hidden | the main search behaviour, plus both match fields |
| `test_search_no_results` | a query that matches nothing shows no posts | edge case |
| `test_delete_requires_login` | logged-out delete returns **401** with the "Please log in." JSON, and the post is **still in the DB** | the tutorial's test only checks the JSON; this also proves nothing was deleted |
| `test_delete_when_logged_in_removes_post` | logged-in delete returns 200 and the row count drops 1 → 0 | checks the database, not just the response |
| `test_add_requires_login` | logged-out POST to `/add` returns 401 and nothing is saved | the other protected action |

### A bug I hit and fixed

The tutorial's fixture sets `app.config["SQLALCHEMY_DATABASE_URI"]` to `test.db`
**after** importing the app. In Flask-SQLAlchemy 3.x the engine is created when
`db = SQLAlchemy(app)` runs, so that change is ignored. The tests were really
using `project/flaskr.db` (or the Postgres DB when `DATABASE_URL` was set), and
`drop_all()` would wipe real data. `test_database` failed, which exposed the bug.
The fix: set the `DATABASE_URL` environment variable to `test.db` **before**
importing the app (the app already reads `DATABASE_URL`).

## TDD (Red → Green → Refactor)

1. **Red:** write a test for behaviour that doesn't exist yet and watch it fail
   (e.g. `test_empty_db` failed while `/` still returned "Hello, World!").
2. **Green:** write just enough code to make it pass (the `index` view + template).
3. **Refactor:** clean up and re-run the tests (e.g. moving from raw `sqlite3`
   to SQLAlchemy while all tests stayed green; Black/Flake8).

## Deployment (Render)

1. Push this repo to GitHub (public).
2. Render dashboard → **New → Web Service** → connect the repo, branch `main`.
3. Settings:
   - **Build command:** `pip install -r requirements.txt && python create_db.py`
   - **Start command:** `gunicorn project.app:app`
   - **Instance type:** Free
4. **Environment** → add `PYTHON_VERSION` = `3.12.10` (your local version).
5. Wait for "Live" in Logs, then open the `.onrender.com` URL.

### Postgres on Render

1. **New → Postgres**, give it a name, choose Free, create it.
2. Copy the **Internal** and **External** Database URLs.
3. Create the tables in the remote DB from your machine:
   ```powershell
   $env:DATABASE_URL="<External Database URL>"
   python create_db.py
   Remove-Item Env:DATABASE_URL     # so local runs go back to SQLite
   ```
4. Web service → **Environment** → add `DATABASE_URL` = **Internal** Database URL. Saving it redeploys the service.

`app.py` uses `DATABASE_URL` when it is set, rewriting `postgres://` to
`postgresql://` because SQLAlchemy only accepts the latter, and falls back to
SQLite when it isn't set. `psycopg2-binary` is the Postgres driver.

**Why `gunicorn`?** `flask run` starts a single-threaded development server.
Gunicorn is a production WSGI server that runs several worker processes.
`project.app:app` means "the `app` object in the `project/app.py` module".

## Linting

```powershell
python -m flake8 --exclude env --ignore E402,E501 .
python -m black --exclude=env .
```

E402 is ignored because `from project import models` has to come after
`db` is created; otherwise there would be a circular import.
