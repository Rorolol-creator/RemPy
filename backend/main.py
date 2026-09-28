from PQueue import *
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from PIL import Image
import imageio.v3 as iio
import io
import requests
import base64


app = FastAPI()


def propagation_custom(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    h, w = img.shape
    q = PQueue()
    distances = np.full((h, w), 1e10, dtype=float)

    for i in range(h):
        for j in range(w):
            if mask[i, j] > 0:
                distances[i, j] = 0.0
                q.push(0.0, (i, j))

    neighbors = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    while not q.empty():
        (p, (l, c)) = q.pop()

        if p > distances[l, c]:
            continue

        for dl, dc in neighbors:
            (ul, uc) = (l + dl, c + dc)
            # print(ul, " ", uc, " and h = ", h, " w = ", w)
            if 0 <= ul < h and 0 <= uc < w:
                dist = distances[l, c] + np.abs(int(img[l, c]) - int(img[ul, uc]))

                if dist < distances[ul, uc]:
                    distances[ul, uc] = dist
                    q.push(dist, (ul, uc))

    return distances


@njit
def heappush(heap_dist, heap_l, heap_c, heap_size, dist, l, c):
    i = heap_size
    parent = (i - 1) // 2

    while i > 0:
        parent = (i - 1) // 2
        if heap_dist[parent] <= dist:
            break

        heap_dist[i] = heap_dist[parent]
        heap_l[i] = heap_l[parent]
        heap_c[i] = heap_c[parent]

        i = parent

    heap_dist[i] = dist
    heap_l[i] = l
    heap_c[i] = c

    return heap_size + 1


@njit
def heappop(heap_dist, heap_l, heap_c, heap_size):
    dist = heap_dist[0]
    l = heap_l[0]
    c = heap_c[0]

    heap_size -= 1

    heap_dist[0] = heap_dist[heap_size]
    heap_l[0] = heap_l[heap_size]
    heap_c[0] = heap_c[heap_size]

    i = 0
    while True:
        left = 2 * i + 1
        right = 2 * i + 2
        smallest = i

        if left < heap_size and heap_dist[left] < heap_dist[smallest]:
            smallest = left
        if right < heap_size and heap_dist[right] < heap_dist[smallest]:
            smallest = right

        if smallest == i:
            break

        heap_dist[i], heap_dist[smallest] = heap_dist[smallest], heap_dist[i]
        heap_l[i], heap_l[smallest] = heap_l[smallest], heap_l[i]
        heap_c[i], heap_c[smallest] = heap_c[smallest], heap_c[i]

        i = smallest

    return dist, l, c, heap_size


@njit
def propagation_njit(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    h, w = img.shape
    img = img.astype(np.int64)

    heap_dist = np.empty(h * w, dtype=np.int64)
    heap_l = np.empty(h * w, dtype=np.int64)
    heap_c = np.empty(h * w, dtype=np.int64)
    heap_size = 0

    distances = np.full((h, w), 1e10, dtype=np.int64)

    for i in range(h):
        for j in range(w):
            if mask[i, j] > 0:
                distances[i, j] = 0

                heap_dist[heap_size] = 0
                heap_l[heap_size] = i
                heap_c[heap_size] = j
                heap_size += 1

    neighbors = ((-1, 0), (0, 1), (1, 0), (0, -1))
    while heap_size > 0:
        p, l, c, heap_size = heappop(heap_dist, heap_l, heap_c, heap_size)

        if p > distances[l, c]:
            continue

        for dl, dc in neighbors:
            (ul, uc) = (l + dl, c + dc)

            if 0 <= ul < h and 0 <= uc < w:
                if distances[ul, uc] <= distances[l, c]:
                    continue

                dist = int(distances[l, c] + np.abs(int(img[l, c]) - int(img[ul, uc])))
                if dist < distances[ul, uc]:
                    distances[ul, uc] = dist
                    heap_size = heappush(
                        heap_dist, heap_l, heap_c, heap_size, dist, ul, uc
                    )

    return distances


def compile():
    dummy_img = np.zeros((2, 2), dtype=np.int64)
    dummy_mask = np.zeros((2, 2), dtype=np.int64)
    propagation_njit(dummy_img, dummy_mask)


@app.post("/propagate")
async def get_images(img: UploadFile = File(...), mask: UploadFile = File(...)):
    img_bytes = await img.read()
    mask_bytes = await mask.read()

    image_ = Image.open(io.BytesIO(img_bytes)).convert("L")
    mask_ = Image.open(io.BytesIO(mask_bytes)).convert("L")

    if image_.size != mask_.size:
        raise HTTPException(
            status_code=400, detail="Image and mask dimensions do not match"
        )

    payload = {
        "img": (img.filename, img_bytes, img.content_type),
        "mask": (mask.filename, mask_bytes, mask.content_type),
    }

    response = requests.post("http://database:6000/load", files=payload)

    if response.ok:
        data = response.json()
        if data.get("exists"):
            return data

    npimg = np.array(image_)
    npmask = np.array(mask_)

    # Compiling Before computing the time it took
    compile()

    start = time.perf_counter()
    result_custom = propagation_custom(npimg, npmask)
    end_custom = time.perf_counter()
    result_njit = propagation_njit(npimg, npmask)
    end_njit = time.perf_counter()
    t_custom = end_custom - start
    t_njit = end_njit - end_custom
    files = {
        "bytes_custom": (
            "custom.bin",
            io.BytesIO(result_custom.tobytes()),
            "application/octet-stream",
        ),
        "bytes_njit": (
            "njit.bin",
            io.BytesIO(result_njit.tobytes()),
            "application/octet-stream",
        ),
    }

    data = {
        "image_filename": img.filename,
        "mask_filename": mask.filename,
        "t_custom": str(t_custom),
        "t_njit": str(t_njit),
        "shape": str(result_custom.shape),
    }

    requests.post("http://database:6000/save", files=files, data=data)

    custom_b64 = base64.b64encode(result_custom.tobytes()).decode("ascii")
    njit_b64 = base64.b64encode(result_njit.tobytes()).decode("ascii")

    return {
        "bytes_custom": custom_b64,
        "bytes_njit": njit_b64,
        "t_custom": t_custom,
        "t_njit": t_njit,
        "shape": str(result_custom.shape),
    }
