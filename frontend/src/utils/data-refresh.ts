import mitt from 'mitt';

const emitter = mitt();
const DATA_REFRESH_KEY = 'DATA_REFRESH';

export function emitDataRefresh() {
  emitter.emit(DATA_REFRESH_KEY);
}

export function onDataRefresh(handler: () => void) {
  emitter.on(DATA_REFRESH_KEY, handler);
}

export function offDataRefresh(handler: () => void) {
  emitter.off(DATA_REFRESH_KEY, handler);
}
