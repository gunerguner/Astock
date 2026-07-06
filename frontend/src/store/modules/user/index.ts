import { defineStore } from 'pinia';
import { UserState } from './types';

const useUserStore = defineStore('user', {
  state: (): UserState => ({
    name: 'Astock',
    avatar: undefined,
    job: undefined,
    organization: undefined,
    location: undefined,
    email: undefined,
    introduction: undefined,
    personalWebsite: undefined,
    jobName: undefined,
    organizationName: undefined,
    locationName: undefined,
    phone: undefined,
    registrationDate: undefined,
    accountId: undefined,
    certification: undefined,
    role: 'admin',
  }),

  getters: {
    userInfo(state: UserState): UserState {
      return { ...state };
    },
  },

  actions: {
    setInfo(partial: Partial<UserState>) {
      this.$patch(partial);
    },
    resetInfo() {
      this.$reset();
    },
  },
});

export default useUserStore;
