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
                activo                INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS kvk_temporadas (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                nombre   TEXT NOT NULL,
                activa   INTEGER DEFAULT 1,
                inicio   DATETIME DEFAULT CURRENT_TIMESTAMP,
                fin      DATETIME
            );

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
        try:
            await db.execute('ALTER TABLE mge_inscripciones ADD COLUMN cabezas INTEGER DEFAULT 0')
            await db.commit()
        except Exception:
            pass


# ─── Cola de títulos ───────────────────────────────────────────────────────────

async def add_to_queue(guild_id: str, user_id: str, username: str, titulo: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT id FROM cola_titulos WHERE guild_id=? AND user_id=? AND estado="pendiente"',
            (guild_id, user_id)
        )
        if await cursor.fetchone():
            return False
        await db.execute(
            'INSERT INTO cola_titulos (guild_id, user_id, username, titulo) VALUES (?,?,?,?)',
            (guild_id, user_id, username, titulo)
        )
        await db.commit()
        return True


async def get_queue(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM cola_titulos WHERE guild_id=? AND estado="pendiente" ORDER BY ts ASC',
            (guild_id,)
        )
        return await cursor.fetchall()


async def get_next(guild_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM cola_titulos WHERE guild_id=? AND estado="pendiente" ORDER BY ts ASC LIMIT 1',
            (guild_id,)
        )
        return await cursor.fetchone()


async def remove_from_queue(guild_id: str, user_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM cola_titulos WHERE guild_id=? AND user_id=? AND estado="pendiente"',
            (guild_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def mark_given(guild_id: str, user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE cola_titulos SET estado="dado" WHERE guild_id=? AND user_id=? AND estado="pendiente"',
            (guild_id, user_id)
        )
        await db.commit()


async def clear_queue(guild_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'DELETE FROM cola_titulos WHERE guild_id=? AND estado="pendiente"',
            (guild_id,)
        )
        await db.commit()


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


# ─── Eventos ──────────────────────────────────────────────────────────────────

async def create_event(guild_id: str, canal_id: str, rol_ping: str, nombre: str,
                       descripcion: str, hora: str, dias: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO eventos (guild_id, canal_id, rol_ping, nombre, descripcion, hora, dias)
            VALUES (?,?,?,?,?,?,?)
        ''', (guild_id, canal_id, rol_ping, nombre, descripcion, hora, dias))
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


async def delete_event(guild_id: str, event_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM eventos WHERE id=? AND guild_id=?',
            (event_id, guild_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_event_aviso(event_id: int, fecha: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE eventos SET dia_ultimo_aviso=? WHERE id=?', (fecha, event_id))
        await db.commit()


async def update_event_ejecucion(event_id: int, fecha: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE eventos SET dia_ultima_ejecucion=? WHERE id=?', (fecha, event_id))
        await db.commit()


# ─── KvK ──────────────────────────────────────────────────────────────────────

async def kvk_create(guild_id: str, nombre: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO kvk_temporadas (guild_id, nombre) VALUES (?,?)',
            (guild_id, nombre)
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
                (temporada_id, governor_id, governor_name, kills_t4, kills_t5, kill_points, muertes, dkp)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(temporada_id, governor_id) DO UPDATE SET
                governor_name = excluded.governor_name,
                kills_t4      = excluded.kills_t4,
                kills_t5      = excluded.kills_t5,
                kill_points   = excluded.kill_points,
                muertes       = excluded.muertes,
                dkp           = excluded.dkp,
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


# ─── MGE ──────────────────────────────────────────────────────────────────────

async def mge_crear_evento(guild_id: str, nombre: str, poder_min: int, max_plazas: int, descripcion: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO mge_eventos (guild_id, nombre, poder_min, max_plazas, descripcion) VALUES (?,?,?,?,?)',
            (guild_id, nombre, poder_min, max_plazas, descripcion)
        )
        await db.commit()
        return cursor.lastrowid


async def mge_get_eventos_activos(guild_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM mge_eventos WHERE guild_id=? AND activo=1 ORDER BY created_at ASC',
            (guild_id,)
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
                        gobernador: str, poder: int, cabezas: int = 0) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                'INSERT INTO mge_inscripciones (evento_id, guild_id, user_id, gobernador, poder, cabezas) VALUES (?,?,?,?,?,?)',
                (evento_id, guild_id, user_id, gobernador, poder, cabezas)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def mge_cancelar_inscripcion(evento_id: int, user_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM mge_inscripciones WHERE evento_id=? AND user_id=?',
            (evento_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def mge_get_inscritos(evento_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM mge_inscripciones WHERE evento_id=? ORDER BY poder DESC',
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
            'SELECT * FROM solicitudes_reclutamiento WHERE guild_id=? AND user_id=? AND estado="pendiente"',
            (guild_id, user_id)
        )
        return await cursor.fetchone()


async def reclu_get_por_canal(guild_id: str, canal_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM solicitudes_reclutamiento WHERE guild_id=? AND canal_id=? AND estado="pendiente"',
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
            'SELECT * FROM solicitudes_reclutamiento WHERE guild_id=? AND estado="pendiente" ORDER BY created_at ASC',
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
