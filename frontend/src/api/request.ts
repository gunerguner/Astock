import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios';
import { Message } from '@arco-design/web-vue';
import i18n from '@/locale';

const { t } = i18n.global;

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export type HttpResponse<T = unknown> = ApiResponse<T>;

export interface RequestInstance {
  get<T = unknown, D = unknown>(
    url: string,
    config?: AxiosRequestConfig<D>
  ): Promise<T>;
  post<T = unknown, D = unknown>(
    url: string,
    data?: D,
    config?: AxiosRequestConfig<D>
  ): Promise<T>;
}

const instance = axios.create({
  baseURL: '/api/v1'
});

instance.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
);

instance.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data;
    if (res.code !== 0) {
      Message.error({
        content: res.message || t('common.requestFailed'),
        duration: 5 * 1000
      });
      return Promise.reject(
        new Error(res.message || t('common.requestFailed'))
      );
    }
    return res.data as unknown as AxiosResponse<ApiResponse>;
  },
  (error) => {
    const message =
      error.response?.data?.message ||
      error.message ||
      t('common.networkFailed');
    Message.error({
      content: message,
      duration: 5 * 1000
    });
    return Promise.reject(error);
  }
);

const request: RequestInstance = {
  get<T, D = unknown>(url: string, config?: AxiosRequestConfig<D>) {
    return instance.get(url, config) as Promise<T>;
  },
  post<T, D = unknown>(url: string, data?: D, config?: AxiosRequestConfig<D>) {
    return instance.post(url, data, config) as Promise<T>;
  }
};

export default request;
