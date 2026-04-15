"""
v0.6.0 迁移脚本：创建 switches 表（含 cached_info/is_online）和 server_switches 关联表
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
        # 检查 switches 表是否存在
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='switches'"))
        if result.fetchone():
            print("[migrate] switches 表已存在，检查并补充新列")
            # 补充新列（如果不存在）
            for col, col_type in [
                ("cached_info", "TEXT"),
                ("cached_at", "TIMESTAMP"),
                ("is_online", "INTEGER DEFAULT 0"),
                ("online_checked_at", "TIMESTAMP"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE switches ADD COLUMN {col} {col_type}"))
                    conn.commit()
                    print(f"[migrate] switches.{col} 列已添加")
                except Exception as e:
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        pass
                    else:
                        print(f"[migrate] switches.{col} 跳过: {e}")
        else:
            Base.metadata.create_all(bind=engine)
            print("[migrate] switches 和 server_switches 表已创建")

        # 检查 server_switches 表
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='server_switches'"))
        if result.fetchone():
            print("[migrate] server_switches 表已存在，跳过")
        else:
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
