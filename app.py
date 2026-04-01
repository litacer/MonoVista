"""
MonoVista Flask 主入口

启动方式:
    python app.py
"""

# !! 必须最先执行：在 torch/transformers import 之前设置缓存路径 !!
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent
os.environ.setdefault("HF_HOME",               str(_PROJECT_ROOT / "models_cache" / "huggingface"))
os.environ.setdefault("TORCH_HOME",            str(_PROJECT_ROOT / "models_cache" / "torch"))
os.environ.setdefault("TRANSFORMERS_CACHE",    str(_PROJECT_ROOT / "models_cache" / "transformers"))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(_PROJECT_ROOT / "models_cache" / "huggingface" / "hub"))

from flask import Flask
from flask_cors import CORS
from loguru import logger
from dotenv import load_dotenv
from sqlalchemy import inspect, text

from backend.models.depth_estimator import init_pool
from backend.dibr.synthesizer import get_synthesizer
from backend.api.routes import api_bp
from backend.models.user import db

def _ensure_model_registry_columns(app: Flask):
    """轻量迁移：为已存在的 model_registry 表补齐新字段；同时补齐 users 表新字段。"""
    with app.app_context():
        insp = inspect(db.engine)
        tables = insp.get_table_names()

        # ── users 表迁移 ───────────────────────────────────────────
        if "users" in tables:
            user_cols = {c["name"] for c in insp.get_columns("users")}
            user_ddl = []
            if "signature" not in user_cols:
                user_ddl.append("ALTER TABLE users ADD COLUMN signature VARCHAR(100) NULL DEFAULT ''")
            if "phone" not in user_cols:
                user_ddl.append("ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL")
            for sql in user_ddl:
                db.session.execute(text(sql))
            if user_ddl:
                db.session.commit()
                logger.info(f"[migration] users 表已补齐字段: {user_ddl}")

        # ── model_registry 表迁移 ──────────────────────────────────
        if "model_registry" not in tables:
            return
        cols = {c["name"] for c in insp.get_columns("model_registry")}
        ddl = []
        if "display_name" not in cols:
            ddl.append("ALTER TABLE model_registry ADD COLUMN display_name VARCHAR(120) NULL")
        if "description" not in cols:
            ddl.append("ALTER TABLE model_registry ADD COLUMN description TEXT NULL")
        if "is_visible" not in cols:
            ddl.append("ALTER TABLE model_registry ADD COLUMN is_visible BOOLEAN NOT NULL DEFAULT 1")
        for sql in ddl:
            db.session.execute(text(sql))
        if ddl:
            db.session.commit()
            logger.info(f"[migration] model_registry 表已补齐字段: {ddl}")

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    db_user = os.getenv("MYSQL_USER", "root")
    db_pass = os.getenv("MYSQL_PASSWORD", "123456")
    db_host = os.getenv("MYSQL_HOST", "120.24.30.144")
    db_port = os.getenv("MYSQL_PORT", "13306")
    db_name = os.getenv("MYSQL_DB", "monovista")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        return {"message": "MonoVista API", "docs": "/api/health"}

    with app.app_context():
        db.create_all()

    _ensure_model_registry_columns(app)

    return app


app = create_app()


if __name__ == "__main__":
    default_model = os.getenv("DEPTH_MODEL_KEY", "dav2-small")
    device        = os.getenv("DEVICE", None) or None

    logger.info(f"HF_HOME    : {os.environ['HF_HOME']}")
    logger.info(f"TORCH_HOME : {os.environ['TORCH_HOME']}")
    logger.info(f"Loading default model: {default_model}, device={device}")
    init_pool(default_key=default_model, device=device)
    get_synthesizer()
    logger.info("MonoVista backend ready!")

    app.run(
        host="0.0.0.0",
        #host="127.0.0.1",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
