# create_db.py


from project.app import app, db
from project.models import Post  # noqa: F401 (registers the table with SQLAlchemy)

with app.app_context():
    # create the database and the db table
    db.create_all()

    # commit the changes
    db.session.commit()
