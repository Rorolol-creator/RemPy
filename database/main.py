import psycopg2

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import base64

app = FastAPI()

conn = psycopg2.connect(
    dbname="benchmark_db",
    user="benchmark_user",
    password="secret",
    host="postgres",
    port=5432,
)
conn.autocommit = True

cur = conn.cursor()

with conn.cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS benchmarks (
            id SERIAL PRIMARY KEY,
            image_filename TEXT NOT NULL,
            mask_filename TEXT NOT NULL,
            bytes_custom BYTEA NOT NULL,
            t_custom REAL,
            bytes_njit BYTEA NOT NULL,
            t_njit REAL,
            shape TEXT NOT NULL,
            UNIQUE(image_filename, mask_filename)
        )
    """)


@app.post("/save")
async def save(
    image_filename: str = Form(...),
    mask_filename: str = Form(...),
    bytes_custom: UploadFile = File(...),
    t_custom: float = Form(...),
    bytes_njit: UploadFile = File(...),
    t_njit: float = Form(...),
    shape: str = Form(...),
):
    custom = await bytes_custom.read()
    njit = await bytes_njit.read()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO benchmarks
                (image_filename, mask_filename, bytes_custom, t_custom, bytes_njit, t_njit, shape)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (image_filename, mask_filename)
                DO UPDATE SET
                    bytes_custom = EXCLUDED.bytes_custom,
                    t_custom = EXCLUDED.t_custom,
                    bytes_njit = EXCLUDED.bytes_njit,
                    t_njit = EXCLUDED.t_njit,
                    shape = EXCLUDED.shape
                """,
                (
                    image_filename,
                    mask_filename,
                    psycopg2.Binary(custom),
                    t_custom,
                    psycopg2.Binary(njit),
                    t_njit,
                    shape,
                ),
            )
        return {"status": "saved"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.post("/load")
async def load(img: UploadFile = File(...), mask: UploadFile = File(...)):
    img_name = img.filename
    mask_name = mask.filename

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bytes_custom, t_custom, bytes_njit, t_njit, shape FROM benchmarks
            WHERE image_filename = %s AND mask_filename = %s
            LIMIT 1
        """,
            (img_name, mask_name),
        )
        result = cur.fetchone()

    if result:
        bytes_custom, t_custom, bytes_njit, t_njit, shape = result
        custom_b64 = base64.b64encode(bytes_custom).decode("ascii")
        njit_b64 = base64.b64encode(bytes_njit).decode("ascii")
        return {
            "exists": True,
            "bytes_custom": custom_b64,
            "t_custom": t_custom,
            "bytes_njit": njit_b64,
            "t_njit": t_njit,
            "shape": shape,
        }
    return {"exists": False}


@app.get("/all")
async def get_all():
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, image_filename, mask_filename, t_custom, t_njit
            FROM benchmarks
            ORDER BY id DESC
        """)
        rows = cur.fetchall()

    return [
        {
            "id": r[0],
            "image": r[1],
            "mask": r[2],
            "t_custom": r[3],
            "t_njit": r[4],
        }
        for r in rows
    ]


@app.get("/specific")
async def get_specific(id: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bytes_custom, t_custom, bytes_njit, t_njit, shape FROM benchmarks
            WHERE id = %s
            LIMIT 1
        """,
            (id,),
        )
        result = cur.fetchone()

    if result:
        bytes_custom, t_custom, bytes_njit, t_njit, shape = result
        custom_b64 = base64.b64encode(bytes_custom).decode("ascii")
        njit_b64 = base64.b64encode(bytes_njit).decode("ascii")
        return {
            "exists": True,
            "bytes_custom": custom_b64,
            "t_custom": t_custom,
            "bytes_njit": njit_b64,
            "t_njit": t_njit,
            "shape": shape,
        }
    return {"exists": False}
