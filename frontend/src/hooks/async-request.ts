import { ref, type Ref } from 'vue';

export default function useAsyncRequest<T, Args extends unknown[] = []>(
  requester: (...args: Args) => Promise<T>,
) {
  // 初值 true：页面在 onMounted 首次运行时立刻进入加载态，
  // 避免第一帧闪出空表格/空图表；若实例从未 run，请勿依赖 loading 判断。
  const loading = ref(true);
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
      // 保留上一次成功的数据，由 AsyncState 展示「陈旧数据 + 失败横幅」
      error.value = err;
      return undefined;
    } finally {
      loading.value = false;
    }
  };

  return { loading, data, error, run };
}
