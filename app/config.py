import os


def _database_uri():
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    # Variables que AWS Elastic Beanstalk expone cuando la base de datos RDS se configura en el ambiente
    # (o que se definen manualmente en Configuracion > Propiedades del entorno si RDS es independiente).
    if os.environ.get("RDS_HOSTNAME"):
        return "postgresql://{user}:{password}@{host}:{port}/{name}".format(
            user=os.environ["RDS_USERNAME"],
            password=os.environ["RDS_PASSWORD"],
            host=os.environ["RDS_HOSTNAME"],
            port=os.environ.get("RDS_PORT", "5432"),
            name=os.environ.get("RDS_DB_NAME", "postgres"),
        )
    return "sqlite:///blacklist.db"


class Config:
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "devops-entrega1-blacklist-secret-key-cambiar")
    # El token es estatico/predefinido para toda la aplicacion, por eso no expira.
    JWT_ACCESS_TOKEN_EXPIRES = False
    PROPAGATE_EXCEPTIONS = True


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
