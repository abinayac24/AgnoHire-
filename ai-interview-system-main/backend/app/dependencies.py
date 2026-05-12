from app.database.mongo import db_manager


def get_repository():
    return db_manager
