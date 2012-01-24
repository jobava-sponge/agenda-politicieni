import os.path
from datetime import datetime
from collections import defaultdict
from flask import json
from flaskext.sqlalchemy import SQLAlchemy
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openid_url = db.Column(db.Text())
    name = db.Column(db.Text())
    email = db.Column(db.Text())


class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text())

    def get_content(self):
        version = self.versions.order_by(ContentVersion.time.desc()).first()
        return {} if version is None else json.loads(version.content)

    def save_content_version(self, new_content, user):
        utcnow = datetime.utcnow()
        version = ContentVersion(person=self, user=user, time=utcnow)
        version.content = json.dumps(new_content)
        db.session.add(version)
        db.session.commit()
        log.info("Content update for person id=%d version_id=%d",
                 self.id, version.id)


class ContentVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'))
    person = db.relationship('Person',
        backref=db.backref('versions', lazy='dynamic'))
    content = db.Column(db.LargeBinary)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User')
    time = db.Column(db.DateTime)


def get_persons():
    results = {}

    for person in Person.query.all():
        results[person.id] = dict(person.get_content(), name=person.name)

    return results


def import_json(json_path):
    utcnow = datetime.utcnow()
    count = defaultdict(int)

    with open(json_path, 'rb') as f:
        people_data = json.load(f)

    for person_data in people_data:
        found_persons = Person.query.filter_by(name=person_data['name']).all()
        if found_persons:
            assert len(found_persons) == 1
            person = found_persons[0]

        else:
            person = Person(name=person_data['name'])
            db.session.add(person)
            log.info('New person %r, id=%d', person_data['name'], person.id)
            count['new-person'] += 1

        emails = person_data['emails']
        if emails:
            content = {'email': emails}
            if content != person.get_content():
                version = ContentVersion(person=person, time=utcnow)
                version.content = json.dumps(content)
                db.session.add(version)
                log.info('Content update for person id=%d', person.id)
                count['new-version'] += 1

    db.session.commit()
    if count:
        log.info("JSON import from %r completed; %r", json_path, dict(count))


def get_user(openid_url):
    return User.query.filter_by(openid_url=openid_url).first()


def get_update_user(openid_url, name, email):
    user = get_user(openid_url)
    if user is None:
        user = User(openid_url=openid_url)
        log.info("New user, openid_url=%r", openid_url)

    if (name, email) != (user.name, user.email):
        user.name = name
        user.email = email
        db.session.add(user)
        db.session.commit()
        log.info("User data modified for openid_url=%r", openid_url)

    return user
