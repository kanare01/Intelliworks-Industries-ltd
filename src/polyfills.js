// Ensure global fetch can be read and set without throwing "Cannot set property fetch of #<Window> which has only a getter"
(function initFetchPolyfill() {
  try {
    const targetObj = typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : null);
    if (targetObj) {
      const origFetch = targetObj.fetch;
      let activeFetch = origFetch ? function(...args) {
        return origFetch.apply(this || targetObj, args);
      } : null;

      try {
        Object.defineProperty(targetObj, 'fetch', {
          get() {
            return activeFetch;
          },
          set(fn) {
            activeFetch = fn;
          },
          configurable: true,
          enumerable: true
        });
      } catch (err) {
        // Ignored if targetObj.fetch is already configurable or locked
      }

      if (typeof globalThis !== 'undefined' && globalThis !== targetObj) {
        try {
          Object.defineProperty(globalThis, 'fetch', {
            get() {
              return activeFetch;
            },
            set(fn) {
              activeFetch = fn;
            },
            configurable: true,
            enumerable: true
          });
        } catch (err) {
          // Ignored
        }
      }
    }
  } catch (e) {
    // Non-blocking
  }
})();
