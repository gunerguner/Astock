import axios from 'axios';
import type { AxiosRequestConfig, AxiosResponse } from 'axios';
import { Message } from '@arco-design/web-vue';

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export type HttpResponse<T = unknown> = ApiResponse<T>;

axios.defaults.baseURL = '/api/v1';

axios.interceptors.request.use(
  (config: AxiosRequestConfig) => config,
  (error) => Promise.reject(error)
);

axios.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data;
    if (res.code !== 0) {
      Message.error({
        content: res.message || '请求失败',
        duration: 5 * 1000,
      });
      return Promise.reject(new Error(res.message || '请求失败'));
    }
    return res;
  },
  (error) => {
    const message =
      error.response?.data?.message || error.message || '网络请求失败';
    Message.error({
      content: message,
      duration: 5 * 1000,
    });
    return Promise.reject(error);
  }
);
