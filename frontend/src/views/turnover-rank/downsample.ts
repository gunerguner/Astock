/**
 * Largest-Triangle-Three-Buckets。
 * 点数不超过 threshold 时原样返回；超出时保留首尾，并在每个时间桶里留下面积最大的真实点。
 */
export default function downsampleLttb<T>(
  points: T[],
  threshold: number,
  valueOf: (point: T) => number,
): T[] {
  const { length } = points;
  if (threshold >= length || threshold < 3) return points;

  const sampled: T[] = [points[0]];
  const bucketSize = (length - 2) / (threshold - 2);
  let previous = 0;

  for (let bucket = 0; bucket < threshold - 2; bucket += 1) {
    const avgStart = Math.floor((bucket + 1) * bucketSize) + 1;
    let avgEnd = Math.floor((bucket + 2) * bucketSize) + 1;
    avgEnd = Math.min(avgEnd, length);
    const avgCount = avgEnd - avgStart;

    let avgX = 0;
    let avgY = 0;
    if (avgCount > 0) {
      for (let index = avgStart; index < avgEnd; index += 1) {
        avgX += index;
        avgY += valueOf(points[index]);
      }
      avgX /= avgCount;
      avgY /= avgCount;
    } else {
      avgX = length - 1;
      avgY = valueOf(points[length - 1]);
    }

    const rangeStart = Math.floor(bucket * bucketSize) + 1;
    const rangeEnd = Math.min(
      Math.floor((bucket + 1) * bucketSize) + 1,
      length,
    );
    if (rangeStart < rangeEnd) {
      const previousX = previous;
      const previousY = valueOf(points[previous]);
      let maxArea = -1;
      let selected = rangeStart;

      for (let index = rangeStart; index < rangeEnd; index += 1) {
        const area = Math.abs(
          (previousX - avgX) * (valueOf(points[index]) - previousY) -
            (previousX - index) * (avgY - previousY),
        );
        if (area > maxArea) {
          maxArea = area;
          selected = index;
        }
      }

      sampled.push(points[selected]);
      previous = selected;
    }
  }

  sampled.push(points[length - 1]);
  return sampled;
}
