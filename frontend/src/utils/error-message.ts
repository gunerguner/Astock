export default function describeError(
  error: unknown,
  fallback: string,
): string {
  if (typeof error === 'string' && error.trim()) return error.trim();
  if (!error || typeof error !== 'object') return fallback;

  const { response } = error as {
    response?: { data?: { message?: unknown } };
  };
  const apiMessage = response?.data?.message;
  if (typeof apiMessage === 'string' && apiMessage.trim()) {
    return apiMessage.trim();
  }
  if (error instanceof Error && error.message.trim()) {
    const message = error.message.trim();
    if (message === 'Network Error') return fallback;
    return message;
  }
  return fallback;
}
