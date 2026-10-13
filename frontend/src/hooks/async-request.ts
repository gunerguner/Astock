import { ref, type Ref } from 'vue';

export default function useAsyncRequest<T, Args extends unknown[] = []>(
  requester: (...args: Args) => Promise<T>,
) {
  const loading = ref(false);
  const data = ref<T | null>(null) as Ref<T | null>;
  const error = ref<unknown>(null);

  const run = async (...args: Args): Promise<T | undefined> => {
    loading.value = true;
    error.value = null;
    try {
      const result = await requester(...args);
      data.value = result;
      return result;
    } catch (err) {
      data.value = null;
      error.value = err;
      return undefined;
    } finally {
      loading.value = false;
    }
  };

  return { loading, data, error, run };
}
