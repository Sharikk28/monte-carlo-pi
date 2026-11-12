import math
import random


def solve(points, seed, on_progress):
    generator = random.Random(seed)
    chunk = points // 100
    inside = 0
    done = 0
    for percent in range(1, 101):
        if percent == 100:
            chunk = points - done
        for _ in range(chunk):
            x = generator.random()
            y = generator.random()
            if x * x + y * y <= 1:
                inside += 1
        done += chunk
        on_progress(percent, f"Оброблено {done} точок, π ≈ {4 * inside / done:.5f}")
    pi = 4 * inside / points
    return {"pi": pi, "error": abs(pi - math.pi), "inside": inside, "points": points}
