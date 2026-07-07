import { ref, type Ref } from 'vue';

export default function useAsyncRequest<T, Args extends unknown[] = []>(
  requester: (...args: Args) => Promise<T>
) {
  const loading = ref(false);
  const data = ref<T | null>(null) as Ref<T | null>;

  const run = async (...args: Args): Promise<T> => {
    loading.value = true;
    try {
      const result = await requester(...args);
      data.value = result;
      return result;
    } finally {
      loading.value = false;
    }
  };

  return { loading, data, run };
}
