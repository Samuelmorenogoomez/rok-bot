import os
import aiosqlite

DB_PATH = os.getenv('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'rok.db'))


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript('''
            CREATE TABLE IF NOT EXISTS cola_titulos (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT    NOT NULL,
                user_id  TEXT    NOT NULL,
                username TEXT    NOT NULL,
                titulo   TEXT    NOT NULL,
                estado   TEXT    DEFAULT 'pendiente',
                ts       DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS miembros (
                guild_id   TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                discord_name TEXT NOT NULL,
                gobernador TEXT NOT NULL,
                poder      INTEGER DEFAULT 0,
                tropa      TEXT DEFAULT 'mixto',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS eventos (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id              TEXT NOT NULL,
                canal_id              TEXT NOT NULL,
                rol_ping              TEXT DEFAULT '',
                nombre                TEXT NOT NULL,
                descripcion           TEXT DEFAULT '',
                hora                  TEXT NOT NULL,
                dias                  TEXT NOT NULL,
                dia_ultimo_aviso      TEXT DEFAULT '',
                dia_ultima_ejecucion  TEXT DEFAULT '',
                activo                INTEGER DEFAULT 1,
                puntual               INTEGER DEFAULT 0,
                fecha_unica           TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS kvk_temporadas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id      TEXT NOT NULL,
                nombre        TEXT NOT NULL,
                activa        INTEGER DEFAULT 1,
                inicio        DATETIME DEFAULT CURRENT_TIMESTAMP,
                fin           DATETIME,
                historia      TEXT DEFAULT '',
                fecha_inicio  TEXT DEFAULT '',
                fecha_fin     TEXT DEFAULT '',
                recuperacion  INTEGER DEFAULT 0,
                guerra_activa INTEGER DEFAULT 0,
                meta_kp         INTEGER DEFAULT 0,
                meta_aclamacion INTEGER DEFAULT 0,
                objetivos       TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS kvk_baseline_guerra (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                temporada_id  INTEGER NOT NULL,
                governor_id   TEXT NOT NULL,
                governor_name TEXT NOT NULL,
                kills_t4      INTEGER DEFAULT 0,
                kills_t5      INTEGER DEFAULT 0,
                muertes       INTEGER DEFAULT 0,
                UNIQUE (temporada_id, governor_id)
            );

            CREATE TABLE IF NOT EXISTS kvk_bajas_acumuladas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                temporada_id  INTEGER NOT NULL,
                governor_id   TEXT NOT NULL,
                governor_name TEXT NOT NULL,
                kills_t4      INTEGER DEFAULT 0,
                kills_t5      INTEGER DEFAULT 0,
                muertes       INTEGER DEFAULT 0,
                UNIQUE (temporada_id, governor_id)
            );

            -- Guerras contadas con el CSV de ROKSTATS: activa (foto inicial) → cerrada (foto final)
            CREATE TABLE IF NOT EXISTS kvk_guerras (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id        TEXT    NOT NULL,
                temporada_id    INTEGER NOT NULL,
                estado          TEXT    NOT NULL DEFAULT 'activa',
                activada_por    TEXT    DEFAULT '',
                inicio_ts       INTEGER NOT NULL,
                terminada_por   TEXT    DEFAULT '',
                fin_ts          INTEGER DEFAULT 0,
                csv_inicial     TEXT    DEFAULT '',
                csv_final       TEXT    DEFAULT ''
            );

            -- Kill Points de cada gobernador en el CSV inicial y en el final de cada guerra
            CREATE TABLE IF NOT EXISTS kvk_guerra_datos (
                guerra_id    INTEGER NOT NULL,
                fase         TEXT    NOT NULL,
                governor_id  TEXT    NOT NULL,
                nombre       TEXT    NOT NULL,
                kp           INTEGER NOT NULL,
                poder        INTEGER DEFAULT 0,
                PRIMARY KEY (guerra_id, fase, governor_id)
            );

            -- Sistema de capturas sustituido por el CSV (2026-10-20)
            DROP TABLE IF EXISTS kvk_capturas;

            CREATE TABLE IF NOT EXISTS kvk_stats (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                temporada_id INTEGER NOT NULL,
                guild_id     TEXT NOT NULL,
                user_id      TEXT NOT NULL,
                username     TEXT NOT NULL,
                kills_t4     INTEGER DEFAULT 0,
                kills_t5     INTEGER DEFAULT 0,
                muertes      INTEGER DEFAULT 0,
                updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (temporada_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS encuestas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    TEXT NOT NULL,
                canal_id    TEXT NOT NULL,
                mensaje_id  TEXT DEFAULT '',
                tipo        TEXT DEFAULT 'general',
                pregunta    TEXT NOT NULL,
                opciones    TEXT NOT NULL,
                activa      INTEGER DEFAULT 1,
                horas       INTEGER DEFAULT 24,
                creador_id  TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS encuesta_votos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                encuesta_id INTEGER NOT NULL,
                user_id     TEXT NOT NULL,
                opcion_idx  INTEGER NOT NULL,
                UNIQUE (encuesta_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS config_canales (
                guild_id  TEXT NOT NULL,
                tipo      TEXT NOT NULL,
                canal_id  TEXT NOT NULL,
                PRIMARY KEY (guild_id, tipo)
            );

            CREATE TABLE IF NOT EXISTS kvk_import (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                temporada_id  INTEGER NOT NULL,
                governor_id   TEXT NOT NULL,
                governor_name TEXT NOT NULL,
                kills_t4      INTEGER DEFAULT 0,
                kills_t5      INTEGER DEFAULT 0,
                kill_points   INTEGER DEFAULT 0,
                muertes       INTEGER DEFAULT 0,
                dkp           INTEGER DEFAULT 0,
                aclamacion    INTEGER DEFAULT 0,
                poder_delta   INTEGER DEFAULT 0,
                imported_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (temporada_id, governor_id)
            );

            CREATE TABLE IF NOT EXISTS config_general (
                guild_id TEXT NOT NULL,
                clave    TEXT NOT NULL,
                valor    TEXT NOT NULL,
                PRIMARY KEY (guild_id, clave)
            );

            CREATE TABLE IF NOT EXISTS mge_eventos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    TEXT NOT NULL,
                nombre      TEXT NOT NULL,
                poder_min   INTEGER DEFAULT 0,
                max_plazas  INTEGER DEFAULT 10,
                descripcion TEXT DEFAULT '',
                activo      INTEGER DEFAULT 1,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mge_inscripciones (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                evento_id  INTEGER NOT NULL,
                guild_id   TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                gobernador TEXT NOT NULL,
                poder      INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (evento_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS mge_seleccionados (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                evento_id   INTEGER NOT NULL,
                guild_id    TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                gobernador  TEXT NOT NULL,
                poder       INTEGER DEFAULT 0,
                posicion    INTEGER NOT NULL,
                assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (evento_id, user_id),
                UNIQUE (evento_id, posicion)
            );

            CREATE TABLE IF NOT EXISTS solicitudes_reclutamiento (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                canal_id   TEXT NOT NULL,
                gobernador TEXT DEFAULT '',
                poder      TEXT DEFAULT '',
                tropa      TEXT DEFAULT '',
                estado     TEXT DEFAULT 'pendiente',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS log_admin (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                user_name  TEXT NOT NULL,
                accion     TEXT NOT NULL,
                detalle    TEXT DEFAULT '',
                ts         INTEGER NOT NULL,
                mensaje_id TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS ausencias (
                guild_id   TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                hasta      DATETIME NOT NULL,
                motivo     TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            );
        ''')
        await db.commit()
        # Migración: añadir cabezas a mge_inscripciones si no existe
        for columna in ('cabezas INTEGER DEFAULT 0', 'cabezas_txt TEXT DEFAULT \'\''):
            try:
                await db.execute(f'ALTER TABLE mge_inscripciones ADD COLUMN {columna}')
                await db.commit()
            except Exception:
                pass
        # Migración: tablón de inscripción MGE (tropa, cierre automático, mensaje del tablón)
        for columna in (
            'tropa TEXT DEFAULT \'todas\'',
            'cierre_ts INTEGER DEFAULT 0',
            'canal_id TEXT DEFAULT \'\'',
            'mensaje_id TEXT DEFAULT \'\'',
            'inscripcion_abierta INTEGER DEFAULT 1',
        ):
            try:
                await db.execute(f'ALTER TABLE mge_eventos ADD COLUMN {columna}')
                await db.commit()
            except Exception:
                pass
        # Migración: añadir columnas a kvk_temporadas si no existen
        for columna in (
            'historia TEXT DEFAULT \'\'',
            'fecha_inicio TEXT DEFAULT \'\'',
            'fecha_fin TEXT DEFAULT \'\'',
            'recuperacion INTEGER DEFAULT 0',
            'guerra_activa INTEGER DEFAULT 0',
            'meta_kp INTEGER DEFAULT 0',
            'meta_aclamacion INTEGER DEFAULT 0',
            'objetivos TEXT DEFAULT \'\'',
        ):
            try:
                await db.execute(f'ALTER TABLE kvk_temporadas ADD COLUMN {columna}')
                await db.commit()
            except Exception:
                pass
        # Migración: aclamación y poder ganado/perdido de HeroScroll en kvk_import (metas y tablero del KvK)
        for columna in ('aclamacion INTEGER DEFAULT 0', 'poder_delta INTEGER DEFAULT 0'):
            try:
                await db.execute(f'ALTER TABLE kvk_import ADD COLUMN {columna}')
                await db.commit()
            except Exception:
                pass
        # Migración: CSV de ROKSTATS en kvk_guerras
        for columna in ('csv_inicial TEXT DEFAULT \'\'', 'csv_final TEXT DEFAULT \'\''):
            try:
                await db.execute(f'ALTER TABLE kvk_guerras ADD COLUMN {columna}')
                await db.commit()
            except Exception:
                pass
        # Migración: añadir puntual/fecha_unica a eventos si no existen
        for columna in ('puntual INTEGER DEFAULT 0', 'fecha_unica TEXT DEFAULT \'\''):
            try:
                await db.execute(f'ALTER TABLE eventos ADD COLUMN {columna}')
                await db.commit()
            except Exception:
                pass


# ─── Miembros ─────────────────────────────────────────────────────────────────

async def upsert_member(guild_id: str, user_id: str, discord_name: str, gobernador: str, poder: int, tropa: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO miembros (guild_id, user_id, discord_name, gobernador, poder, tropa, updated_at)
            VALUES (?,?,?,?,?,?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                discord_name = excluded.discord_name,
                gobernador   = excluded.gobernador,
                poder        = excluded.poder,
                tropa        = excluded.tropa,
                updated_at   = CURRENT_TIMESTAMP
        ''', (guild_id, user_id, discord_name, gobernador, poder, tropa))
        await db.commit()


async def get_member(guild_id: str, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM miembros WHERE guild_id=? AND user_id=?',
            (guild_id, user_id)
        )
        return await cursor.fetchone()


async def get_all_members(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM miembros WHERE guild_id=? ORDER BY poder DESC',
            (guild_id,)
        )
        return await cursor.fetchall()


async def get_miembros_externos(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM miembros WHERE guild_id=? AND user_id LIKE 'ext_%' ORDER BY gobernador ASC",
            (guild_id,)
        )
        return await cursor.fetchall()


# ─── Eventos ──────────────────────────────────────────────────────────────────

async def create_event(guild_id: str, canal_id: str, rol_ping: str, nombre: str,
                       descripcion: str, hora: str, dias: str,
                       puntual: bool = False, fecha_unica: str = '') -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO eventos (guild_id, canal_id, rol_ping, nombre, descripcion, hora, dias, puntual, fecha_unica)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (guild_id, canal_id, rol_ping, nombre, descripcion, hora, dias, int(puntual), fecha_unica))
        await db.commit()
        return cursor.lastrowid


async def get_all_active_events() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM eventos WHERE activo=1')
        return await cursor.fetchall()


async def get_guild_events(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM eventos WHERE guild_id=? AND activo=1 ORDER BY hora ASC',
            (guild_id,)
        )
        return await cursor.fetchall()


async def get_event(event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM eventos WHERE id=?', (event_id,))
        return await cursor.fetchone()


async def update_event(event_id: int, nombre: str, hora: str, dias: str,
                       puntual: bool, fecha_unica: str, rol_ping: str):
    # Se reinician las marcas de aviso para que, si cambia la hora, se vuelva a avisar hoy
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE eventos SET nombre=?, hora=?, dias=?, puntual=?, fecha_unica=?, rol_ping=?,
                               dia_ultimo_aviso='', dia_ultima_ejecucion=''
            WHERE id=?
        ''', (nombre, hora, dias, int(puntual), fecha_unica, rol_ping, event_id))
        await db.commit()


async def update_event_canal(event_id: int, canal_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE eventos SET canal_id=? WHERE id=?', (canal_id, event_id))
        await db.commit()


async def delete_event(guild_id: str, event_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM eventos WHERE id=? AND guild_id=?',
            (event_id, guild_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_event_by_id(event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM eventos WHERE id=?', (event_id,))
        await db.commit()


async def update_event_aviso(event_id: int, fecha: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE eventos SET dia_ultimo_aviso=? WHERE id=?', (fecha, event_id))
        await db.commit()


async def update_event_ejecucion(event_id: int, fecha: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE eventos SET dia_ultima_ejecucion=? WHERE id=?', (fecha, event_id))
        await db.commit()


# ─── KvK ──────────────────────────────────────────────────────────────────────

async def kvk_create(guild_id: str, nombre: str, historia: str = '',
                     fecha_inicio: str = '', fecha_fin: str = '', recuperacion: bool = False) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO kvk_temporadas (guild_id, nombre, historia, fecha_inicio, fecha_fin, recuperacion) VALUES (?,?,?,?,?,?)',
            (guild_id, nombre, historia, fecha_inicio, fecha_fin, int(recuperacion))
        )
        await db.commit()
        return cursor.lastrowid


async def kvk_end_active(guild_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'UPDATE kvk_temporadas SET activa=0, fin=CURRENT_TIMESTAMP WHERE guild_id=? AND activa=1',
            (guild_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def kvk_get_active(guild_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM kvk_temporadas WHERE guild_id=? AND activa=1 ORDER BY id DESC LIMIT 1',
            (guild_id,)
        )
        return await cursor.fetchone()


async def kvk_set_metas(temporada_id: int, meta_kp: int, meta_aclamacion: int, objetivos: str):
    """Metas por jugador (0 = sin meta) y objetivos del KvK; se pueden cambiar con la temporada en curso."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE kvk_temporadas SET meta_kp=?, meta_aclamacion=?, objetivos=? WHERE id=?',
            (meta_kp, meta_aclamacion, objetivos, temporada_id)
        )
        await db.commit()


async def kvk_upsert_stats(temporada_id: int, guild_id: str, user_id: str,
                           username: str, kills_t4: int, kills_t5: int, muertes: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO kvk_stats (temporada_id, guild_id, user_id, username, kills_t4, kills_t5, muertes, updated_at)
            VALUES (?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
            ON CONFLICT(temporada_id, user_id) DO UPDATE SET
                username   = excluded.username,
                kills_t4   = excluded.kills_t4,
                kills_t5   = excluded.kills_t5,
                muertes    = excluded.muertes,
                updated_at = CURRENT_TIMESTAMP
        ''', (temporada_id, guild_id, user_id, username, kills_t4, kills_t5, muertes))
        await db.commit()


async def kvk_get_ranking(temporada_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT * FROM kvk_stats
            WHERE temporada_id=?
            ORDER BY (kills_t4 + kills_t5) DESC
        ''', (temporada_id,))
        return await cursor.fetchall()


async def kvk_get_player_stats(temporada_id: int, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM kvk_stats WHERE temporada_id=? AND user_id=?',
            (temporada_id, user_id)
        )
        return await cursor.fetchone()


# ─── Encuestas ────────────────────────────────────────────────────────────────

async def create_encuesta(guild_id: str, canal_id: str, tipo: str, pregunta: str,
                          opciones_json: str, horas: int, creador_id: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO encuestas (guild_id, canal_id, tipo, pregunta, opciones, horas, creador_id) VALUES (?,?,?,?,?,?,?)',
            (guild_id, canal_id, tipo, pregunta, opciones_json, horas, creador_id)
        )
        await db.commit()
        return cursor.lastrowid


async def update_encuesta_mensaje(encuesta_id: int, mensaje_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE encuestas SET mensaje_id=? WHERE id=?', (mensaje_id, encuesta_id))
        await db.commit()


async def get_encuesta(encuesta_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM encuestas WHERE id=?', (encuesta_id,))
        return await cursor.fetchone()


async def get_all_active_encuestas() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM encuestas WHERE activa=1')
        return await cursor.fetchall()


async def upsert_vote(encuesta_id: int, user_id: str, opcion_idx: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO encuesta_votos (encuesta_id, user_id, opcion_idx)
            VALUES (?,?,?)
            ON CONFLICT(encuesta_id, user_id) DO UPDATE SET opcion_idx=excluded.opcion_idx
        ''', (encuesta_id, user_id, opcion_idx))
        await db.commit()


async def get_user_vote(encuesta_id: int, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM encuesta_votos WHERE encuesta_id=? AND user_id=?',
            (encuesta_id, user_id)
        )
        return await cursor.fetchone()


async def get_votos(encuesta_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM encuesta_votos WHERE encuesta_id=?', (encuesta_id,)
        )
        return await cursor.fetchall()


async def close_encuesta(encuesta_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE encuestas SET activa=0 WHERE id=?', (encuesta_id,))
        await db.commit()


# ─── Config canales ───────────────────────────────────────────────────────────

async def set_canal_config(guild_id: str, tipo: str, canal_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO config_canales (guild_id, tipo, canal_id)
            VALUES (?,?,?)
            ON CONFLICT(guild_id, tipo) DO UPDATE SET canal_id=excluded.canal_id
        ''', (guild_id, tipo, canal_id))
        await db.commit()


async def get_canal_config(guild_id: str, tipo: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM config_canales WHERE guild_id=? AND tipo=?',
            (guild_id, tipo)
        )
        return await cursor.fetchone()


async def get_config(guild_id: str, clave: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT valor FROM config_general WHERE guild_id=? AND clave=?',
            (guild_id, clave)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def kvk_clear_import(temporada_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM kvk_import WHERE temporada_id=?', (temporada_id,))
        await db.commit()


async def kvk_clear_stats(temporada_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM kvk_stats WHERE temporada_id=?', (temporada_id,))
        await db.commit()


async def kvk_insert_import(temporada_id: int, rows: list):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany('''
            INSERT INTO kvk_import
                (temporada_id, governor_id, governor_name, kills_t4, kills_t5, kill_points, muertes, dkp, aclamacion,
                 poder_delta)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(temporada_id, governor_id) DO UPDATE SET
                governor_name = excluded.governor_name,
                kills_t4      = excluded.kills_t4,
                kills_t5      = excluded.kills_t5,
                kill_points   = excluded.kill_points,
                muertes       = excluded.muertes,
                dkp           = excluded.dkp,
                aclamacion    = excluded.aclamacion,
                poder_delta   = excluded.poder_delta,
                imported_at   = CURRENT_TIMESTAMP
        ''', rows)
        await db.commit()


async def kvk_get_import_ranking(temporada_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT * FROM kvk_import
            WHERE temporada_id=?
            ORDER BY (kills_t4 + kills_t5) DESC
        ''', (temporada_id,))
        return await cursor.fetchall()


async def kvk_clear_guerras(temporada_id: int):
    """Borra las guerras cerradas de la temporada y sus datos."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM kvk_guerra_datos WHERE guerra_id IN "
            "(SELECT id FROM kvk_guerras WHERE temporada_id=? AND estado='cerrada')", (temporada_id,)
        )
        await db.execute("DELETE FROM kvk_guerras WHERE temporada_id=? AND estado='cerrada'", (temporada_id,))
        await db.commit()


# ─── Guerras (CSV de ROKSTATS) ────────────────────────────────────────────────

async def _insertar_datos(db, guerra_id: int, fase: str, filas: list):
    await db.executemany(
        'INSERT OR REPLACE INTO kvk_guerra_datos (guerra_id, fase, governor_id, nombre, kp, poder) VALUES (?,?,?,?,?,?)',
        [(guerra_id, fase, f['governor_id'], f['nombre'], f['kp'], f['poder']) for f in filas]
    )


async def guerra_get(guerra_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM kvk_guerras WHERE id=?', (guerra_id,))
        return await cursor.fetchone()


async def guerra_get_abierta(guild_id: str):
    """Guerra activa (como mucho hay una)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM kvk_guerras WHERE guild_id=? AND estado='activa' ORDER BY id DESC LIMIT 1",
            (guild_id,)
        )
        return await cursor.fetchone()


async def guerra_crear(guild_id: str, temporada_id: int, user_id: str, ts: int, csv_nombre: str, filas: list) -> int:
    """Crea la guerra con la foto inicial del CSV."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO kvk_guerras (guild_id, temporada_id, activada_por, inicio_ts, csv_inicial) VALUES (?,?,?,?,?)',
            (guild_id, temporada_id, user_id, ts, csv_nombre)
        )
        guerra_id = cursor.lastrowid
        await _insertar_datos(db, guerra_id, 'inicial', filas)
        await db.execute('UPDATE kvk_temporadas SET guerra_activa=1 WHERE id=?', (temporada_id,))
        await db.commit()
        return guerra_id


async def guerra_cerrar(guerra_id: int, user_id: str, ts: int, csv_nombre: str, filas: list) -> bool:
    """Guarda la foto final del CSV y cierra la guerra."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE kvk_guerras SET estado='cerrada', terminada_por=?, fin_ts=?, csv_final=? "
            "WHERE id=? AND estado='activa'",
            (user_id, ts, csv_nombre, guerra_id)
        )
        if cursor.rowcount == 0:
            return False
        await _insertar_datos(db, guerra_id, 'final', filas)
        await db.execute(
            'UPDATE kvk_temporadas SET guerra_activa=0 WHERE id=(SELECT temporada_id FROM kvk_guerras WHERE id=?)',
            (guerra_id,)
        )
        await db.commit()
        return True


async def guerra_cancelar(guerra_id: int) -> bool:
    """Anula una guerra activa sin contar nada."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT temporada_id FROM kvk_guerras WHERE id=? AND estado='activa'", (guerra_id,))
        fila = await cursor.fetchone()
        if not fila:
            return False
        await db.execute('DELETE FROM kvk_guerra_datos WHERE guerra_id=?', (guerra_id,))
        await db.execute('DELETE FROM kvk_guerras WHERE id=?', (guerra_id,))
        await db.execute('UPDATE kvk_temporadas SET guerra_activa=0 WHERE id=?', (fila[0],))
        await db.commit()
        return True


async def guerra_numero(guerra) -> int:
    """Número de la guerra dentro de su temporada (1, 2, 3…)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT COUNT(*) FROM kvk_guerras WHERE temporada_id=? AND id<=?',
            (guerra['temporada_id'], guerra['id'])
        )
        return (await cursor.fetchone())[0]


async def guerra_contar_datos(guerra_id: int, fase: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT COUNT(*) FROM kvk_guerra_datos WHERE guerra_id=? AND fase=?', (guerra_id, fase)
        )
        return (await cursor.fetchone())[0]


async def guerra_get_datos(guerra_id: int, fase: str) -> dict:
    """{governor_id: kp} de una fase."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT governor_id, kp FROM kvk_guerra_datos WHERE guerra_id=? AND fase=?', (guerra_id, fase)
        )
        return {r[0]: r[1] for r in await cursor.fetchall()}


async def guerra_resultados(guerra_id: int) -> list:
    """Gobernadores presentes en los dos CSV, con sus KP hechos, de más a menos."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT f.governor_id, f.nombre, i.kp AS kp_inicial, f.kp AS kp_final, f.poder,
                   MAX(f.kp - i.kp, 0) AS ganados
            FROM kvk_guerra_datos i
            JOIN kvk_guerra_datos f
              ON f.guerra_id = i.guerra_id AND f.governor_id = i.governor_id AND f.fase = 'final'
            WHERE i.guerra_id = ? AND i.fase = 'inicial'
            ORDER BY ganados DESC
        ''', (guerra_id,))
        return await cursor.fetchall()


async def guerra_ranking_temporada(temporada_id: int) -> list:
    """KP hechos en guerra sumando todas las guerras cerradas de la temporada."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT f.governor_id,
                   (SELECT d.nombre FROM kvk_guerra_datos d
                     WHERE d.governor_id = f.governor_id ORDER BY d.guerra_id DESC LIMIT 1) AS nombre,
                   SUM(MAX(f.kp - i.kp, 0)) AS ganados,
                   SUM(CASE WHEN f.kp > i.kp THEN 1 ELSE 0 END) AS guerras
            FROM kvk_guerras g
            JOIN kvk_guerra_datos i ON i.guerra_id = g.id AND i.fase = 'inicial'
            JOIN kvk_guerra_datos f ON f.guerra_id = g.id AND f.governor_id = i.governor_id AND f.fase = 'final'
            WHERE g.temporada_id = ? AND g.estado = 'cerrada'
            GROUP BY f.governor_id
            HAVING ganados > 0
            ORDER BY ganados DESC
        ''', (temporada_id,))
        return await cursor.fetchall()


# ─── MGE ──────────────────────────────────────────────────────────────────────

async def mge_crear_evento(guild_id: str, nombre: str, poder_min: int, max_plazas: int, descripcion: str,
                           tropa: str = 'todas', cierre_ts: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO mge_eventos (guild_id, nombre, poder_min, max_plazas, descripcion, tropa, cierre_ts) '
            'VALUES (?,?,?,?,?,?,?)',
            (guild_id, nombre, poder_min, max_plazas, descripcion, tropa, cierre_ts)
        )
        await db.commit()
        return cursor.lastrowid


async def mge_set_tablon(evento_id: int, canal_id: str, mensaje_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE mge_eventos SET canal_id=?, mensaje_id=? WHERE id=?',
            (canal_id, mensaje_id, evento_id)
        )
        await db.commit()


async def mge_get_evento_por_mensaje(mensaje_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM mge_eventos WHERE mensaje_id=?', (mensaje_id,))
        return await cursor.fetchone()


async def mge_set_inscripcion_abierta(evento_id: int, abierta: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE mge_eventos SET inscripcion_abierta=? WHERE id=?',
            (1 if abierta else 0, evento_id)
        )
        await db.commit()


async def mge_get_pendientes_autocierre(ahora_ts: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM mge_eventos WHERE activo=1 AND inscripcion_abierta=1 AND cierre_ts>0 AND cierre_ts<=?',
            (ahora_ts,)
        )
        return await cursor.fetchall()


async def mge_set_meta_individual(evento_id: int, user_id: str, meta: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'UPDATE mge_seleccionados SET poder=? WHERE evento_id=? AND user_id=?',
            (meta, evento_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def mge_get_eventos_activos(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM mge_eventos WHERE guild_id=? AND activo=1 ORDER BY created_at ASC',
            (guild_id,)
        )
        return await cursor.fetchall()


async def mge_get_eventos_cerrados(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM mge_eventos WHERE guild_id=? AND activo=0 ORDER BY created_at DESC',
            (guild_id,)
        )
        return await cursor.fetchall()


async def mge_get_historial_usuario(guild_id: str, user_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            '''
            SELECT e.nombre, e.poder_min, e.created_at, s.posicion, s.poder as meta_individual
            FROM mge_seleccionados s
            JOIN mge_eventos e ON s.evento_id = e.id
            WHERE s.guild_id=? AND s.user_id=?
            ORDER BY e.created_at DESC
            ''',
            (guild_id, user_id)
        )
        return await cursor.fetchall()


async def mge_get_evento(evento_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM mge_eventos WHERE id=?', (evento_id,))
        return await cursor.fetchone()


async def mge_cerrar_evento(guild_id: str, evento_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'UPDATE mge_eventos SET activo=0 WHERE id=? AND guild_id=?',
            (evento_id, guild_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def mge_inscribir(evento_id: int, guild_id: str, user_id: str,
                        gobernador: str, poder: int, cabezas: int = 0, cabezas_txt: str = '') -> bool:
    """Inscribe o actualiza las cabezas si ya estaba inscrito. Devuelve True si es una inscripción nueva."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT 1 FROM mge_inscripciones WHERE evento_id=? AND user_id=?', (evento_id, user_id)
        )
        nueva = await cursor.fetchone() is None
        await db.execute(
            'INSERT INTO mge_inscripciones (evento_id, guild_id, user_id, gobernador, poder, cabezas, cabezas_txt) '
            'VALUES (?,?,?,?,?,?,?) '
            'ON CONFLICT(evento_id, user_id) DO UPDATE SET '
            'gobernador=excluded.gobernador, poder=excluded.poder, '
            'cabezas=excluded.cabezas, cabezas_txt=excluded.cabezas_txt',
            (evento_id, guild_id, user_id, gobernador, poder, cabezas, cabezas_txt)
        )
        await db.commit()
        return nueva


async def mge_cancelar_inscripcion(evento_id: int, user_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM mge_inscripciones WHERE evento_id=? AND user_id=?',
            (evento_id, user_id)
        )
        # Si tenía plaza asignada, se libera
        await db.execute(
            'DELETE FROM mge_seleccionados WHERE evento_id=? AND user_id=?',
            (evento_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def mge_get_inscritos(evento_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM mge_inscripciones WHERE evento_id=? ORDER BY id ASC',
            (evento_id,)
        )
        return await cursor.fetchall()


async def mge_count_inscritos(evento_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT COUNT(*) FROM mge_inscripciones WHERE evento_id=?', (evento_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def mge_seleccionar(evento_id: int, guild_id: str, user_id: str,
                          gobernador: str, poder: int, posicion: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        # Liberar esa posición si ya estaba ocupada por otro usuario
        await db.execute(
            'DELETE FROM mge_seleccionados WHERE evento_id=? AND posicion=? AND user_id!=?',
            (evento_id, posicion, user_id)
        )
        # Liberar al usuario de cualquier posición anterior que tuviera
        await db.execute(
            'DELETE FROM mge_seleccionados WHERE evento_id=? AND user_id=?',
            (evento_id, user_id)
        )
        await db.execute(
            'INSERT INTO mge_seleccionados (evento_id, guild_id, user_id, gobernador, poder, posicion) '
            'VALUES (?,?,?,?,?,?)',
            (evento_id, guild_id, user_id, gobernador, poder, posicion)
        )
        await db.commit()
        return True


async def mge_quitar_seleccion(evento_id: int, user_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM mge_seleccionados WHERE evento_id=? AND user_id=?',
            (evento_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def mge_vaciar_seleccion(evento_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('DELETE FROM mge_seleccionados WHERE evento_id=?', (evento_id,))
        await db.commit()
        return cursor.rowcount


async def mge_get_seleccionados(evento_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM mge_seleccionados WHERE evento_id=? ORDER BY posicion ASC',
            (evento_id,)
        )
        return await cursor.fetchall()


async def mge_get_inscripcion(evento_id: int, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM mge_inscripciones WHERE evento_id=? AND user_id=?',
            (evento_id, user_id)
        )
        return await cursor.fetchone()


# ─── Ausencias ────────────────────────────────────────────────────────────────

# ─── Reclutamiento ────────────────────────────────────────────────────────────

async def reclu_crear_solicitud(guild_id: str, user_id: str, canal_id: str,
                                gobernador: str, poder: str, tropa: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO solicitudes_reclutamiento (guild_id, user_id, canal_id, gobernador, poder, tropa) VALUES (?,?,?,?,?,?)',
            (guild_id, user_id, canal_id, gobernador, poder, tropa)
        )
        await db.commit()
        return cursor.lastrowid


async def reclu_get_solicitud_activa(guild_id: str, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM solicitudes_reclutamiento WHERE guild_id=? AND user_id=? AND estado='pendiente'",
            (guild_id, user_id)
        )
        return await cursor.fetchone()


async def reclu_get_por_canal(guild_id: str, canal_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM solicitudes_reclutamiento WHERE guild_id=? AND canal_id=? AND estado='pendiente'",
            (guild_id, canal_id)
        )
        return await cursor.fetchone()


async def reclu_actualizar_estado(solicitud_id: int, estado: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE solicitudes_reclutamiento SET estado=? WHERE id=?', (estado, solicitud_id))
        await db.commit()


async def reclu_get_pendientes(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM solicitudes_reclutamiento WHERE guild_id=? AND estado='pendiente' ORDER BY created_at ASC",
            (guild_id,)
        )
        return await cursor.fetchall()


# ─── Ausencias ────────────────────────────────────────────────────────────────

async def set_ausencia(guild_id: str, user_id: str, hasta: str, motivo: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO ausencias (guild_id, user_id, hasta, motivo)
            VALUES (?,?,?,?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                hasta  = excluded.hasta,
                motivo = excluded.motivo,
                created_at = CURRENT_TIMESTAMP
        ''', (guild_id, user_id, hasta, motivo))
        await db.commit()


async def get_ausencia(guild_id: str, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM ausencias WHERE guild_id=? AND user_id=? AND hasta > CURRENT_TIMESTAMP',
            (guild_id, user_id)
        )
        return await cursor.fetchone()


async def clear_ausencia(guild_id: str, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM ausencias WHERE guild_id=? AND user_id=?', (guild_id, user_id))
        await db.commit()


async def get_all_ausentes(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT a.user_id, a.hasta, a.motivo, m.gobernador, m.discord_name
            FROM ausencias a
            LEFT JOIN miembros m ON a.guild_id = m.guild_id AND a.user_id = m.user_id
            WHERE a.guild_id=? AND a.hasta > CURRENT_TIMESTAMP
            ORDER BY a.hasta ASC
        ''', (guild_id,))
        return await cursor.fetchall()


async def get_ausentes_ids(guild_id: str) -> set:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT user_id FROM ausencias WHERE guild_id=? AND hasta > CURRENT_TIMESTAMP',
            (guild_id,)
        )
        rows = await cursor.fetchall()
        return {r[0] for r in rows}


async def set_config(guild_id: str, clave: str, valor: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO config_general (guild_id, clave, valor)
            VALUES (?,?,?)
            ON CONFLICT(guild_id, clave) DO UPDATE SET valor=excluded.valor
        ''', (guild_id, clave, valor))
        await db.commit()


async def get_all_canales_config(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM config_canales WHERE guild_id=?', (guild_id,)
        )
        return await cursor.fetchall()


# ─── Registro de acciones de admin ────────────────────────────────────────────
# Solo se añade. La única forma de borrar es la purga automática de lo que tiene más de
# RETENCION_DIAS (cogs/registro.py), que decidió el usuario para que no se llene.

async def log_insertar(guild_id: str, user_id: str, user_name: str, accion: str, detalle: str, ts: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO log_admin (guild_id, user_id, user_name, accion, detalle, ts) VALUES (?,?,?,?,?,?)',
            (guild_id, user_id, user_name, accion, detalle, ts)
        )
        await db.commit()
        return cursor.lastrowid


async def log_set_mensaje(log_id: int, mensaje_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE log_admin SET mensaje_id=? WHERE id=?', (mensaje_id, log_id))
        await db.commit()


async def log_get_por_mensajes(mensaje_ids: list[str]) -> list:
    if not mensaje_ids:
        return []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        marcas = ','.join('?' * len(mensaje_ids))
        cursor = await db.execute(f'SELECT * FROM log_admin WHERE mensaje_id IN ({marcas}) ORDER BY id', mensaje_ids)
        return await cursor.fetchall()


async def log_buscar(guild_id: str, user_id: str = None, texto: str = None, limite: int = 20) -> list:
    sql, params = 'SELECT * FROM log_admin WHERE guild_id=?', [guild_id]
    if user_id:
        sql += ' AND user_id=?'
        params.append(user_id)
    if texto:
        sql += ' AND (accion LIKE ? OR detalle LIKE ?)'
        params += [f'%{texto}%', f'%{texto}%']
    sql += ' ORDER BY id DESC LIMIT ?'
    params.append(limite)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        return await cursor.fetchall()


async def log_purgar_antiguos(guild_id: str, antes_ts: int) -> list[str]:
    """Borra los registros anteriores a antes_ts y devuelve los IDs de sus mensajes en Discord."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT mensaje_id FROM log_admin WHERE guild_id=? AND ts<? AND mensaje_id!=''", (guild_id, antes_ts)
        )
        mensajes = [r[0] for r in await cursor.fetchall()]
        await db.execute('DELETE FROM log_admin WHERE guild_id=? AND ts<?', (guild_id, antes_ts))
        await db.commit()
        return mensajes
