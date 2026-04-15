"""
v0.6.0 迁移脚本：创建 switches 表和 server_switches 关联表
用法: python -m infrastructure.migrate_to_v060
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, Base
from app.models.switch import Switch
from app.models.server import Server  # 触发 relationship 加载
from sqlalchemy import text

def run():
    with engine.connect() as conn:
        # 检查 switches 表是否已存在
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='switches'"))
        if result.fetchone():
            print("[migrate] switches 表已存在，跳过")
        else:
            Base.metadata.create_all(bind=engine)
            print("[migrate] switches 和 server_switches 表已创建")

        # 检查 server_switches 表
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='server_switches'"))
        if result.fetchone():
            print("[migrate] server_switches 表已存在，跳过")
        else:
            # 手动创建关联表（如果 Base.metadata.create_all 没自动创建）
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS server_switches (
                    server_id INTEGER NOT NULL,
                    switch_id INTEGER NOT NULL,
                    PRIMARY KEY (server_id, switch_id),
                    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE,
                    FOREIGN KEY (switch_id) REFERENCES switches(id) ON DELETE CASCADE
                )
            """))
            conn.commit()
            print("[migrate] server_switches 表已创建")

if __name__ == "__main__":
    run()
