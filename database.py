from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class AppConfig(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=None):
        config = AppConfig.query.get(key)
        return config.value if config else default

    @staticmethod
    def set(key, value):
        config = AppConfig.query.get(key)
        if not config:
            config = AppConfig(key=key)
            db.session.add(config)
        config.value = value
        db.session.commit()

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    channel_name = db.Column(db.String(100))
    action_type = db.Column(db.String(50)) # e.g., "Drive", "Asana", "Sheet", "Bot Invite"
    status = db.Column(db.String(20)) # "SUCCESS", "FAILURE", "INFO"
    details = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'channel_name': self.channel_name,
            'action_type': self.action_type,
            'status': self.status,
            'details': self.details
        }
