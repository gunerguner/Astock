import mitt from 'mitt';

type DataRefreshEvents = {
  DATA_REFRESH: undefined;
};

const emitter = mitt<DataRefreshEvents>();

export function emitDataRefresh() {
  emitter.emit('DATA_REFRESH');
}

export function onDataRefresh(handler: () => void) {
  emitter.on('DATA_REFRESH', handler);
}

export function offDataRefresh(handler: () => void) {
  emitter.off('DATA_REFRESH', handler);
}
